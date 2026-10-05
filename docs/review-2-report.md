# Review 2 Phase Report: ControlForge

**A control-effectiveness dashboard that translates IT/OT security telemetry into measurable business risk**

| | |
|---|---|
| **Project** | Control-effectiveness dashboard for a manufacturing organisation connecting office IT with operational technology (OT) networks |
| **Batch / course** | IE28 · Semester 5 · COE Growth Project |
| **Phase** | Review 2: **75% completion checkpoint** (previous: Review 1 at 35%) |
| **Report date** | 5 October 2026 |
| **Repository** | https://github.com/Kaveeshwar18/controlforge |
| **Scoring method version** | `v1.1` (stamped on every computed score; v1.0 was used at Review 1) |
| **Reference dataset** | `data-gen/generate_data.py --seed 42`. All figures in this report reproduce from that seed |

---

## 1. Executive summary

ControlForge is a working full-stack application: a FastAPI backend, a SQLite store, a React frontend, a standalone scoring engine, an automated test suite and an executed experiment notebook. It answers one management question for a six-plant manufacturing group: *are our completed security controls actually reducing business risk, and how confident can we be in that number?*

Between Review 1 (35%) and Review 2 (75%), the project moved from "built" to **tested and measured**:

1. **Every Review 1 action item is closed** (§4). That covers the four "what's next" items, both open stakeholder action items, and the missing repository link.
2. **An automated test suite was added: 92 tests** (`backend/tests/`, pytest). It covers every failure-state rule, server-side RBAC, redaction, and the resolve-and-write-back workflow through the real HTTP API. All 92 pass.
3. **A seventh designed failure state: source-feed outage.** Each plant now has four tracked integrations (vulnerability scanner, CMDB, EDR, ticketing). A stale or never-connected feed shows a degraded-data banner and widens the worst-case bound in the math.
4. **The experiment was rebuilt and re-executed** (`notebooks/experiment.ipynb`, 11 sections). It now includes a real adverse-audit re-score, one-at-a-time parameter sensitivity, 20-seed robustness, an intervention experiment driven through the live API, and three stress-tested edge cases.
5. **The experiment found and drove fixes for four scoring-method flaws** (method v1.1, §9.7), and **corrected one Review 1 claim** about attribution residuals. The headline metric is now **control-attributable risk reduction**, measured against a same-day counterfactual. It is reported separately from total change since baseline, which also includes vulnerability churn.
6. **Role-based workflow changes are now explicit in the UI.** A per-role "What this view includes" card lists what is visible, what the server withholds, and which actions the role may take.

**Headline measured result** (network of six plants, seed 42, method v1.1):

| Metric | Value |
|---|---|
| Baseline business-risk index (180 days ago) | **9.5** / 100 |
| Target (current control plan fully verified) | **1.1** |
| Measured today, point estimate | **7.1** |
| Total change since baseline | **−24.8%** (best case −56.9%, worst case **+2.6%**) |
| Share of achievable reduction reached | **28.0%** of target |
| Risk cut by completed controls, per plant (same-day counterfactual) | **14.9% to 44.4%** (point estimates) |
| Plants whose reduction survives the worst case ("reportable") | **3 of 6** |
| Same, after a one-week data-quality "verification sprint" through the API | **6 of 6**; median band narrowing **42%** |

---

## 2. Problem statement

Converged IT/OT manufacturing plants produce large volumes of security telemetry: scanner findings, EDR alerts, patch status, segmentation evidence and incident tickets. That telemetry stays in technical tools. Management sees counts ("142 open vulnerabilities") with no link to business impact, and cannot tell whether remediation work is measurably reducing risk.

There are two specific failure modes the solution must avoid:
- **False confidence.** Presenting a control marked "completed" as effective when nothing independent has verified it.
- **False calm.** Presenting missing, stale or unmonitored data as low risk because there is "no finding".

## 3. Objectives and their status

| # | Objective (from PRD §1.2) | Status at Review 2 |
|---|---|---|
| O1 | Ingest control telemetry, asset criticality, vulnerabilities, incidents and remediation status | **Completed.** 9 ORM entities, seeded for 6 plants (§8) |
| O2 | Compute risk per asset and business unit, weighted by criticality and business impact | **Completed.** `scoring.asset_risk`, `business_risk` (§9) |
| O3 | Show risk reduction attributable to completed controls, with baseline, target, measured and error bounds | **Completed, strengthened in Phase 2.** Same-day counterfactual attribution, best/worst bands, reportability rule (§9.5) |
| O4 | Role-based views with different drill-down depth and permissions, across multiple organisations and an external partner | **Completed.** 5 roles, 9 personas, 6 plants + corporate org, enforced server-side (§10) |
| O5 | Explicitly surface missing, stale or low-confidence data | **Completed, extended in Phase 2.** Evidence freshness plus source-feed freshness (§13) |
| O6 | Failure states as first-class designed states | **Completed.** 8 designed states, each seeded, rendered distinctly and covered by tests (§13) |
| O7 | Measurable experiment with error analysis | **Completed in Phase 2.** Executed notebook, 6 error analyses + intervention (§15) |
| O8 | User/stakeholder validation | **Partially complete.** Round 1 done and all its actions closed. Round 2 with real participants is scheduled for the final phase (§16) |

