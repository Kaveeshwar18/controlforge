# Control-Effectiveness Dashboard — PRD & Implementation Plan

**Domain:** Manufacturing plant, IT/OT converged network
**Problem statement:** Management cannot see whether security controls are reducing actual business risk. Technical findings (patches, EDR coverage, segmentation rules, incident closures) never translate into a number a plant manager or CFO can act on.
**Author:** kaveeshwar.dev@gmail.com
**Date:** 2026-09-08
**Status:** Draft v1

---

## 1. Problem & Objective

### 1.1 Problem
IT/OT-converged manufacturing environments generate large volumes of security telemetry (vulnerability scans, EDR alerts, patch status, segmentation logs, incident tickets) but this data stays siloed in technical tools. Executives and plant managers see dashboards full of counts (e.g., "142 open vulnerabilities") with no link to **business risk** — which lines, safety systems, or revenue streams are actually exposed, and whether remediation work is *measurably* reducing that exposure.

### 1.2 Objective
Build a prototype dashboard that:
1. Ingests control telemetry, asset criticality, vulnerabilities, incidents, and remediation status.
2. Computes a **risk score per asset/business unit**, weighted by criticality (safety system, production line, IT asset).
3. Shows **risk reduction attributable to completed controls** — baseline vs. current vs. target — with confidence/error bounds.
4. Provides **role-based views** (CISO, plant manager, OT engineer, external auditor/partner) with different drill-down depth and permissions.
5. Explicitly surfaces **missing, stale, or low-confidence data** rather than presenting a false "green" picture.
6. Handles **failure states** (sensor/feed outage, unverified remediation, conflicting asset inventories) as first-class UI states, not edge cases patched on later.

### 1.3 Non-goals
- Not a full SIEM/GRC replacement — this is a translation/aggregation layer sitting on top of existing tools.
- Not a real-time SOC console (refresh cadence is hourly/daily, not streaming).
- Not production-hardened auth — RBAC is modeled and demonstrated, not enterprise-SSO integrated.

---

## 2. Users & Roles

| Role | Goal | View scope | Permissions |
|---|---|---|---|
| **CISO / Security Director** | See enterprise-wide risk trend, prove ROI of security spend | All orgs/sites, full drill-down | Read all, export, annotate |
| **Plant Manager** | Understand risk to *their* production lines/safety systems in business terms (downtime $, safety), not CVE lists | Single site, business-risk rollup only | Read own site, no raw vuln data unless drilled down |
| **OT/Security Engineer** | Validate which controls are actually effective, triage stale data, close remediation loop | Single site, full technical drill-down | Read/write remediation status, flag data quality issues |
| **External Partner / Auditor** | Verify control effectiveness for compliance (e.g., IEC 62443, insurance audit) without seeing sensitive internals | Site(s) they're scoped to, evidence-only, redacted asset names | Read-only, evidence export, no raw telemetry, no other-org visibility |
| **Multi-org Admin (MSSP/Corporate)** | Compare risk posture across multiple plants/subsidiaries | Cross-org aggregate + per-org drill-in | Read all orgs, manage org/role assignments |

**Key behavior to demonstrate:** the same underlying data renders differently depending on role — e.g., an auditor sees "Control effective, evidence attached" while an engineer sees the underlying CVE IDs and asset hostnames behind that same control.

---

## 3. Data Model

### 3.1 Core entities
- **Organization** (multi-tenant: plant/site, or external partner scope)
- **Asset** — id, name, type (PLC, HMI, historian, IT workstation, safety instrumented system), zone (IT/OT/DMZ per Purdue model), criticality (1–5, tied to safety/production/revenue impact), org_id
- **Control** — id, name, type (patch mgmt, EDR, network segmentation, MFA, backup, allowlisting), applies_to (asset or asset group), status (planned/in-progress/completed/verified), completion_date
- **Vulnerability** — id, CVE/internal ref, asset_id, severity (CVSS), discovered_date, status (open/mitigated/accepted-risk/false-positive)
- **Incident** — id, asset_id or zone, severity, detected_date, resolved_date, root_cause, related_control_id (if a control should have prevented it)
- **Telemetry/Evidence record** — control_id, timestamp, source system, freshness (last_seen), confidence (verified/self-reported/stale/missing)
- **Risk score snapshot** — org_id/asset_id, timestamp, score, method_version, baseline_flag

