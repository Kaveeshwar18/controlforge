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
  evidence. Also computed at `confidence_bias="low"` (worst case: heavily
  discount stale/self-attested evidence) and `"high"` (best case: assume any
  evidence that exists is fully trustworthy) to produce the **error band**.
  These bias overrides only ever apply to the current-day measurement — a
  baseline/target date isn't an audit-trust question, it's a factual or
  hypothetical reconstruction.
- **Per-control attribution**: for each completed control, recompute
  `business_risk` with that one control's effect counterfactually removed
  (`_business_risk_excluding_control`); the delta is that control's marginal
  contribution. The sum of all marginal contributions will **not** generally
  equal `baseline − measured` when controls have overlapping coverage — the
  difference is reported explicitly as `residual` ("interaction effects, not
  cleanly assignable to one control") rather than silently forced to
  reconcile. A large residual is a real signal of highly redundant/overlapping
  control coverage, not a bug.

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
