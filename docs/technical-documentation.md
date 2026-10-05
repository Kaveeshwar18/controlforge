# Technical Documentation — Control-Effectiveness Dashboard

## 1. Architecture

```
data-gen/generate_data.py   Synthetic multi-org dataset (assets, controls, evidence,
                             vulnerabilities, incidents, data-quality issues, risk
                             snapshots) written to backend/coe_dashboard.sqlite3

backend/app/
  models.py        SQLAlchemy ORM -- the data model (see section 2)
  scoring.py        Risk scoring & attribution engine (see section 3) -- pure
                     functions over the DB, no FastAPI/HTTP dependency, so it's
                     independently testable and reusable from the notebook
  rbac.py            Role/org access resolution + redaction helpers
  routers/*.py      FastAPI endpoints -- thin wrappers that call scoring.py /
                     rbac.py and shape the JSON response per role

frontend/            React (Vite) SPA -- identity/org switcher, dashboard,
                     drill-down modals, data-quality inbox with resolve action

notebooks/experiment.ipynb   Baseline/target/measured/error experiment, run
                              directly against the same scoring engine
```

Authentication is real: accounts live in the `accounts` table with
bcrypt-hashed passwords, and a signed JWT (`Authorization: Bearer …`)
establishes identity, which is then resolved to a persona in `users` /
`user_org_access` for authorisation. A caller cannot ask to be treated as a
different persona — the earlier `X-User-Id` header approach was removed
precisely because it allowed exactly that. See section 4a.

## 2. Data model

| Entity | Purpose | Key fields |
|---|---|---|
| `Organization` | Plant or corporate wrapper | `org_type`, `parent_id` |
| `User` / `UserOrgAccess` | Simulated identity + org scoping | `role`, `redacted` |
| `Asset` | OT/IT/DMZ asset | `criticality_scanner`, `criticality_cmdb` (two source systems, may conflict), `criticality_resolved`, `business_impact_weight`, `has_telemetry` |
| `Control` | A security control instance, scoped to one asset or a whole zone | `status` (planned/in_progress/completed), `rollout_percentage`, `planned_date`, `completion_date` |
| `Evidence` | A verification event for a control | `timestamp`, `source` (automated_scan / third_party_audit / manual_attestation), `result` |
| `Vulnerability` | Per-asset finding | `cvss`, `discovered_date`, `status`, `resolved_date` |
| `Incident` | Per-asset security event | `severity`, `detected_date`, `resolved_date`, `related_control_id` |
| `DataQualityIssue` | A tracked failure state (conflict / missing_feed / stale_evidence / regression) | `status`, `resolved_by` |
| `RiskSnapshot` | Precomputed historical trend point | `snapshot_type` (historical/target), `score_normalized` |

**Why status and evidence are separate axes:** `Control.status` is what the
team *reports*; `Evidence` is independent proof. A control can be
`status=completed` with zero evidence rows (failure state: nobody ever
verified it) — this is deliberate, not an oversight, and is exactly the
gap the dashboard is built to surface.

## 3. Scoring & attribution engine (`backend/app/scoring.py`)

### 3.1 Asset risk
```
asset_risk = criticality × exposure_factor × (1 − control_effectiveness) × incident_multiplier
```
- `criticality` (1–5): resolved value, or the *more conservative* (higher) of
  the two conflicting source values until a human resolves the conflict —
  risk is never silently understated by an unresolved data-quality issue.
- `exposure_factor`: CVSS-weighted sum of open vulnerabilities, capped at 5,
  with an age multiplier (1.0 / 1.3 / 1.6× for <30 / 30–90 / >90 days open)
  so long-unpatched exposure counts for more.
- `control_effectiveness` (0–1): average, across applicable controls, of each
  control's confidence-weighted effectiveness (section 3.2).
- `incident_multiplier`: `1 + 0.15 × (weighted recent-incident count)` over a
  90-day lookback (unresolved incidents count double a resolved one).

An asset with `has_telemetry = False` (no monitoring feed at all) does **not**
default to low risk — it's scored with a fixed elevated exposure baseline and
`control_effectiveness = 0`, because absence of visibility is itself
risk-bearing (see failure states, section 4 of the failure-mode analysis).

### 3.2 Control effectiveness and evidence-time-awareness
`control_effectiveness(control, evidence, as_of)` is evaluated **as evidence
was known at `as_of`**, not as it stands today — `evidence` is resolved via
`latest_evidence_state(..., as_of)`, which only considers evidence rows with
`timestamp <= as_of`. This is what makes baseline/historical reconstruction
honest: a control isn't credited until proof of it existed at that point in
time, not merely because its DB status field today says "completed".