---

## 4. Response to Review 1 feedback

Review 1 recorded the open items below. **Each one has been implemented**, and the evidence is in the repository.

| # | Review 1 item (source) | Phase 2 implementation | Evidence |
|---|---|---|---|
| R1 | "Finish technical documentation (facility-map section, current auth/entry-point description)" (Review 1 §4.1) | Technical documentation extended with the v1.1 error-band table, control-attributable metric, source-feed health (§3.5), a full API reference (§4b), and a testing section (§4c) | `docs/technical-documentation.md` |
| R2 | "Run a fresh stakeholder walkthrough … and update the feedback summary" (Review 1 §4.2) | Feedback summary updated with the Phase 2 status of every Round 1 action. The Round 2 session with real participants is scheduled for the final phase and is **not** reported as done | `docs/user-feedback-summary.md` (Phase 2 section) |
| R3 | "Update the presentation deck" (Review 1 §4.3) | Content for the deck is now generated from this report's verified results (§15). Final deck production is in the remaining 25% | §17.3 |
| R4 | "Harden remaining rough edges identified during testing" (Review 1 §4.4) | 92 automated tests added. Three further defects (C, D, E) found and fixed. Hardening includes server-side redaction of feed error text for non-technical roles | `backend/tests/`, `docs/failure-mode-analysis.md` §C–E |
| R5 | Stakeholder action #2: "Plain-language explainer for 'unverified controls' count on Plant Manager view" (feedback summary, "Open: next iteration") | **Implemented.** A role-specific explainer appears in the asset drill-down whenever an asset has unverified controls. It explains what "not yet verified" means and when to escalate to the CISO | `frontend/src/components/AssetDrilldown.jsx` |
| R6 | Stakeholder action #5: "Explain the interaction-effect residual in-context" (feedback summary, "Open: next iteration") | **Implemented, then corrected by the experiment.** Investigation showed the residual was vulnerability churn, not control overlap (§9.7, D2). The residual is now ≈0 by construction, and the leaderboard footnote explains the counterfactual basis instead | `ControlLeaderboard.jsx`; notebook §8 |
| R7 | "Repository link: pending" (Review 1 §5) | Public repository provided | https://github.com/Kaveeshwar18/controlforge |
| R8 | Show how the visible workflow changes per role (assignment brief, emphasised in Review 1 §3) | **Implemented.** `RoleScopeCard` on every dashboard: *Visible / Withheld (enforced by the server) / What you can do*, plus a redacted-view notice for auditors | `frontend/src/components/RoleScopeCard.jsx` |

---

## 5. Phase status: what makes up the 75%

| Deliverable (assignment brief) | Review 1 | Review 2 | Notes |
|---|---|---|---|
| Field-workflow map | Done | Done | `docs/field-workflow-map.md`, per-role loop from data source → decision → remediation → data |
| Data-generation script | Done | **Extended** | Source feeds, configurable outages, `--seed` CLI, `CONTROLFORGE_DB` override |
| Functional application | Done | **Extended** | Feed-health panel, degraded banner, role-scope card, reportability chip, control-attributable card |
| Core logic | Done (v1.0) | **Revised (v1.1)** | 4 method fixes driven by the experiment |
| Experiment notebook | Done (basic) | **Rebuilt and executed** | 11 sections, 3 new charts, reproducible on a throwaway DB |
| Failure-mode analysis | 6 states + 2 bugs | **8 states + 5 defects** | `docs/failure-mode-analysis.md` §1–8, §A–E |
| Automated testing | None | **92 tests** | `backend/tests/` |
| Technical documentation | In progress | **Done for v1.1** | API reference, test inventory, error-band table |
| User feedback summary | Round 1 | Round 1 closed | Round 2 pending (final phase) |
| Presentation | Draft | Draft | Final deck in the final phase |

---

## 6. Methodology

1. **Design-science build-measure loop.** Requirements came from the PRD (`PRD_Control_Effectiveness_Dashboard.md`). Each capability was built as a running system, exercised through the UI as every role, then measured in the notebook. Results that contradicted design intent were treated as defects (§9.7).
2. **Synthetic but structured data.** Real plant security telemetry is confidential, so a seeded generator produces a realistic dataset. That includes deliberately injected failure states, so each failure path is exercised rather than described.
3. **Scoring engine isolated from the web layer.** `backend/app/scoring.py` holds pure functions over a database session, with no FastAPI dependency. The API, the tests and the notebook all call the same functions, so the experiment measures exactly what the dashboard shows.
4. **Counterfactual attribution.** Control effect is measured by re-scoring the same day with controls removed, not by before/after comparison alone.
5. **Uncertainty as a first-class output.** Every measured score has a best and worst case derived from evidence quality and data-feed health. A decision rule (reportable only if the worst case still shows a reduction) turns the band into an action.
6. **Method versioning.** `METHOD_VERSION` is stamped on every summary and stored snapshot, so a formula change never silently rewrites history.