### 3.2 Freshness & confidence (critical requirement)
Every telemetry-derived field carries:
- `last_updated` timestamp
- `source` (automated feed vs. manual attestation)
- `staleness_state`: `fresh` (<24h for automated, <30d for manual), `aging`, `stale` (>threshold), `missing` (no record at all)

This state is **rendered in the UI**, not just logged — a risk score built on stale data must visibly say so.

---

## 4. Core Logic — Risk Scoring & Attribution

### 4.1 Asset risk score (per asset, per snapshot)
```
asset_risk = criticality_weight
           × exposure_factor(open_vulns, severity)
           × (1 - control_effectiveness)
           × incident_multiplier(recent_incidents)
```
- `exposure_factor`: normalized CVSS-weighted sum of open vulnerabilities on the asset, decayed by age of exposure.
- `control_effectiveness`: fraction of applicable controls in `completed`/`verified` state, weighted by evidence confidence (a "completed" control with `stale` telemetry counts at reduced weight — see §7 failure design).
- `incident_multiplier`: recent unresolved incidents on the asset increase the score (unpatched theory failed to hold).

### 4.2 Business risk rollup
```
business_risk(zone or org) = Σ asset_risk × business_impact_weight(asset)
```
`business_impact_weight` ties asset to $ downtime/hour, safety classification, or revenue dependency — this is what converts a technical score into a number a plant manager understands.

### 4.3 Attribution — "risk reduction attributable to completed controls"
This is the headline metric requested. Method:
1. **Baseline** = business_risk computed at T0 using only *pre-existing* controls (before the intervention period).
2. **Target** = business_risk if all *planned* controls for the period reach `verified` status (best case).
3. **Measured** = business_risk at current time T using actual completed/verified controls.
4. **Attributable reduction** = `baseline − measured`, decomposed per completed control via a marginal-contribution method: recompute business_risk with each completed control's effect removed (counterfactual "what if this control hadn't been done"), attribute the delta to that control. Sum of per-control deltas reconciled against the total reduction (residual = interaction effects, reported explicitly, not hidden).
5. **Error/uncertainty band**: propagate confidence weights from §3.2 — if 30% of the evidence behind a "completed" control is stale/self-reported, the attributed reduction for that control gets a wider confidence interval, shown as a range not a point estimate.

This directly satisfies the requirement: *baseline, target, measured result, error analysis.*

---

## 5. Functional Requirements

### 5.1 Data preparation
- Synthetic data-generation script producing realistic multi-org datasets (assets, controls, vulns, incidents) with deliberately injected data-quality problems (missing fields, stale timestamps, conflicting asset criticality between two source systems).
- ETL/normalization layer mapping heterogeneous source schemas (simulating scanner export, CMDB export, ticketing export) into the core data model.

### 5.2 Core logic
- Risk scoring engine (§4) as a standalone, testable module — not embedded in UI code.
- Attribution engine producing baseline/target/measured/error output per org and per control.
- Freshness/confidence propagation through every computed value.

### 5.3 User interaction
- Org/site switcher (multi-tenant).
- Role switcher (for demo purposes) showing the same data rendered per role in §2.
- Dashboard: business risk trend line (baseline → target → measured), risk-by-zone heatmap, top risk-driving assets, control effectiveness leaderboard.
- Drill-down: click a risk number → see contributing controls → see contributing vulnerabilities/incidents → see raw evidence record with source/timestamp/confidence.
- Explicit UI states: `fresh`, `aging`, `stale`, `missing data` badges on every risk figure; a risk score built substantially on stale/missing data is flagged, not just colored differently — with a plain-language explanation of what's missing.

### 5.4 Evaluation
- Experiment notebook computing baseline/target/measured/error for the synthetic dataset across at least 2 orgs and multiple time snapshots.
- Sensitivity check: how much does the attributed risk reduction change if evidence confidence is downgraded (simulating an audit finding that some "completed" controls were self-attested, not verified).

---

## 6. Multi-Org / Permission Behavior (explicit requirement)

Demonstrate, not just describe, how the *visible workflow* changes:

