import { useState } from "react";

// Short label for the chip; the full plain-English explanation is the row's
// description text, so the chip only has to categorise.
const TYPE_LABEL = {
  conflict: "Conflict",
  missing_feed: "Unverified",
  stale_evidence: "Out of date",
  regression: "Regression",
};

const TYPE_TONE = {
  conflict: "warn",
  missing_feed: "bad",
  stale_evidence: "warn",
  regression: "bad",
};

export default function DataQualityPanel({ issues, canResolve, onResolve }) {
  const [resolvingId, setResolvingId] = useState(null);
  if (!issues) return null;

  const open = issues.filter((i) => i.status === "open");
  const resolved = issues.filter((i) => i.status === "resolved");

  const handleResolve = async (id) => {
    setResolvingId(id);
    try {
      await onResolve(id);
    } finally {
      setResolvingId(null);
    }
  };

  return (
    <div className="card panel">
      <div className="panel-header">
        <h3>Things limiting how much we can trust this data</h3>
        <span className="pill-static">{open.length} open · {resolved.length} resolved</span>
      </div>
      <div className="panel-help">
        Every risk number above is only as good as the data behind it. These are the gaps currently reducing confidence.
      </div>

      {open.length === 0 ? (
        <div className="empty-state empty-state-good">
          Nothing open — every control feeding the risk score has current, unconflicted evidence.
        </div>
      ) : (
        <ul className="issue-list">
          {open.map((i) => (
            <li key={i.id} className="issue-row">
              <span className={`badge badge-${TYPE_TONE[i.issue_type] || "neutral"} issue-chip`}>
                {TYPE_LABEL[i.issue_type] || i.issue_type}
              </span>
              <span className="issue-desc">{i.description}</span>
              <span className="issue-meta">{i.created_date}</span>
              {canResolve ? (
                <button className="btn-small" disabled={resolvingId === i.id} onClick={() => handleResolve(i.id)}>
                  {resolvingId === i.id ? "Resolving…" : "Resolve"}
                </button>
              ) : (
                <span className="issue-meta issue-locked">Engineer only</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
