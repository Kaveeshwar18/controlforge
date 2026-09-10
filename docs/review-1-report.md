# Review 1 Report — ControlForge

**Project:** Control-effectiveness dashboard for a manufacturing plant connecting office IT with operational technology (OT) networks
**Batch:** IE28 · Sem 5 · COE Growth Project
**Phase:** Review 1 (35% completion checkpoint)

---

## 1. Problem being solved

Management at a manufacturing plant with converged IT/OT networks cannot see whether security controls are actually reducing business risk. Technical telemetry (patch status, vulnerability counts, incident tickets) exists, but nothing translates it into a number a plant manager or executive can act on, and nothing distinguishes a control that's genuinely verified from one that's merely marked "done" on paper.

**Deliverable:** a control-effectiveness dashboard that turns telemetry, asset criticality, vulnerabilities, incidents and remediation status into a business-risk score with an honest confidence range — plus role-based views, drill-down evidence, and explicit handling of missing/stale/conflicting data, built and evaluated as a real running system rather than a slide deck.

## 2. Status against the original deliverable list

| Deliverable | Status | Evidence |
|---|---|---|
| Field-workflow map | **Done** | `docs/field-workflow-map.md` |
| Data-generation script | **Done** | `data-gen/generate_data.py` + `data-gen/plants.json` — seeds 6 real plant sites (Chennai, Coimbatore, Bengaluru, Hyderabad, Pune, Mumbai), assets, controls, vulnerabilities, incidents, and deliberately injected data-quality failures |
| Core logic (risk scoring engine) | **Done** | `backend/app/scoring.py` — asset risk → business risk rollup → baseline/target/measured/error attribution, with per-control marginal-contribution attribution |
| Functional application | **Done** | FastAPI backend + React frontend, real SQLite-backed data, real authentication (bcrypt + JWT), real RBAC — not a mockup |
| User interaction | **Done** | Role-based dashboard views, drill-down modals (asset/control evidence), an interactive facility map, search/filter, a data-quality inbox with a working resolve action that recomputes the live score |
| Evaluation (experiment notebook) | **Done** | `notebooks/experiment.ipynb` — executed, with real baseline/target/measured/error output and a sensitivity analysis on evidence trust |
| Failure-state design | **Done** | `docs/failure-mode-analysis.md` — 6 designed failure states (missing evidence, stale evidence, conflicting source data, partial rollout, control regression, unmonitored assets) plus 2 real bugs found and fixed during hands-on testing |
| Technical documentation | **In progress** | `docs/technical-documentation.md` covers the data model, scoring engine and RBAC; the facility-map feature still needs its own section |
| User/stakeholder feedback summary | **In progress** | `docs/user-feedback-summary.md` exists from an earlier walkthrough; a fresh round against the current India-plant build is planned |
| Presentation | **Draft** | `docs/presentation.md` predates the facility map and the current sign-in flow and needs an update pass |

## 3. What's actually working right now

- **Risk scoring is real math, not placeholder numbers.** Every asset's risk score factors in criticality (with a conservative fallback when two source systems disagree), open-vulnerability exposure weighted by age, control effectiveness weighted by evidence confidence, and recent-incident history. Org-level risk rolls these up by business impact.
- **The headline metric — risk reduction attributed to completed controls — comes with an honest error band**, not a single confident-looking number. The band is derived from how much of the "completed" evidence is independently verified vs. self-attested vs. stale, so a program that looks good on paper but is thin on verification shows a visibly wider (and sometimes worse-case-negative) range.
- **Role-based access is enforced server-side**, not just hidden in the UI: a Plant Manager cannot even see that other plants exist; an External Auditor sees redacted asset names and an evidence-verification statement instead of raw CVE data; only specific roles can resolve data-quality issues.
- **Failure states are seeded into the data, not just described.** A control marked "completed" with zero verification evidence gets zero risk credit in the actual scoring math. An unmonitored OT asset is scored as elevated risk rather than defaulting to "fine," because absence of visibility is itself a risk signal.
- **The facility map is data-driven**, not hardcoded: plant names, coordinates, and org access all come from `data-gen/plants.json`; adding a seventh plant is a data change, not a code change.

## 4. What's next (remaining ~65%, roughly in order)

1. Finish technical documentation (facility-map section, current auth/entry-point description).
2. Run a fresh stakeholder walkthrough against the current India-plant build and update the feedback summary.
3. Update the presentation deck to reflect the facility map and current sign-in flow.
4. Harden remaining rough edges identified during testing (see `docs/failure-mode-analysis.md` §3 for the two already found and fixed).

## 5. Repository / how to run it

```bash
# backend
cd backend && pip install -r requirements.txt
python ../data-gen/generate_data.py
uvicorn app.main:app --reload --port 8000

# frontend
cd frontend && npm install && npm run dev
```

Repository link: _pending — see note below on repository setup._