| Scenario | Behavior |
|---|---|
| CISO switches from Org A to Org B | Full drill-down available in both; cross-org comparison view available only at corporate/MSSP role |
| Plant Manager (Org A) attempts to view Org B | Access denied, org selector doesn't list Org B at all (not just a blocked click) |
| External Auditor views Org A | Asset hostnames/IPs redacted to generic labels ("PLC-Line3-Unit2"); raw CVE list hidden behind an "evidence package" summarizing control verification status only |
| OT Engineer flags a telemetry feed as broken | Risk scores dependent on that feed immediately show `stale`/`missing` badges across all roles' views of that asset — engineer's action changes what everyone sees |
| Data conflict (two source systems disagree on asset criticality) | System does not silently pick one; UI shows a "conflicting data" state and requires an engineer/admin to resolve, with the unresolved conflict visible to CISO as a data-quality risk item itself |

---

## 7. Failure-State Design (explicit requirement — not happy-path only)

At least the following states must be designed and demonstrable in the prototype, each with a distinct, intentional UI treatment (not a generic error page):

1. **Missing telemetry feed** — a control marked "completed" has no evidence record at all. UI: risk contribution from this control is excluded from the "measured" reduction and shown as "unverified — excluded from risk credit," with a call-to-action for the engineer role.
2. **Stale data** — evidence exists but exceeds freshness threshold. UI: risk score still computed but rendered with a visible staleness watermark/band and reduced confidence weight in the attribution math (§4.3), not silently treated as current.
3. **Conflicting source data** — two systems report different criticality or status for the same asset. UI: neither value is auto-resolved; a "data conflict" flag blocks that asset from contributing a point-estimate risk score until reconciled, and the conflict itself is surfaced as a governance risk.
4. **Partial control rollout** — a control is "in progress" (e.g., EDR deployed to 60% of applicable assets). UI: risk credit is prorated, not binary; shown as a progress-weighted partial reduction, distinct from "completed."
5. **Regression** — an asset with a previously "completed/verified" control shows a new incident or reopened vulnerability. UI: control effectiveness for that asset is automatically downgraded and flagged for re-verification; historical attributed-reduction claims for that control are annotated as "under review," not silently left unchanged.
6. **Access/permission failure** — a role attempts an action outside its scope (e.g., auditor tries to view raw asset IPs). UI: explicit "not authorized for this role" state with reason, not a blank screen or generic 403.

Each failure state above should be reachable in the demo dataset/script (i.e., seeded, not hypothetical).

---

## 8. Measurable Experiment Design

**Metric:** Business risk reduction attributable to completed security controls, per org, over a defined observation window.

- **Baseline (T0):** business_risk computed from asset/control/vuln state at period start, using only controls already verified before T0.
- **Target:** business_risk if all controls planned for the window reach `verified` status with full-confidence evidence.
- **Measured (T1):** business_risk computed from actual state at period end, using real (seeded) completion/verification data, with confidence weighting applied.
- **Result:** % risk reduction achieved (measured vs. baseline), and % of target achieved (measured vs. target).
- **Error analysis:**
  - Confidence interval from evidence-quality weighting (§4.3).
  - Sensitivity analysis: rerun with stale/self-attested evidence downgraded to "unverified" — report how much the headline reduction number changes. This quantifies the "cons" of the approach (data quality dependency) rather than hiding it.
  - Attribution residual (interaction effects not cleanly assignable to a single control) reported as a named line item, not absorbed silently into one control's credit.

---

## 9. Known Weaknesses & Mitigations ("cons" and how to solve them efficiently)

