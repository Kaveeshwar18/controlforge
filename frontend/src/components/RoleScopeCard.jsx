// Makes the permission model visible instead of implicit: the same dashboard
// looks different per role, and this card says how and why, so a reviewer
// switching personas can see the workflow change rather than having to spot it.

const ROLE_SCOPE = {
  CISO: {
    sees: ["Full technical drill-down: CVEs, evidence logs, incidents", "Per-control credit and confidence"],
    hidden: ["Other plants", "Cross-plant comparison"],
    does: "Reads and challenges the numbers. Can't resolve data issues — that stays with the people who fix them.",
  },
  PLANT_MANAGER: {
    sees: ["Business risk in plain terms", "How many controls are verified per machine"],
    hidden: ["CVE lists and evidence logs", "Control-by-control breakdown", "Other plants (not even listed)"],
    does: "Reads the business answer. Asks the CISO or engineer about anything flagged.",
  },
  OT_ENGINEER: {
    sees: ["Full technical drill-down", "Internal feed error messages"],
    hidden: ["Other plants"],
    does: "Resolves data-quality issues. Each fix writes real evidence and changes the score for every role.",
  },
  EXTERNAL_AUDITOR: {
    sees: ["Verification statements per control", "Feed freshness (without internal error detail)"],
    hidden: ["Equipment names (shown as generic labels)", "CVE lists and raw evidence logs", "Plants outside the audit scope"],
    does: "Read-only. Writes findings from the evidence statements.",
  },
  CORP_ADMIN: {
    sees: ["All six plants", "Cross-plant comparison", "Full technical drill-down"],
    hidden: [],
    does: "Compares plants and can resolve data issues anywhere.",
  },
};

export default function RoleScopeCard({ role, orgCount, redacted }) {
  const scope = ROLE_SCOPE[role];
  if (!scope) return null;
  return (
    <div className="card panel role-card">
      <div className="panel-header">
        <h3>What this view includes</h3>
        <span className="pill-static">{orgCount} {orgCount === 1 ? "plant" : "plants"}</span>
      </div>
      {redacted && <div className="role-redacted">Redacted view: equipment identities are masked for this plant.</div>}
      <div className="role-section-label">Visible</div>
      <ul className="role-list role-list-good">
        {scope.sees.map((s) => <li key={s}>{s}</li>)}
      </ul>
      {scope.hidden.length > 0 && (
        <>
          <div className="role-section-label">Withheld (enforced by the server, not just hidden)</div>
          <ul className="role-list role-list-muted">
            {scope.hidden.map((s) => <li key={s}>{s}</li>)}
          </ul>
        </>
      )}
      <div className="role-does">{scope.does}</div>
    </div>
  );
}
