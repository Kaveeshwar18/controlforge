# Field-Workflow Map

How each role actually moves through the system, end to end — from raw
telemetry to a decision, and back around to remediation.

## 1. Data sources → the dashboard

```
Vulnerability scanner ──┐
CMDB / asset inventory ─┼──▶ data-gen/ETL layer ──▶ core data model ──▶ scoring engine ──▶ API ──▶ dashboard
EDR / SIEM telemetry ───┤        (normalizes              (assets, controls,      (risk +
Ticketing / GRC tool ───┘      heterogeneous            evidence, vulns,      attribution,
                                source schemas)          incidents)            confidence-weighted)
```
In production, the box labeled "ETL layer" is where real scanner exports,
CMDB exports, and ticketing exports would be normalized into the schema in
`backend/app/models.py`. The prototype's `data-gen/generate_data.py` stands
in for that pipeline, including deliberately injecting the same kinds of
disagreement real source systems produce (see technical-documentation.md
section 2).

## 2. Per-role workflow

### OT Security Engineer (Priya Nair / Dev Patel)
1. Opens the dashboard scoped to their own plant.
2. Checks the **data-quality & failure-state inbox** first, not the risk
   score — this is the actionable queue.
3. For each open issue, resolves it *by doing the underlying work* (the
   "Resolve" action represents completing a re-verification scan, connecting
   a telemetry feed, or reconciling a criticality conflict — see
   `dataquality.py`), not just dismissing a ticket.
4. Sees the risk score, control leaderboard, and every other role's view of
   their plant update immediately as a result — closing the loop between
   "I did the work" and "the business risk number reflects it."
5. Drills into a specific asset or control to see the raw CVE/evidence data
   behind a risk figure when investigating.

### CISO (Sarah Chen / Tom Becker)
1. Opens the dashboard scoped to their plant.
2. Reads the top-line baseline → target → measured cards, with the
   confidence band as the first thing checked, not the point estimate alone.
3. Uses the control-effectiveness leaderboard to defend budget/headcount
   asks with attributed, not asserted, risk reduction per control.
4. Drills into a control or asset when a number looks off, or ahead of an
   audit, to check what's actually backing it.
5. Cannot resolve data-quality issues themselves — that's a deliberate
   separation of duties; the CISO consumes the number, the engineer produces
   the evidence behind it.

### Plant Manager (Miguel Alvarez / Lena Ortiz)
1. Opens the dashboard scoped to their plant — sees the same top-line cards
   as the CISO, but in business framing ("business risk reduced" rather than
   "risk reduction attributed to controls").
2. Cannot see the raw technical control leaderboard confidence notes or
   CVE-level drill-down — asset drill-down shows a **control coverage
   summary** (counts) and **open exposure count**, not CVE IDs.
3. Uses this to answer "is the OT investment we approved actually reducing
   risk to the line" without needing to interpret CVSS scores.

### External Auditor (James Cole)
1. Opens the dashboard scoped to whichever plant(s) they're engaged to
   review — the org selector shows *only* those, nothing else exists from
   their point of view.
2. Every asset name is redacted to `Type-Zone-UnitN` — they can assess
   posture and evidence quality without seeing internal plant topology.
3. Control drill-down shows an **evidence package statement**
   ("Independently verified" / "Not independently verified" / "No
   verification evidence on file") instead of the raw evidence log — enough
   to write an audit finding, not enough to see internal monitoring
   configuration.
4. Cannot resolve issues or see the cross-org comparison — read-only,
   single-engagement scope only.

### Corporate Admin / MSSP (Amara Diallo)
1. Opens the dashboard scoped to the corporate wrapper org, or switches to
   any individual plant with full drill-down access (same depth as that
   plant's own CISO).
2. Uses **Compare across organizations** — a view no other role can reach —
   to rank plants by measured risk and % of achievable target reached, for
   portfolio-level budget and attention allocation.
3. Can resolve data-quality issues in any plant, standing in for corporate
   security functions with cross-site authority.

## 3. The loop that matters

```
Engineer finds/fixes a gap → resolves the issue → evidence/criticality/telemetry
record updates → EVERY role's next read reflects it, correctly scoped and
framed for them → CISO/Plant Manager/Auditor see the change without the
engineer needing to tell them
```
This loop — one action, immediately visible everywhere it should be, in the
form each role needs — is the workflow the whole prototype exists to prove
out, not the individual screens.