---

## 7. System architecture and technology

```
 data-gen/plants.json ──► data-gen/generate_data.py ──► SQLite (backend/coe_dashboard.sqlite3)
   (plants, coordinates,      (seeded synthetic assets, controls,      ▲
    roles, feed faults)        evidence, vulns, incidents, feeds,      │ SQLAlchemy ORM (models.py)
                               data-quality issues, snapshots)         │
                                                                       │
            ┌──────────────── backend/app ─────────────────────────────┴────────┐
            │ scoring.py   pure risk / attribution / feed-health engine          │
            │ rbac.py      identity → role capabilities, org scope, redaction    │
            │ auth.py      bcrypt hashing, JWT issue/verify                      │
            │ routers/     auth · orgs · risk · assets · controls ·              │
            │              dataquality · compare   (16 endpoints, §10.4)         │
            └──────────────▲────────────────────────────────▲───────────────────┘
                           │ JSON over HTTP (Bearer JWT)    │ direct import
              frontend/ (React SPA)              notebooks/experiment.ipynb
              dashboard, map, drill-downs,       backend/tests/ (pytest, TestClient)
              data-quality inbox
```

| Layer | Technology (pinned version) |
|---|---|
| API | Python 3.11, FastAPI 0.115.0, Uvicorn 0.30.6, Pydantic 2.9.2 (with `EmailStr`) |
| Persistence | SQLAlchemy 2.0.35 ORM on SQLite (path overridable via `CONTROLFORGE_DB`) |
| Security | bcrypt 5.0.0, PyJWT 2.13.0 (HS256) |
| Frontend | React 19.2, Vite 8.2, Recharts 3.10 (trend chart), react-simple-maps 5.0 + world-atlas 2.0 (facility map), oxlint |
| Testing | pytest 8.3.3, httpx 0.27.2 / Starlette `TestClient` |
| Experiment | Jupyter (nbconvert-executed), pandas, NumPy, matplotlib |

---

## 8. Data model and data preparation

### 8.1 Entities (`backend/app/models.py`)

| Entity | Role in scoring | Key fields |
|---|---|---|
| `Organization` | Plant or corporate parent | `org_type`, `parent_id`, `city`, `state`, `lat`, `lon` |
| `User`, `UserOrgAccess` | Persona, role, org grants | `role`; `redacted` per grant (auditor) |
| `Account` | Login credentials, separate from authorisation | `username`, `email`, `password_hash` (bcrypt) |
| `Asset` | OT/IT/DMZ asset (Purdue zone) | `criticality_scanner`, `criticality_cmdb` (two sources), `criticality_resolved`, `business_impact_weight`, `has_telemetry` |
| `Control` | Asset- or zone-scoped control | `control_type` (EDR, patching, segmentation, MFA, backup, allowlisting, privileged access), `status`, `rollout_percentage`, `planned_date`, `completion_date` |
| `Evidence` | Proof a control works | `timestamp`, `source` (automated_scan / third_party_audit / manual_attestation), `result` (pass / fail) |
| `Vulnerability` | Exposure | `cvss`, `discovered_date`, `status`, `resolved_date` |
| `Incident` | Realised risk | `severity`, `detected_date`, `resolved_date`, `related_control_id` |
| `DataFeed` (**new**) | Upstream integration health | `feed_type`, `expected_interval_hours`, `last_sync`, `last_error` |
| `DataQualityIssue` | Engineer inbox | `issue_type` (conflict / missing_feed / stale_evidence / regression / **feed_outage**), `asset_id`, `control_id`, **`feed_id`** |
| `RiskSnapshot` | Historical trend | `as_of_date`, `score_normalized`, `method_version` |

### 8.2 Generated dataset (seed 42)

**6 plants** (Chennai, Coimbatore, Bengaluru, Hyderabad, Pune, Mumbai, with real city coordinates) plus a corporate org. **137 assets, 283 controls, 315 evidence records, 275 vulnerabilities, 23 incidents, 24 source feeds, 75 data-quality issues, 42 risk snapshots, 9 personas.**

Plant differences come from one data-driven knob, `maturity` in `plants.json` (Pune 0.25 → Bengaluru 0.82). It scales completed controls, verified evidence, backlog remediation, criticality conflicts and unmonitored assets. Adding a plant is a data change, not a code change.