- `planned` → 0 effectiveness.
- `in_progress` → `0.7 × rollout_fraction`. We don't store historical
  rollout %, so for a past `as_of` we linearly interpolate rollout from 0% at
  `planned_date` to the current rollout% today (`historical_rollout_percentage`)
  — a documented simplification rather than silently applying today's
  progress retroactively to the baseline.
- `completed` → 0 until `completion_date`, then `1.0` if verified (fresh/aging
  evidence from `automated_scan` or `third_party_audit`) or `0.7 × confidence`
  otherwise. A completed control with **zero** evidence rows gets **zero**
  credit, full stop — that's failure state #1, and it's enforced in the math,
  not just flagged in the UI.

### 3.3 Business risk rollup
```
business_risk(org, as_of) = Σ_assets  asset_risk(asset, as_of) × business_impact_weight(asset)
```
Normalized to a 0–100 index by dividing by a theoretical worst-case reference
(`max_reference_score`: every asset at max criticality/exposure/incident
multiplier and zero control effectiveness).

### 3.4 Baseline / Target / Measured / Error (`compute_attribution`)
- **Baseline** = `business_risk(org, today − 180d)`.
- **Target** = `target_business_risk(org, today)`: every control *currently
  planned, in-progress, or completed* for the org assumed to reach verified
  status, capped at `TARGET_MAX_EFFECTIVENESS = 0.9` — even a fully executed
  plan doesn't drive risk to literal zero (undetected/zero-day exposure,
  human error), so the ceiling stays credible instead of implying a perfect
  security program is achievable.
- **Measured** = `business_risk(org, today)`, confidence-weighted by real
  evidence. Also computed at `confidence_bias="low"` and `"high"` to produce
  the **error band** (method v1.1):

  | Input | Point | Best case (`high`) | Worst case (`low`) |
  |---|---|---|---|
  | Verified evidence (automated scan / audit, not stale) | table confidence | 1.0 | table confidence (kept) |
  | Self-attested evidence | 0.7 × table confidence | 0.7 × 1.0 | 0 |
  | Stale or missing evidence | discounted / 0 | 1.0 if any passing record, else 0 | 0 |
  | Failed most recent check (`result = "fail"`) | 0 | 0 | 0 |
  | Unmonitored asset exposure | 2.5 | 1.0 | 4.0 |
  | Scanner feed stale/missing | — | — | exposure × 1.25 |
  | Ticketing feed stale/missing | — | — | incident multiplier + 0.15 |
  These bias overrides only ever apply to the current-day measurement — a
  baseline/target date isn't an audit-trust question, it's a factual or
  hypothetical reconstruction.