| Weakness / Con | Why it matters | Mitigation implemented in this design |
|---|---|---|
| **Garbage-in scoring** — risk score is only as good as source telemetry | Execs could be shown false confidence | Freshness/confidence weighting (§3.2, §4.3) built into the *math*, not just a UI label; stale/missing data mechanically discounts the score rather than being cosmetic |
| **False attribution** — hard to prove a specific control caused a risk drop vs. correlation (e.g., an asset was also decommissioned) | Overclaiming ROI erodes trust in the dashboard | Counterfactual marginal-contribution method (§4.3) + explicit residual/interaction-effect line instead of forcing 100% attribution to named controls |
| **Gaming the metric** — teams mark controls "completed" without real verification to improve the score | Metric becomes a target instead of a measure (Goodhart's law) | Two-tier status: `completed` (self-reported) vs. `verified` (evidence-backed); only `verified` gets full risk credit; unverified-but-completed gets partial/flagged credit |
| **Multi-tenant data leakage** | Cross-org or auditor exposure is a compliance/legal risk | Row-level org scoping enforced at query layer + role-based field redaction (not just UI hiding) — demonstrated explicitly in §6 |
| **Alert/number fatigue at exec level** | If CISO dashboard = engineer dashboard, executives disengage | Role-based rollup (§5.3) — business-risk language and $ / safety framing for plant manager, technical drill-down only for engineer/CISO on demand |
| **Static snapshot ages quickly, no one revisits** | Dashboard becomes another ignored tool | Freshness badges + automatic downgrade of stale evidence (§7.2) forces visible decay, prompting re-verification rather than silent staleness |
| **Single point of failure in scoring formula (weights are subjective)** | Business_impact_weight, criticality scale, etc. are judgment calls | Method versioning on every risk snapshot (`method_version` field) so historical comparisons are never silently distorted by formula changes; weights configurable per org and documented in technical docs, not hardcoded assumptions dressed as fact |
| **OT asset visibility gaps** (many OT devices can't run agents/scanners) | Under-representation of OT risk vs. IT risk | Explicit `missing` staleness state (not defaulted to "low risk") for assets with no telemetry source at all — absence of data is itself surfaced as a risk driver, per NIST/IEC 62443 guidance on OT visibility gaps |

---

## 10. Deliverables (mapped to requirements)

| Deliverable | Description |
|---|---|
| **Field-workflow map** | Diagram of how each role interacts with the system end-to-end (data source → dashboard → decision → remediation loop back to data) |
| **Data-generation script** | Python script producing seeded synthetic multi-org dataset incl. injected failure states |
| **Functional application** | Working prototype (backend risk/attribution engine + frontend dashboard with role/org switching) |
| **Experiment notebook** | Baseline/target/measured/error computation + sensitivity analysis, reproducible |
| **Failure-mode analysis** | Write-up of the 6 failure states in §7, how each is triggered, detected, and displayed |
| **User/stakeholder feedback summary** | Structured feedback from a mock stakeholder review session (plant manager + engineer personas minimum) |
| **Technical documentation** | Data model, scoring formulas, RBAC model, API/module reference |
| **Presentation** | Executive-facing summary translating the above into the business narrative |

---

## 11. Implementation Plan

### Phase 0 — Setup (Day 1)
- Repo scaffold: `/data-gen`, `/backend` (scoring engine + API), `/frontend` (dashboard), `/notebooks`, `/docs`
- Define core data schema (§3) as code (pydantic/TypeScript types)

### Phase 1 — Data layer (Days 2–3)
- Build data-generation script: multi-org, assets, controls, vulns, incidents, telemetry, with seeded failure states (§7)
- Build ETL/normalization stubs simulating multiple source systems

### Phase 2 — Core logic (Days 4–6)
- Implement asset risk scoring (§4.1)
- Implement business risk rollup (§4.2)
- Implement attribution engine: baseline/target/measured + counterfactual marginal contribution + confidence weighting (§4.3)
- Unit tests incl. failure-state inputs (missing/stale/conflicting data)

### Phase 3 — API + RBAC (Days 7–8)
- REST/GraphQL API exposing scores, drill-down evidence, freshness metadata
- Role/org scoping middleware (row-level + field-level redaction)

### Phase 4 — Frontend dashboard (Days 9–12)
- Org/role switcher
- Business risk trend (baseline→target→measured) chart
- Risk-by-zone heatmap, top risk drivers, control effectiveness leaderboard
- Drill-down flow: risk number → controls → vulns/incidents → raw evidence
- Explicit freshness/missing/conflict/unauthorized UI states (§7)

### Phase 5 — Experiment & evaluation (Days 13–14)
- Run experiment notebook across ≥2 orgs, multiple snapshots
- Sensitivity/error analysis
- Failure-mode analysis document

### Phase 6 — Stakeholder validation (Day 15)
- Mock review session with plant-manager and engineer personas (or real stakeholders if available)
- Collect structured feedback (usefulness, trust in numbers, missing states)
- Iterate on 1–2 highest-impact items

### Phase 7 — Documentation & presentation (Day 16)
- Technical docs, field-workflow map, executive presentation

---

## 12. Success Criteria
- Prototype computes and displays baseline/target/measured risk reduction with error bounds for ≥2 orgs.
- All 6 failure states in §7 are seeded, triggerable, and visibly distinct in the UI.
- Role-based view and permission differences are demonstrable live (not just documented).
- Stakeholder feedback session produces at least 3 concrete, addressed action items.
- Every risk figure in the UI is traceable via drill-down to raw evidence with a timestamp and confidence state.