### 8.3 Injected failure states (the generator's contract)
missing evidence on completed controls · stale evidence · scanner-vs-CMDB criticality conflicts · partial rollouts · regression (incident on a verified control's asset) · unmonitored OT assets · **source-feed outages** (`feed_faults`: Pune scanner stale 218 h; Hyderabad ticketing never connected; Mumbai CMDB stale 40 days; Chennai EDR delayed).

---

## 9. Core logic and algorithms (`backend/app/scoring.py`)

### 9.1 Asset risk
```
asset_risk = criticality × exposure × (1 − mean control effectiveness) × incident_multiplier
exposure   = min(5, Σ open vulns (CVSS/10) × age factor{<30d: 1.0, 30–90d: 1.3, >90d: 1.6})
incident_multiplier = 1 + 0.15 × (unresolved + 0.5 × resolved incidents in last 90 days)
```
- Criticality conflict: score with the **higher** of the two source values until an engineer resolves it.
- Unmonitored asset: fixed exposure 2.5 (point), **1.0 / 4.0 best / worst** (v1.1), and zero control credit.

### 9.2 Control effectiveness with evidence-time-awareness
- Evidence is resolved **as known at the scored date** (`timestamp <= as_of`), so a baseline never uses proof recorded later.
- `planned` → 0. `in_progress` → 0.7 × rollout fraction, with historical rollout linearly interpolated from `planned_date`.
- `completed` → 1.0 × confidence if verified (automated scan or audit, not stale, passed). Otherwise 0.7 × confidence. **0 if there is no evidence. 0 if the most recent check failed** (v1.1).
- Confidence table by (freshness, source): fresh 1.0 / 1.0 / 0.7, aging 0.85 / 0.85 / 0.5, stale 0.3 / 0.3 / 0.2 for scan / audit / attestation. Freshness thresholds: automated ≤2 d fresh, ≤14 d aging; manual ≤14 d fresh, ≤45 d aging.

### 9.3 Business risk rollup and normalisation
`business_risk = Σ asset_risk × business_impact_weight`, normalised to a 0–100 index against a theoretical worst case (max criticality, exposure and incident multiplier, zero control credit).

### 9.4 Error band (method v1.1)

| Input | Point | Best case | Worst case |
|---|---|---|---|
| Verified evidence | table confidence | 1.0 | table confidence |
| Self-attested evidence | 0.7 × confidence | 0.7 | **0** |
| Stale / missing evidence | discounted / 0 | 1.0 if any passing record | **0** |
| Failed check | 0 | 0 | 0 |
| Unmonitored exposure | 2.5 | 1.0 | 4.0 |
| Scanner feed stale/missing | — | — | exposure × 1.25 |
| Ticketing feed stale/missing | — | — | incident multiplier + 0.15 |

### 9.5 Baseline, target, measured, attribution
- **Baseline**: business risk at today − 180 days.
- **Target**: every control already in the plan verified, effectiveness capped at 0.9 (`TARGET_MAX_EFFECTIVENESS`), with telemetry gaps assumed fixed.
- **Measured**: today, with point, best and worst case.
- **Control-attributable reduction** (new in v1.1): `(R_without_completed_controls − R_today) / R_without_completed_controls`, both scored today under the same bias, so vulnerability churn and feed adjustments cancel out.
- **Per-control attribution**: marginal counterfactual (exclude one control and re-score). Because risk is linear in each control's credit, the credits add up exactly to the control-attributable total, so the residual is ≈0. The check is kept as a guard.
- **Reportable** = worst-case total reduction > 0.

### 9.6 Source-feed health
`feed_state`: fresh ≤1.5× expected interval, aging ≤4×, stale beyond that, missing if never synced. Point estimates are unchanged. Only the worst case is widened (§9.4).

### 9.7 Method v1.1: defects found by the experiment and fixed

| # | Observed in the v2 experiment (first run) | Root cause | Fix |
|---|---|---|---|
| D1 | Band width uncorrelated with evidence quality (r = −0.05), and a verification sprint *widened* the band | Worst case capped all evidence at 0.5, including fresh verified evidence | Worst case trusts verified evidence fully and self-attested/stale/missing not at all. Correlation is now r = 0.26 and the sprint narrows the band by a median 42% |
| D2 | Bengaluru's "reduction attributed to controls" of 60.2% was 48.8 points vulnerability churn | Total change since baseline was labelled as control effect | Separate `controls_reduction_pct` against a same-day counterfactual |
| D3 | A fully unmonitored plant had a zero-width band | One constant for all three cases | Unmonitored best/worst bounds |
| D4 | Failed checks would earn credit | `Evidence.result` ignored | Fail → zero credit, flagged in attribution note |
| — | Review 1 explained a large negative residual as "overlapping controls" | The residual was taken against total change | Corrected. The residual is computed against the control-attributable total and is now 0.0 at every plant |

Also fixed: defect **C**. The v1 notebook reported the best case under a "worst case" label because the fields were named `reduction_low/high`. They were renamed `reduction_best_case/worst_case`, and a regression test now guards the ordering.

---

## 10. Role-based access, multi-organisation and external-partner support

### 10.1 Roles and personas (from `data-gen/plants.json`)

| Role | Personas | Org scope | Technical drill-down | Raw asset names | Resolve issues | Cross-plant compare |
|---|---|---|---|---|---|---|
| CISO | Sarah Chen (Chennai), Tom Becker (Mumbai) | own plant | yes | yes | no | no |
| Plant Manager | Miguel Alvarez (Chennai), Lena Ortiz (Pune) | own plant | **no**, business summary only | yes | no | no |
| OT Security Engineer | Priya Nair (Chennai), Dev Patel (Bengaluru), Ravi Krishnan (Pune) | own plant | yes | yes | **yes** | no |
| External Auditor (partner org "Meridian Assurance Partners") | James Cole | Chennai, Pune, Mumbai (redacted grants) | **no**, evidence statements only | **no** (`Type-Zone-UnitN`) | no | no |
| Corporate Admin | Amara Diallo | corporate + all 6 plants | yes | yes | yes | **yes** |

### 10.2 How the visible workflow changes

| Situation | What happens |
|---|---|
| Plant Manager opens the app | Org selector lists only their plant. Other plants are not returned by `GET /orgs` at all. The controls panel is hidden and the asset drill-down shows counts (applicable / verified / not yet verified / open weaknesses), not CVEs |
| Plant Manager requests another plant directly | `403` with a reason (*"role PLANT_MANAGER does not have access to organization 'pune'"*), rendered as an explicit error state |
| External Auditor views a plant | Equipment names masked. The control drill-down returns `evidence_package_statement` ("Independently verified" / "Not independently verified" / "No verification evidence on file") instead of the evidence log. The feed panel shows staleness but not internal error text |
| OT Engineer resolves an issue | Write-back to the scored record (criticality set, evidence inserted, telemetry connected, feed re-synced). Every other role's next read reflects it |
| Corporate Admin | Gets the extra *Compare* view across all six plants and can resolve anywhere |
| Any role | The "What this view includes" card states visible items, server-withheld items and permitted actions |

### 10.3 Enforcement
All scoping and redaction happens server-side (`rbac.require_org_access`, `is_redacted`, capability flags, `_feeds_for`). The UI only reflects what the API returns. Asset IDs stay opaque lookup tokens in redacted views, and only display names are masked (defect A, Review 1).

### 10.4 API surface (16 endpoints)
`POST /auth/signup`, `POST /auth/login`, `GET /auth/me`, `GET /me`, `GET /orgs`, `GET /orgs/{id}/risk-summary`, `/risk-trend`, `/zones`, `/controls`, `/controls/{cid}`, `/assets`, `/assets/{aid}`, `/data-quality`, `POST /data-quality/{iid}/resolve`, `GET /orgs/{id}/feeds` (**new**), `GET /compare`. The full reference is in `docs/technical-documentation.md` §4b.

---

## 11. Security measures

| Measure | Implementation | Verified by test |
|---|---|---|
| Password storage | bcrypt with per-hash salt. Never logged or returned | — |
| Session tokens | JWT HS256, 12 h TTL, `Authorization: Bearer` | `test_no_token_is_rejected`, `test_tampered_token_is_rejected` |
| Identity binding | Token → account → exactly one persona. No client-supplied role or persona header | all RBAC tests use real tokens |
| Account enumeration | Identical 401 message for a wrong password and an unknown user | `test_wrong_password_gives_the_same_vague_error_as_unknown_user` |
| Signing secret | `CONTROLFORGE_SECRET` env var. Local `.dev-secret` fallback (mode 0600, git-ignored) | — |
| Tenant isolation | Org scoping on every org endpoint | `test_every_org_endpoint_enforces_scoping` (7 endpoints) |
| Field redaction | Asset names, evidence logs and feed error text for non-technical roles | 4 auditor/plant-manager tests |
| Write authorisation | Resolve restricted to OT Engineer / Corp Admin. Double-resolve rejected (400) | `test_only_engineer_or_admin_can_resolve`, `test_resolving_twice_is_rejected` |

**Known security gaps, documented and out of prototype scope:** no login rate-limiting or lockout, MFA, password reset or refresh-token rotation; tokens are held in browser storage rather than HttpOnly cookies; CORS is `allow_origins=["*"]` for local development.

---

## 12. User interaction and interface features

| Component | Function |
|---|---|
| `SummaryBanner` | Plain-language headline ("risk is X% lower than on <date>"), control-attributable cut, best/worst range, **reportability chip**, measurement date and method version |
| `Gauge` | % of achievable (target) reduction reached |
| `RiskSummaryCards` | Risk today with range. Technical roles see "Cut by completed controls", business roles see "Change since baseline" |
| `ControlLeaderboard` | Top controls by credited share, with confidence tone (verified / self-reported / out of date / not verified / failed). Click for evidence |
| `ControlDrilldown`, `AssetDrilldown` | Evidence log, CVEs and incidents (technical roles), or business summary with explainer (others) |
| `DegradedBanner`, `FeedHealthPanel` (**new**) | Per-feed last-sync age and state, plain-language consequence, "Restore feed" action for engineers |
| `RoleScopeCard` (**new**) | Visible / withheld / permitted actions per role |
| `MapPanel` | India facility map (react-simple-maps, Mercator). Pins coloured by fixed risk bands (high ≥9, elevated ≥6), per-plant metrics, click to switch plant |
| `RiskTrendChart`, `ZoneHeatmap` | 180-day trend against the target line (Recharts). Risk share by IT/OT/DMZ zone with unmonitored counts |
| `AssetList` | Top-25 risk assets with conflict and no-telemetry flags, free-text search |
| `DataQualityPanel` | Inbox by issue type (Conflict / Unverified / Out of date / Regression / **Feed down**) with resolve action. Read-only roles see "Engineer only" |
| `ComparePanel` | Cross-plant comparison (Corp Admin only) |
| `IdentityBar` | "Viewing as" persona switcher (real login per persona), plant switcher |

---

## 13. Failure-state design (8 designed states)

| # | State | Detection | Effect on score | UI treatment | Test |
|---|---|---|---|---|---|
| 1 | Completed control, no evidence | `latest_evidence_state` → missing | zero credit | "Not verified, no credit given"; inbox item | `test_completed_control_without_evidence_gets_zero_credit` |
| 2 | Stale evidence | age vs source threshold | confidence 0.2–0.3; worst case 0 | "Stale" badge; inbox item | `test_stale_evidence_is_discounted_not_zeroed` |
| 3 | Conflicting criticality | scanner ≠ CMDB, unresolved | uses the higher value | "Data conflict" flag; engineer resolves | `test_criticality_conflict_scores_conservatively`, `test_resolving_a_conflict_clears_it_for_every_role` |
| 4 | Partial rollout | `in_progress` + % | prorated 0.7 × % | "In progress (n% rolled out)" | `test_partial_rollout_is_prorated` |
| 5 | Regression | incident on a verified control's asset | incident multiplier | "Regression" review item | `test_unresolved_incident_raises_risk` |
| 6 | Unmonitored asset | `has_telemetry = False` | elevated exposure, wide band | "No telemetry" badge, zone counts | `test_unmonitored_asset_is_not_scored_as_safe`, `..._gets_an_uncertainty_band...` |
| 7 | Permission failure | server capability/scope check | — | explicit 403 reason banner | `test_plant_manager_gets_explicit_403_for_another_plant` |
| 8 | **Source-feed outage (new)** | `feed_state` stale/missing | worst case widened | degraded banner, freshness panel, inbox | `test_stale_scanner_widens_worst_case_but_not_point_estimate`, `test_resolving_a_feed_outage_narrows_the_worst_case` |

Additional state introduced in v1.1: **failed verification** (zero credit, "Failed its most recent verification"), tested by `test_failed_verification_earns_no_credit_even_when_recent`.

---

## 14. Testing and quality assurance

**92 automated tests, all passing** (`cd backend && python -m pytest`, about 40 s).

| Suite | Tests | Scope |
|---|---|---|
| `tests/test_scoring.py` | 25 functions → 63 cases (parametrised) | Hand-computed scenarios on an in-memory DB for every scoring rule and failure state. Engine invariants across all six seeded plants: best ≤ point ≤ worst, target ≤ measured, unverified = zero credit, best-case ≥ worst-case reduction, control-attributable within [0, 100] and ordered |
| `tests/test_api.py` | 23 functions → 29 cases | Real HTTP with signed JWTs: authentication, scoping, redaction, admin-only compare, resolve permissions and write-back |

Test isolation: unit tests use a fresh in-memory SQLite per test. API tests use a throwaway seeded file database (`CONTROLFORGE_DB`), reseeded before and after every mutating test. The frontend builds cleanly with Vite; oxlint reports no errors (2 non-blocking style warnings).

**Defects found and fixed during testing** (`docs/failure-mode-analysis.md`):

| ID | Defect | Found by |
|---|---|---|
| A | Redacted asset ID broke auditor drill-down | Phase 1 manual role walkthrough |
| B | Out-of-order responses showed the wrong plant's numbers | Phase 1 rapid switching |
| C | Notebook reported the best case as the worst case | Phase 2 notebook review |
| D1–D4 | Four scoring-method flaws (§9.7) | Phase 2 experiment |
| E | False "no plants assigned" error on every first load | Phase 2 UI check |

---

## 15. Experiment and results (`notebooks/experiment.ipynb`)

The notebook runs on its own throwaway database (seed 42), drives the production scoring engine directly, and drives the live API for the intervention. Charts: `baseline_measured_target.png`, `parameter_sensitivity.png`, `seed_robustness.png`.

### 15.1 Baseline, target, measured (risk index 0–100)

| Plant (maturity) | Baseline | Target | Measured [best–worst] | Change since baseline [best / worst] | Cut by completed controls [range] | % of target | Reportable |
|---|---|---|---|---|---|---|---|
| Bengaluru (0.82) | 11.16 | 0.66 | 4.45 [1.94–6.81] | −60.2% [−82.6 / −39.0] | 31.8% [15.5–61.0] | 63.9 | **Yes** |
| Coimbatore (0.72) | 10.20 | 1.45 | 9.03 [7.83–9.93] | −11.4% [−23.3 / −2.7] | 30.3% [25.0–38.3] | 13.3 | **Yes** |
| Mumbai (0.62) | 8.44 | 1.19 | 6.27 [3.45–8.01] | −25.7% [−59.1 / −5.1] | 44.4% [32.1–67.9] | 29.9 | **Yes** |
| Hyderabad (0.55) | 8.73 | 1.16 | 7.96 [3.77–11.61] | −8.9% [−56.8 / +32.9] | 26.9% [18.4–56.1] | 10.3 | No |
| Chennai (0.35) | 8.03 | 0.84 | 6.75 [3.96–9.28] | −16.0% [−50.7 / +15.5] | 14.9% [8.2–31.2] | 17.8 | No |
| Pune (0.25) | 10.19 | 1.26 | 8.39 [3.96–12.53] | −17.6% [−61.1 / +23.0] | 29.5% [22.9–57.1] | 20.1 | No |
| **Network** | **9.5** | **1.1** | **7.1** | **−24.8% [−56.9 / +2.6]** | — | **28.0** | — |

*Change since baseline: negative means risk fell. Worst-case values of +15.5% to +32.9% mean risk may have **risen**.*

**Interpretation.** Every plant's point estimate shows risk falling. Only three of six can report it, because at Chennai, Hyderabad and Pune the evidence can't rule out an increase. Those three plants combine weak evidence with unmonitored OT assets and, at Pune and Hyderabad, a dead feed.

### 15.2 Error analyses

| Analysis | Method | Result |
|---|---|---|
| A. What drives band width | Correlate band width with the weak-evidence share of completed controls | r = 0.26 (v1.0: −0.05). The widest bands (Hyderabad 89.7 pts, Pune 84.1 pts) combine degraded feeds and unmonitored assets. n = 6, so this is indicative only |
| B. Controls vs. exposure churn | Re-score baseline and today with all control credit forced to zero, then split the change | Bengaluru: 48.8 of 60.2 pts from exposure change. At the other five plants exposure *worsened* (−3.8 to −43.8 pts) and controls offset it. This is why total change is not reported as control effect |
| C. Adverse audit | Re-score with every self-attestation treated as absent | Network reduction 24.8% → **23.1%**. Largest drops Mumbai −5.4 pts, Coimbatore −4.7 pts. Reportability unchanged |
| D. Parameter sensitivity | One-at-a-time low/high on four judgement weights | Unverified-control credit 0.5–0.9 → 21.0–28.7% (swing **7.7 pts**). Unmonitored exposure 1.5–3.5 → 28.0–22.3% (5.7). Self-attestation confidence ×0.5–×1.4 → 23.9–25.6% (1.7). Incident weight 0.05–0.30 → 25.1–24.4% (0.7) |
| E. Seed robustness | Regenerate the full network with seeds 1–20 | Network reduction mean **32.7% ± 4.8** (95% range 27.1–41.7%). Worst case mean 6.7% ± 6.9. Seed 42 is the most conservative draw. Plant ordering by mean reduction follows maturity exactly (Pune 20.5% → Bengaluru 48.2%). Pune is reportable in 15% of seeds, Coimbatore in 90% |
| F. Attribution residual | Control-attributable total vs Σ per-control credit | Residual 0.0 at all six plants (linear model, §9.5). Corrects Review 1 |

### 15.3 Intervention experiment: one-week verification sprint

**Intervention.** No new controls. All 75 open data-quality issues are resolved through `POST /resolve` as the Corporate Admin: 29 missing evidence or telemetry, 23 stale evidence, 14 criticality conflicts, 6 regression reviews and 3 feed outages.

| Plant | Issues fixed | Measured before → after | Band width before → after (pts) | Narrowing | Reportable before → after |
|---|---|---|---|---|---|
| Bengaluru | 7 | 4.4 → 2.4 | 43.8 → 24.2 | 45% | Yes → Yes |
| Chennai | 16 | 6.8 → 4.5 | 66.3 → 17.7 | 73% | No → **Yes** |
| Coimbatore | 9 | 9.0 → 8.6 | 20.6 → 16.5 | 20% | Yes → Yes |
| Hyderabad | 13 | 8.0 → 5.0 | 89.7 → 55.0 | 39% | No → **Yes** |
| Mumbai | 11 | 6.3 → 5.7 | 54.8 → 44.6 | 19% | Yes → Yes |
| Pune | 19 | 8.4 → 4.7 | 83.3 → 34.7 | 58% | No → **Yes** |

**Result:** reportable plants went from **3 to 6**, with a median band narrowing of **42%**. **Caveat:** every check was recorded as passing, so this is an optimistic bound. Self-attested fixes raise the point and best case but, by design, not the worst case.

### 15.4 Edge and failure cases, stress-tested (Bengaluru, the healthiest plant)

| Case | Measured [best–worst] | Change since baseline | Reportable |
|---|---|---|---|
| Reference | 4.45 [1.94–6.81] | −60.2% | Yes |
| E1: evidence blackout (all evidence lost) | 6.52 [4.98–8.06] | −45.9% (exposure change only) | Yes |
| E2: E1 + all feeds stale for 30 days | 6.52 [4.98–9.79] | −45.9% | Yes (worst case widened) |
| E3: E2 + every asset unmonitored and conflicted | 22.45 [8.98–35.91] | 0.0% | **No** |

In all three cases the outputs stay bounded and honest. Lost evidence removes control credit. Stale feeds widen only the worst case. Total blindness raises risk and uncertainty instead of reading as "no data, no risk".

---

## 16. Stakeholder validation

- **Round 1 (Phase 1):** a structured walkthrough as CISO, Plant Manager, OT Engineer, External Auditor and Corp Admin. It produced 6 findings: 2 validated as-is, 2 fixed in Phase 1, and 2 open. **Both open items are now closed** (§4, R5–R6).
- **Round 2 (final phase, not yet conducted):** a session with real plant-manager and engineer participants on the v1.1 build, using a scripted task list (read the headline, judge reportability, drill into an unverified control, resolve a feed outage). It will measure task success and self-reported trust. No Round 2 results are claimed in this report.

---

## 17. Implementation status

### 17.1 Completed (verifiable in the repository)
Full-stack application · 16 REST endpoints · JWT + bcrypt authentication · server-side RBAC and redaction for 5 roles, 9 personas, 6 plants + corporate org and an external auditor org · seeded generator with 7 injected failure classes and `--seed` · scoring engine v1.1 (asset risk, rollup, evidence-time-awareness, error bands, control-attributable reduction, per-control attribution, target, feed health, failed-verification handling, method versioning) · resolve workflow with write-back for 5 issue types · India facility map · trend, zone, leaderboard and drill-down views · degraded-data banner and feed-freshness panel · role-scope card · reportability rule · 92 automated tests · executed 11-section experiment notebook · failure-mode analysis (8 states, defects A–E) · technical documentation · field-workflow map · PRD.

### 17.2 Current capabilities (what a user can do today)
Switch between nine personas and see each role's server-enforced view. Read the plain-language business answer with its confidence range and reportability. Drill from a plant to a control or asset to raw evidence, CVEs and incidents (role permitting). See exactly which source feeds are stale. As an engineer, resolve issues and watch every role's numbers update. As Corporate Admin, compare all plants.

### 17.3 Remaining for final submission (the last 25%)
1. **Stakeholder validation Round 2** with real participants (§16).
2. **Pass/fail choice in the resolve UI.** The engine already handles `result = "fail"`. The API and UI need to let an engineer record a failed verification.
3. **Final presentation deck**, built from this report's verified results.
4. **Field-workflow map refresh** to include the feed-outage loop.
5. **Demo packaging**: a single-command start script and a recorded walkthrough.

### 17.4 Future enhancements (beyond project scope)
Calibration of judgement weights against real incident history · Shapley attribution, if the model becomes non-linear · append-only control-status history (replacing linear rollout interpolation) · real connectors (scanner/CMDB/EDR/ticketing APIs) in place of synthetic feeds · PostgreSQL and multi-process deployment · production authentication (SSO/MFA, lockout, refresh rotation, HttpOnly cookies, restricted CORS) · an OT vendor/contractor partner role scoped to specific zones.

---

## 18. Limitations

- The data is synthetic. Results show that the method behaves correctly, not real-world risk levels.
- The weights are judgement calls. §15.2-D quantifies the two that matter most (unverified-control credit, unmonitored exposure).
- Per-plant results vary widely across seeds (SD 14–19 pts). Only the network-level conclusion is stable from a single dataset.
- The intervention assumes every verification passes, so it is an upper bound.
- SQLite with a single process is not suitable for concurrent production load.

---

## 19. How to reproduce

```bash
git clone https://github.com/Kaveeshwar18/controlforge.git && cd controlforge
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements-dev.txt
cd backend && python ../data-gen/generate_data.py            # seed 42 by default
python -m pytest                                              # 92 tests
uvicorn app.main:app --port 8000                              # API
cd ../frontend && npm install && npm run dev                  # UI at http://localhost:5173
cd ../notebooks && jupyter nbconvert --to notebook --execute --inplace experiment.ipynb
```

Figures depend on the run date, because the window is today − 180 days with dates generated relative to today. Relative results reproduce exactly for a given seed.

## 20. Deliverables index

| Deliverable | Location |
|---|---|
| PRD and implementation plan | `PRD_Control_Effectiveness_Dashboard.md` |
| Field-workflow map | `docs/field-workflow-map.md` |
| Data-generation script | `data-gen/generate_data.py`, `data-gen/plants.json` |
| Functional application | `backend/app/`, `frontend/src/` |
| Automated tests | `backend/tests/` |
| Experiment notebook and charts | `notebooks/experiment.ipynb`, `notebooks/*.png` |
| Failure-mode analysis | `docs/failure-mode-analysis.md` |
| User feedback summary | `docs/user-feedback-summary.md` |
| Technical documentation | `docs/technical-documentation.md` |
| Presentation (draft) | `docs/presentation.md` |
| Review 1 report | `docs/review-1-report.md` |
| **This report** | `docs/review-2-report.md` |
