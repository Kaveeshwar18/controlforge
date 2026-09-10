const ROLE_LABEL = {
  CISO: "CISO",
  PLANT_MANAGER: "Plant Manager",
  OT_ENGINEER: "OT Security Engineer",
  EXTERNAL_AUDITOR: "External Auditor",
  CORP_ADMIN: "Corporate Admin",
};

export default function IdentityBar({
  account, personas, onSwitchPersona, orgs, currentOrgId, onOrgChange, searchQuery, onSearchChange,
}) {
  if (!account) return null;

  const firstName = (account.name || account.username).split(" ")[0];
  const initials = (account.name || account.username)
    .split(" ")
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
  const orgName = orgs.find((o) => o.id === currentOrgId)?.name || "no plant selected";

  return (
    <header className="topbar">
      <div className="greeting">
        <h1>Hello, {firstName}</h1>
        <p>{ROLE_LABEL[account.role] || account.role} · {orgName}</p>
      </div>

      <div className="topbar-right">
        <label className="search-pill">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="7" />
            <path d="m21 21-4.3-4.3" strokeLinecap="round" />
          </svg>
          <input
            type="text"
            placeholder="Search equipment"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
          />
        </label>

        {/* only the plants this account actually has access to */}
        {orgs.length > 1 && (
          <select
            className="pill-select"
            value={currentOrgId || ""}
            onChange={(e) => onOrgChange(e.target.value)}
            title="Switch plant"
          >
            {orgs.map((o) => (
              <option key={o.id} value={o.id}>
                {o.name}{o.redacted ? " (redacted)" : ""}
              </option>
            ))}
          </select>
        )}

        {/* no login page -- this is how you become a different persona to
            compare what each role sees */}
        <select
          className="pill-select"
          value={account.username}
          onChange={(e) => onSwitchPersona(e.target.value)}
          title="Viewing as"
        >
          {personas.map((p) => (
            <option key={p.id} value={p.id}>{p.label}</option>
          ))}
        </select>
        <div className="avatar" title={`${account.username} · ${account.email}`}>{initials}</div>
      </div>
    </header>
  );
}
