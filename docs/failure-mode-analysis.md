# Failure-Mode Analysis

The PRD requires failure-state design, not just a happy path. This document
lists every failure state built into the prototype, where it's seeded, how
it's detected, and exactly how the UI treats it differently from a "healthy"
reading. Six states were required as a minimum. This build has eight designed
states (§1–8) plus the defects found and fixed during testing (§A–E). Every
designed state is covered by an automated test in `backend/tests/`.

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

## 8. Source-feed outage (added in Phase 2)

**What it is:** An upstream integration (vulnerability scanner, CMDB, EDR
collector, incident ticketing) stops syncing or was never connected. Every
figure derived from that feed is silently frozen at its last sync.

**Where it's seeded:** `data-gen/plants.json` → `feed_faults` per plant, applied
by `generate_data.py::seed_feeds`. Pune: scanner stale (218 h, 24 h expected).
Hyderabad: ticketing never connected. Mumbai: CMDB stale (40 days). Chennai:
EDR delayed (aging, not stale).

**Detection:** `scoring.feed_state()` classifies each `DataFeed` as
fresh (≤1.5× expected interval) / aging (≤4×) / stale / missing (`last_sync IS NULL`).

**Effect on the math:** the point estimate is unchanged, because we don't
know what the feed would have reported. The **worst case** is widened:
scanner stale/missing → exposure ×1.25; ticketing stale/missing → +0.15
incident multiplier per asset. CMDB/EDR outages are flagged but don't move the
score (documented as such in the UI).

**UI treatment:** an amber degraded-data banner above the headline, naming the
feed and its consequence in plain language; a "Data freshness" panel listing
every feed with last-sync age and state badge; a `feed_outage` issue in the
data-quality inbox. An engineer's resolve sets `last_sync = now()` and the
banner and worst-case widening disappear for every role. External auditors
and plant managers see the state but not the internal error text
(`risk.py::_feeds_for`).

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


**C. Best/worst case reported the wrong way round in the experiment
(found in Phase 2 code review of the notebook).** `AttributionSummary` named
its fields `reduction_low` / `reduction_high`, where *low* was actually the
**larger** reduction (it came from the "low risk" best case). The v1
notebook's `worst_case_reduction_pct` column therefore printed the
**best** case under a worst-case label: the most optimistic number, labelled
as the most cautious one. The same notebook's "sensitivity analysis" only
counted self-attested controls and never re-scored anything. Fixed by
renaming the fields to `reduction_best_case` / `reduction_worst_case`, adding
regression test `test_best_case_reduction_is_never_smaller_than_worst_case`,
and replacing the sensitivity section with a real re-score (notebook §5).

**D. Four scoring-method flaws exposed by the v2 experiment → method v1.1.**
The first run of the rebuilt notebook produced results that contradicted
the design intent. Each was fixed and versioned (`METHOD_VERSION = "v1.1"`):

| # | Symptom in the experiment | Root cause | Fix |
|---|---|---|---|
| D1 | Band width uncorrelated with evidence quality (r = −0.05), and a verification sprint *widened* the band | Worst case capped **all** evidence at 0.5 confidence, including fresh independent verification, so more good controls meant a wider band | Worst case keeps full confidence for verified evidence and gives 0 to self-attested/stale/missing |
| D2 | At Bengaluru, 48.8 of the 60.2-point "reduction attributed to controls" came from vulnerability churn | The headline was total change since baseline, labelled as control effect | New `controls_reduction_pct`: today's risk vs. a same-day counterfactual with completed controls removed, scored under the same bias |
| D3 | A plant with every asset unmonitored got a zero-width band (most "certain" when it knew least) | Unmonitored exposure was a single constant in all three cases | Bounds use `UNMONITORED_EXPOSURE_BEST/WORST` = 1.0 / 4.0 around the 2.5 point |
| D4 | A failed verification would still earn credit | `latest_evidence_state` ignored `Evidence.result` | `result == "fail"` → confidence 0, `failed = True`, attribution note "Failed its most recent verification" |

A further correction came out of this: the large negative "interaction
residual" that Review 1 (and stakeholder finding #5) explained as
overlapping controls was really vulnerability churn, because it was taken
against total change. Against the control-attributable total, the residual
is 0 at every plant: risk is linear in each control's credit (asset risk
uses *average* effectiveness), so marginal attribution is exactly additive.

**E. False "no plants assigned" error on every first load.** The
dashboard showed *"This account has no plants assigned yet"* for a moment
while the org list was still loading. That's a failure state shown when no
failure existed, which trains users to ignore real errors. Fixed with an
explicit `orgsLoaded` state in `App.jsx`: a loading message shows until the
list arrives, and the error only shows for a genuinely empty list.
