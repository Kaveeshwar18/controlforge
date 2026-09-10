# Stakeholder Validation Summary

A structured walkthrough of the working prototype, in character as the two
minimum personas the PRD calls for (Plant Manager, OT Security Engineer),
plus the CISO and External Auditor views since both were readily testable.
Each finding below came from actually operating the app end-to-end (see
`docs/failure-mode-analysis.md` section 3 for two bugs this same process
caught), not from reviewing a mockup.

> **Note:** this session was run against the earlier two-site US dataset
> (Riverside / Dover). The plant network has since moved to six Indian
> sites, so site names below are historical. The findings and the fixes
> they produced still stand — they were about behaviour, not data.

## Session format
Walked each persona through: log in as that role → read the top-line risk
cards → drill into an asset/control → (engineer only) resolve a data-quality
issue → observe how the change surfaces elsewhere. Feedback captured inline.

## Findings

### 1. "The confidence band changed my mind about what to say in the board meeting" — CISO persona
Seeing `measured_score: 9.0 [10.5–6.5]` instead of a bare `9.0` was flagged as
the single most useful design decision in the prototype. Direct quote (in
character): *"If I'd been shown just '4.5% reduction' I'd have said that in
the board meeting. Seeing the worst-case bound is actually a regression
changes what I'm willing to claim."* — **Validated, no change needed.**

### 2. "I don't want to see CVE numbers, and now I don't" — Plant Manager persona
The asset drill-down for `PLANT_MANAGER` correctly shows a control-coverage
summary and exposure count instead of CVE-level detail. Feedback: this is the
right altitude, but the *count* of "unverified/missing" controls needs a
one-line explanation inline — a plant manager reading "2 unverified" has no
way to know if that's normal or alarming without CISO context.
**Action item (open):** add a short static explainer line to the summary
card, e.g. "controls without independent verification — ask your CISO if
this is expected for in-progress work."

### 3. "Why does fixing one thing barely move the number?" — OT Engineer persona
After resolving a `stale_evidence` issue (which now genuinely re-verifies the
control per the fix described in failure-mode-analysis.md), the org-level
risk index moved by less than the displayed rounding (1 decimal place) could
show. Feedback: an engineer who just did real work wants to see *something*
move, even if the true org-wide effect is small.
**Action item (resolved during this build):** the resolve action was
originally cosmetic for `stale_evidence`/`missing_feed` issues (it only
closed the ticket, without writing new evidence) — fixed so resolving now
inserts a real evidence record and the score genuinely recomputes. The
*display* still rounds to one decimal at the org level; per-asset or
per-control drill-down shows the more granular change. This was flagged
clearly enough that no further UI change is planned for this round.

### 4. "I compared two plants and I'm not sure I was looking at the right one" — Corp Admin persona
While testing rapid role-switching, a stale API response from a previous org
selection briefly overwrote a newer one on screen with no visual indication.
**Action item (resolved during this build):** root-caused as an
out-of-order-response race condition and fixed with a request-token guard
(see failure-mode-analysis.md section 3B). Re-tested after the fix: rapid
switching between Riverside / Dover / corporate wrapper org now always shows
the org currently selected.

### 5. "The residual number on the leaderboard is bigger than I expected, and I don't know if that's bad" — CISO persona
The "residual (interaction effects, unattributed)" figure on the control
leaderboard was large and negative for the Riverside dataset, which reads as
confusing without context.
**Action item (open, documented rather than fixed):** this is a real,
expected property of marginal-contribution attribution when controls have
overlapping coverage (see technical-documentation.md section 3.4) — not a
bug. Recommendation for the next iteration: add a tooltip/expander
explaining *why* a large residual is not itself a red flag, since a plain
number with no context reads as an error to anyone not already familiar with
Shapley-style attribution.

### 6. "As an auditor I want to know evidence is real, and now I can" — External Auditor persona
The evidence-package statement ("Independently verified" /
"Not independently verified" / "No verification evidence on file") without a
raw evidence log was confirmed as the right level of disclosure — enough to
write a finding, not enough to see internal monitoring config.
**Validated, no change needed.**

## Summary of action items
| # | Item | Status |
|---|---|---|
| 1 | Confidence band on measured risk | Validated as-is |
| 2 | Plain-language explainer for "unverified controls" count on Plant Manager view | Open — next iteration |
| 3 | Resolve action must write real evidence, not just close the ticket | **Fixed this build** |
| 4 | Stale-response race condition on rapid role/org switching | **Fixed this build** |
| 5 | Explain the interaction-effect residual in-context | Open — next iteration |
| 6 | Auditor evidence-package disclosure level | Validated as-is |
