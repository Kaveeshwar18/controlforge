# ControlForge

A control-effectiveness dashboard for a manufacturing organization whose plants connect office IT to operational technology (OT) networks. It exists to answer one question management usually can't: **are our security controls actually reducing business risk, and how confident can we really be in that number?**

Built as a working full-stack application — real database, real scoring engine, real authentication and role-based access control — not a mockup or a slide deck.

---

## What it actually does

- **Turns technical telemetry into a business risk score.** Every asset's risk is computed from its criticality, open vulnerabilities (weighted by severity and how long they've been open), how effective its security controls are, and recent incident history. Asset scores roll up into a per-plant business risk number weighted by business impact.
- **Reports risk reduction with an honest confidence range, not a bare number.** The headline "risk reduction attributed to controls" metric comes with a best-case/worst-case band derived from how much of the underlying evidence is independently verified vs. self-attested vs. stale. A security program that looks good on paper but is thin on verification shows a visibly wide — sometimes worst-case-negative — range instead of a falsely confident single figure.
- **Attributes reduction to specific controls**, using a marginal-contribution method (remove one control, see how much the score changes), with the unattributed remainder (from overlapping control coverage) reported explicitly rather than hidden.
- **Enforces role-based access server-side**, not just in the UI. A Plant Manager can't see that other plants exist. An External Auditor sees redacted asset names and a verification *statement* instead of raw evidence logs. Only specific roles can resolve data-quality issues.
- **Treats data-quality problems as first-class**, not edge cases: a control marked "completed" with zero verification evidence gets **zero** risk credit in the actual math; an unmonitored OT asset is scored as elevated risk rather than defaulting to "fine because there's no data saying otherwise."
- **Maps six real plants across India** (Chennai, Coimbatore, Bengaluru, Hyderabad, Pune, Mumbai) on an interactive facility map — click a marker for that plant's risk/baseline/reduction/control-effectiveness/critical-assets/vulnerabilities/incidents, or open it to switch the whole dashboard to that plant.

## Architecture

```
backend/            FastAPI app
  app/models.py       SQLAlchemy data model (orgs, assets, controls, evidence,
                       vulnerabilities, incidents, data-quality issues, accounts)
  app/scoring.py       The risk scoring & attribution engine (pure functions,
                       independently testable, no HTTP dependency)
  app/auth.py          bcrypt password hashing + JWT session tokens
  app/rbac.py          Role/org access resolution + field redaction
  app/routers/*.py     API endpoints — thin wrappers around scoring.py/rbac.py

data-gen/
  plants.json          Single source of truth for the plant network: site
                       names, coordinates, size, and who can see them
  generate_data.py     Seeds the database from plants.json — synthetic assets,
                       controls, evidence, vulnerabilities, incidents, and
                       deliberately injected data-quality failures

frontend/            React (Vite) SPA
  src/App.jsx          App shell, session bootstrap, dashboard data loading
  src/components/*     Dashboard panels, facility map, drill-down modals

notebooks/
  experiment.ipynb     Executed baseline/target/measured/error experiment
                       with a sensitivity analysis on evidence trust

docs/                Field-workflow map, technical documentation,
                     failure-mode analysis, stakeholder feedback, presentation
```

## Sign-in model

There is no login page. The app authenticates itself as a seeded demo persona on load and exposes the rest as a **"viewing as" switcher** in the top bar — so every role's view of the RBAC model stays instantly explorable without a credentials form getting in the way.

Real authentication still runs underneath: accounts live in a `accounts` table with bcrypt-hashed passwords, and a signed JWT resolves to a persona (role + org access) — a caller cannot ask to be treated as a different persona than the token names. Nothing is exposed unauthenticated.

| Persona | Role | Plant | Sees |
|---|---|---|---|
| Sarah Chen | CISO | Chennai | Full technical drill-down |
| Miguel Alvarez | Plant Manager | Chennai | Business framing only, no controls panel |
| Priya Nair | OT Engineer | Chennai | Can resolve data-quality issues |
| Tom Becker | CISO | Mumbai | Mumbai's equivalent view |
| Lena Ortiz | Plant Manager | Pune | Highest-risk site, business framing |
| Dev Patel | OT Engineer | Bengaluru | Lowest-risk site |
| Ravi Krishnan | OT Engineer | Pune | Can resolve issues at the worst-scoring site |
| James Cole | External Auditor | Chennai / Pune / Mumbai | Redacted asset names, evidence-verification statements only |
| Amara Diallo | Corporate Admin | All six plants | Cross-plant comparison view |

Self-registration (`POST /api/auth/signup`) still works and creates a real account with `PLANT_MANAGER` access to Chennai — it's just not surfaced as a UI anymore.

## Running it

```bash
# 1. Backend
cd backend
python3.11 -m venv ../.venv && source ../.venv/bin/activate
pip install -r requirements.txt
python ../data-gen/generate_data.py     # seeds backend/coe_dashboard.sqlite3
uvicorn app.main:app --reload --port 8000

# 2. Frontend (separate terminal)
cd frontend
npm install
npm run dev     # http://localhost:5173
```

Re-run `python data-gen/generate_data.py` at any time to reset to a clean seeded state (this drops all accounts, including any you self-registered).

## The engineering decisions worth knowing about

- **Evidence-time-awareness.** A control's effectiveness is computed using the evidence that existed *at the date being scored* — a control isn't credited until proof of it existed at that point in time, which is what makes the baseline-vs-today comparison honest rather than retroactively flattering.
- **Marginal-contribution attribution can be super-additive.** When individually crediting each control (by counterfactually removing it) the sum can exceed the true total reduction, because overlapping controls share credit for the same protected asset. The dashboard reports this residual explicitly instead of silently forcing the numbers to add up.
- **Data-driven, not hardcoded.** The plant network, coordinates, and role/org access all come from `data-gen/plants.json`. Adding a seventh plant is a data change.
- **Two real bugs were found by actually clicking through the app as each role**, not by code review — see `docs/failure-mode-analysis.md` §3. That process is part of why this is described as tested, not just built.

## Known limitations (a prototype, and explicitly scoped as one)

No rate limiting or lockout on repeated failed logins, no password reset flow, no MFA, no refresh-token rotation, session tokens in `localStorage`/`sessionStorage` rather than an HTTPS-only cookie. Real production auth would need all of these; they're out of scope for demonstrating the risk-scoring and RBAC model itself.

## Docs
- [PRD & implementation plan](PRD_Control_Effectiveness_Dashboard.md)
- [Review 1 report](docs/review-1-report.md)
- [Field-workflow map](docs/field-workflow-map.md)
- [Technical documentation](docs/technical-documentation.md)
- [Failure-mode analysis](docs/failure-mode-analysis.md)
- [Stakeholder feedback summary](docs/user-feedback-summary.md)
- [Presentation](docs/presentation.md)