- **Control-attributable reduction** (v1.1, the brief's headline metric):
  `controls_reduction_pct = (R_without − R_today) / R_without`, where
  `R_without = business_risk(today, excluded_control_ids = all completed)`.
  Both sides are scored on the same day under the same bias, so vulnerability
  churn and feed adjustments cancel out. The total change since baseline
  (`reduction_pct`) is still reported, but as a separate figure.
- **Per-control attribution**: for each completed control, recompute
  `business_risk` with that one control excluded. The delta is its marginal
  contribution. Because asset risk uses the *average* effectiveness, risk is
  linear in each control's credit, so the marginal contributions add up
  exactly to the control-attributable total (`residual ≈ 0`, verified in the
  notebook §8). In v1.0 the residual was taken against total change and so
  absorbed vulnerability churn. It was wrongly described as an overlap
  "interaction effect" (corrected, failure-mode analysis §D). The residual
  check is kept as a guard in case the model becomes non-linear.
- **Reportable** = `reduction_worst_case > 0`. This is the decision rule for
  whether a plant's improvement can be quoted to the board.

### 3.5 Source-feed health (`feed_state`, `feed_health`)
Each plant has four `DataFeed` rows (`vuln_scanner`, `cmdb`, `edr_telemetry`,
`ticketing`) with `expected_interval_hours` and `last_sync`. State: fresh
≤1.5× interval, aging ≤4×, stale beyond that, missing if `last_sync` is
NULL. Stale/missing scanner or ticketing feeds widen the worst case only
(table above). `GET /orgs/{id}/feeds` and the `feed_health` block of
`risk-summary` both pass through `_feeds_for()`, which strips `last_error`
and internal system names for roles without technical drill-down.

## 4. RBAC & redaction (`backend/app/rbac.py`)

| Role | Cross-org | Technical drill-down | Raw asset names | Can resolve issues |
|---|---|---|---|---|
| CISO | No | Yes | Yes | No |
| Plant Manager | No | No (business summary only) | Yes | No |
| OT Engineer | No | Yes | Yes | Yes |
| External Auditor | No | No (evidence-package statement only) | No (redacted `Type-Zone-UnitN`) | No |
| Corp Admin | Yes | Yes | Yes | Yes |

Enforcement is server-side in every router (`require_org_access`,
`is_redacted`), not just hidden in the UI — a request for an org outside the
caller's `UserOrgAccess` rows gets a `403` with an explicit reason, never a
silently empty or partial result.

**Asset IDs stay real even in redacted views** — only `display_name` is
redacted. The ID is an opaque lookup token the UI never shows the user;
redacting it too would break drill-down navigation for no privacy benefit
(this was a real bug found during testing — see failure-mode analysis).

## 4a. Authentication

| Concern | How it's handled |
|---|---|
| Password storage | bcrypt (`$2b$12$…`); never stored, logged or returned |
| Session | JWT, 12h TTL, `Authorization: Bearer` header |
| Signing key | `CONTROLFORGE_SECRET` env var; falls back to a generated local `.dev-secret` file so dev reloads don't sign everyone out |
| Failed login | Deliberately vague ("invalid username or password") so responses can't enumerate accounts |
| Self-registration | Creates an account with `PLANT_MANAGER` on the demo plant — a prototype provisioning default; real onboarding would be admin-driven |

Identity → authorisation is a one-way resolution: the token names an account,
the account maps to exactly one persona, and that persona's role and org
grants decide everything. There is no client-controllable path into that.

## 4b. API reference

| Method & path | Purpose | Role restrictions |
|---|---|---|
| `POST /api/auth/signup`, `POST /api/auth/login`, `GET /api/auth/me` | Account creation, sign-in (JWT), session check | public / any |
| `GET /api/me` | Role + capability flags | any |
| `GET /api/orgs` | Orgs the caller may see, with per-plant map metrics | scoped |
| `GET /api/orgs/{id}/risk-summary` | Baseline/target/measured, bands, control-attributable cut, reportable flag, freshness overview, feed health | scoped |
| `GET /api/orgs/{id}/risk-trend` | Historical snapshots + live today + target | scoped |
| `GET /api/orgs/{id}/zones` | Risk index by Purdue zone (IT/OT/DMZ) | scoped |
| `GET /api/orgs/{id}/controls` | Control leaderboard with per-control credit range | scoped |
| `GET /api/orgs/{id}/controls/{cid}` | Control drill-down: evidence log, or evidence statement (non-technical roles) | scoped + redacted |
| `GET /api/orgs/{id}/assets`, `/assets/{aid}` | Top-25 risk assets; asset drill-down (CVEs/incidents only for technical roles) | scoped + redacted |
| `GET /api/orgs/{id}/data-quality` | Data-quality inbox | scoped |
| `POST /api/orgs/{id}/data-quality/{iid}/resolve` | Resolve an issue with write-back to the scored record | OT Engineer, Corp Admin |
| `GET /api/orgs/{id}/feeds` | Source-feed sync status | scoped + redacted |
| `GET /api/compare` | Cross-plant comparison | Corp Admin |

## 4c. Testing (`backend/tests`, 92 tests, `python -m pytest`)
- `test_scoring.py`: hand-computed unit scenarios on an in-memory database
  for every failure rule (freshness thresholds, zero credit without evidence,
  stale discount, prorated rollout, evidence-time-awareness, unmonitored
  assets, criticality conflict, vulnerability ageing, incidents, feed
  thresholds and worst-case widening, failed verification, v1.1 bounds).
  Also whole-engine invariants on the seeded dataset (band ordering, target ≤
  measured, unverified controls credited zero, best ≥ point ≥ worst).
- `test_api.py`: HTTP tests with real signed tokens covering missing or
  tampered tokens, non-enumerating login errors, org scoping on every org
  endpoint, auditor redaction (names, evidence log, feed errors), plant-manager
  summary-only drill-down, admin-only compare, resolve permissions, and
  resolve write-back changing other roles' views (conflict cleared, feed
  restored, worst case narrowed, double-resolve rejected).

## 5. Known limitations
- SQLite, single-process — fine for a prototype, not for concurrent multi-user
  production load.
- Auth gaps that a real deployment needs: rate limiting / lockout on repeated
  failed logins, password reset, MFA, refresh-token rotation, and HTTPS-only
  cookie storage rather than `localStorage`.
- Historical rollout-percentage and in-progress-control confidence are linear
  approximations (documented in 3.2) because we don't store a full history of
  every field — a production system would append-log control status changes
  instead of overwriting them.
