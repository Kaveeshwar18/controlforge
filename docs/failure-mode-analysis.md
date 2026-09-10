# Failure-Mode Analysis

The PRD requires failure-state design, not just a happy path. This document
lists every failure state built into the prototype, where it's seeded, how
it's detected, and exactly how the UI treats it differently from a "healthy"
reading. Six states were required as a minimum; this build has six, plus two
found and fixed during testing (section 3).

## 1. Missing telemetry / unverified control

**What it is:** A control marked `status=completed` in the tracking system
has zero `Evidence` rows — nobody ever independently verified it was actually
done.

**Where it's seeded:** `data-gen/generate_data.py::seed_controls_and_evidence`,
`missing_evidence_quota` (3 per org), chosen at random among completed
controls.

**Detection:** `scoring.latest_evidence_state()` returns
`has_evidence=False, freshness="missing"`. `scoring.control_effectiveness()`
forces effectiveness to **zero** for this case — it is excluded from risk
credit in the math, not just flagged cosmetically.

**UI treatment:**
- Control leaderboard: `risk_reduction_attributed = 0` with note *"No
  verification evidence on file — excluded from risk credit, shown as zero."*
- Data-quality inbox: a `missing_feed` issue naming the specific control.
- Asset drill-down: the control shows a "No evidence" freshness badge.

## 2. Stale evidence

**What it is:** Evidence exists but is older than the freshness threshold
(>14 days for automated/audit sources, >45 days for manual attestation) —
verified once, never re-checked.

**Where it's seeded:** Same function, `stale_evidence_quota` (4 per org) —
these controls get an initial verification near their completion date but
**no** recent re-verification.

**Detection:** `freshness_state()` compares evidence age to source-specific
thresholds; confidence is downgraded (0.2–0.3) rather than zeroed, per
`CONFIDENCE_TABLE`.

**UI treatment:**
- "Stale" badge (red) wherever that control's evidence appears.
- Attributed reduction is still computed but with a wide confidence band and
  an explicit note: *"Evidence is stale... reduction credit heavily
  discounted."*
- Counted separately from "missing" in the freshness overview widget — a
  reviewer can tell "never verified" apart from "verified once, then
  neglected."

## 3. Conflicting source data

**What it is:** Two source systems (vulnerability scanner vs. CMDB) disagree
on an asset's criticality rating.

**Where it's seeded:** `seed_assets()` — 3 assets per org get
`criticality_scanner != criticality_cmdb`.

**Detection:** `scoring.resolved_criticality()` returns `None` when the two
values disagree and no one has resolved it.

**UI treatment:**
- The asset is scored using the **higher** (more conservative) of the two
  values until resolved — risk is never silently understated by an
  unresolved conflict.
- "Data conflict" flag on the asset row and in drill-down.
- A `conflict`-type data-quality issue, resolvable only by OT Engineer / Corp
  Admin. Resolving it writes `criticality_resolved` onto the asset (taking
  the conservative value) and the conflict flag disappears from every role's
  view on the next read.

## 4. Partial control rollout

**What it is:** A control is `in_progress` at some rollout percentage, not a
binary done/not-done state.

**Where it's seeded:** ~28% of per-asset controls in `seed_controls_and_evidence`.

**Detection/handling:** Risk credit is prorated
(`STATUS_WEIGHT["in_progress"] × rollout_fraction`), and for historical
`as_of` dates, rollout is linearly interpolated from 0% at `planned_date` to
today's actual percentage (`historical_rollout_percentage`) rather than
applying today's progress retroactively to the past.

**UI treatment:** Status badge shows "In progress" with the rollout
percentage inline in the asset drill-down control list, distinct from
"Completed."

## 5. Regression (previously-verified control, new incident)

**What it is:** An asset covered by a control that was verified now has a
new incident — the control's real-world effectiveness is in question even
though nothing in its own status/evidence record changed.

**Where it's seeded:** `seed_vulnerabilities_and_incidents()` deliberately
ties one incident's `related_control_id` to a previously-completed control.

**UI treatment:** A `regression`-type data-quality issue is created,
independent of the control's own evidence trail (which still looks "fine" in
isolation) — this is specifically designed so a regression can't be missed
just because the control's own paperwork looks clean. Resolving this issue
type closes the review record; it deliberately does **not** silently restore
the control's risk credit, since the incident itself is a fact that
happened.

## 6. Unmonitored asset (no telemetry at all)

**What it is:** An OT asset with no monitoring agent or feed — common for
legacy PLCs/HMIs that can't run modern agents.

**Where it's seeded:** `seed_assets()`, `has_telemetry=False` for 3 assets
per org.

**UI treatment:** `asset_risk()` does **not** default this to low risk — it
uses a fixed elevated exposure baseline and zero control credit, because
absence of visibility is itself risk-bearing (this reflects real OT security
guidance, e.g. IEC 62443's emphasis on asset visibility gaps). Flagged with a
"No telemetry" badge everywhere the asset appears, and rolled up into a
dedicated `unmonitored_assets` counter on the zone heatmap and risk-summary
freshness overview.

## 7. Permission/authorization failure

**What it is:** A role attempts an action outside its scope — e.g. a Plant
Manager requesting another plant's data, or the cross-org compare view.

**Detection/handling:** Enforced server-side in every router
(`rbac.require_org_access`, capability checks in `dataquality.py` and
`compare.py`) — never only in the UI.

**UI treatment:** An explicit `403` with a human-readable reason (e.g. *"Role
PLANT_MANAGER does not have access to organization 'mumbai'"*), rendered as a
distinct error banner — never a blank screen, a silent empty list, or a
generic failure message.

---

## Failure states found and fixed during testing (not pre-planned, discovered by exercising the UI)

These are included because a "failure-state design" document that only lists
the failure states the design *intended* isn't honest about the process —
these two were found by actually clicking through the app as different roles,
not by code review.

**A. Redacted asset ID broke drill-down.** The auditor-facing asset list
originally redacted `asset_id` itself (not just the display name) to a
synthetic `REDACTED-N` value. The frontend used that same field to fetch the
drill-down endpoint, which 404'd — auditors literally could not open any
asset detail. Fixed by keeping the real ID as an opaque lookup token (never
displayed) and redacting only `display_name`. This is the kind of failure
that's invisible in a code review of the scoring logic but immediately
obvious when you actually click through the workflow as the role it affects.

**B. Stale-response race condition on rapid role/org switching.** Switching
identity fires a new dashboard fetch before the previous one resolves; if an
earlier, slower request for org A resolved *after* a newer request for org B
had already updated the screen, org A's stale numbers would silently
overwrite org B's correct ones — a CISO who quickly checked two plants could
end up looking at the wrong plant's risk score with no indication anything
was wrong. Fixed with a request-token guard in `App.jsx` (`loadRequestId`)
that discards any response superseded by a newer request. This class of bug
is particularly dangerous for a risk dashboard specifically because it fails
silently and confidently — the number just looks normal, it's simply wrong.
