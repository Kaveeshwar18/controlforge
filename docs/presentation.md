# Control-Effectiveness Dashboard
### Turning technical security findings into business risk — a working prototype
Manufacturing plant, IT/OT converged network

---

## The problem
Management cannot see whether security controls are reducing **actual
business risk**. Dashboards show counts ("142 open vulnerabilities"). Nobody
can answer: *is the money and effort we're spending on security measurably
working?*

---

## What we built
A working prototype — not a mockup — that:
- Computes a **business risk score** per plant, weighted by asset criticality
  and business impact (downtime cost, safety classification)
- Reports **baseline → target → measured** risk reduction, attributed to
  specific completed controls, **with an honest error range**
- Shows a different, role-appropriate view to CISO, Plant Manager, OT
  Engineer, External Auditor, and Corporate Admin — same underlying data
- Treats missing/stale/conflicting data as a first-class UI state, never
  silently hidden behind a clean-looking number

---

## The headline number, done honestly
```
Baseline risk (180 days ago):        9.4
Measured risk (today):               9.0    [confidence band: 6.5 – 10.5]
Target (if current plan finishes):   1.2
Reduction attributed to controls:    4.5%    (5.1% of achievable target)
```
The band matters more than the point estimate: if the least-trusted evidence
turns out to be wrong, this plant's "risk reduction" could actually be a
regression. **That's not a bug in the model — that's the model doing its job.**

---

## Role-based views, same data
| Role | Sees |
|---|---|
| CISO | Full technical drill-down, confidence bands, control leaderboard |
| Plant Manager | Business-risk framing, control coverage summary, no CVE lists |
| OT Engineer | Full drill-down + can resolve data-quality issues |
| External Auditor | Redacted asset names, evidence-verification statements only |
| Corp/MSSP Admin | Cross-plant comparison, full access everywhere |

A Plant Manager cannot even see that another plant exists. An Auditor sees
`PLC-OT-Unit2`, never the real hostname.

---

## Failure states are designed in, not bolted on
- Control marked "done" with **zero verification evidence** → excluded from
  risk credit, not just flagged
- Evidence that's gone stale → confidence downgraded, wide error band
- Two source systems disagreeing on asset criticality → scored conservatively
  until a human resolves it, never silently picked
- OT assets with no monitoring feed at all → treated as **elevated** risk, not
  defaulted to "fine because we have no data saying otherwise"
- A previously-verified control's asset gets a new incident → flagged for
  re-review, historical credit doesn't quietly stay unquestioned

---

## What we validated with stakeholders
Walked through the live app as each persona. Two real bugs were caught this
way — not in code review, in actual use:
1. Redacted views broke drill-down navigation for auditors (fixed)
2. Rapid role-switching had a race condition that could silently show the
   wrong plant's risk number (fixed — this is the dangerous kind of bug for
   a risk dashboard: it fails quietly and confidently)

---

## What this doesn't solve (and shouldn't pretend to)
- Doesn't replace the scanner, SIEM, or GRC tool — it's the translation layer
  on top
- A control marked "verified" is only as trustworthy as the evidence behind
  it — self-attestation can still be gamed; the dashboard's job is to make
  that visible (two-tier status + confidence weighting), not to make gaming
  impossible
- Formula weights (criticality scale, business impact) are judgment calls —
  versioned, documented, and configurable per org, not silently baked in

---

## Where this goes next
- Plain-language explainer for the interaction-effect residual on the leaderboard
- Real source-system ETL in place of the synthetic data generator
- Production auth in front of the same RBAC model (the model doesn't change,
  only how identity gets resolved)

---

## Try it
- Backend: `uvicorn backend.app.main:app --reload`
- Frontend: `npm run dev` in `frontend/`
- Data: `python data-gen/generate_data.py`
- Experiment: `notebooks/experiment.ipynb`
