// Source-feed freshness. Every number on the dashboard is only as current as
// the feed it came from, so this is shown to every role -- what changes by
// role is whether you're told *why* a feed is down and how to fix it.

const STATE = {
  fresh: { label: "Current", cls: "badge-good" },
  aging: { label: "Delayed", cls: "badge-warn" },
  stale: { label: "Stale", cls: "badge-bad" },
  missing: { label: "Never connected", cls: "badge-bad" },
};

// What a stale feed means for the reader, in plain words. Kept here rather
// than in the API because it's presentation copy, not a scoring rule.
const CONSEQUENCE = {
  vuln_scanner: "Vulnerabilities disclosed since the last scan aren't counted, so the worst-case figure assumes 25% more exposure than last seen.",
  ticketing: "Incidents raised since the last sync aren't counted, so the worst-case figure assumes unrecorded open incidents.",
  cmdb: "New or retired equipment may be missing from the asset list. The score itself isn't adjusted, so treat the equipment count with caution.",
  edr_telemetry: "Endpoint detections may be delayed. The score itself isn't adjusted.",
};

function formatAge(hours) {
  if (hours == null) return "never";
  if (hours < 1) return `${Math.max(1, Math.round(hours * 60))} min ago`;
  if (hours < 48) return `${Math.round(hours)} h ago`;
  return `${Math.round(hours / 24)} days ago`;
}

export function DegradedBanner({ feeds, canFix, onReview }) {
  const down = (feeds || []).filter((f) => f.state === "stale" || f.state === "missing");
  if (down.length === 0) return null;
  return (
    <div className="degraded-banner" role="alert">
      <div className="degraded-icon" aria-hidden="true">!</div>
      <div className="degraded-copy">
        <strong>
          Part of this picture is out of date: {down.map((f) => f.label).join(" and ")}{" "}
          {down.length === 1 ? (down[0].state === "missing" ? "has never synced" : `last synced ${formatAge(down[0].hours_since_sync)}`) : "aren't syncing"}.
        </strong>
        {down.map((f) => (
          <p key={f.feed_id}>{CONSEQUENCE[f.feed_type]}</p>
        ))}
      </div>
      {canFix && (
        <button className="btn-small degraded-btn" onClick={onReview}>Restore feed</button>
      )}
    </div>
  );
}

export default function FeedHealthPanel({ feeds, computedAt }) {
  if (!feeds) return null;
  return (
    <div className="card panel">
      <div className="panel-header">
        <h3>Data freshness</h3>
      </div>
      <div className="panel-help">When each source system last delivered data into this score.</div>
      {feeds.length === 0 ? (
        <div className="empty-state">No source feeds registered for this plant — every figure here is unverifiable.</div>
      ) : (
        <ul className="feed-list">
          {feeds.map((f) => {
            const s = STATE[f.state] || { label: f.state, cls: "badge-neutral" };
            return (
              <li key={f.feed_id} className="feed-row">
                <div className="feed-copy">
                  <div className="feed-name">{f.label}</div>
                  <div className="feed-meta">
                    {f.state === "missing" ? "No data received yet" : `Synced ${formatAge(f.hours_since_sync)}`} · expected every {f.expected_interval_hours} h
                  </div>
                  {f.last_error && <div className="feed-error">{f.last_error}</div>}
                </div>
                <span className={`badge ${s.cls}`}>{s.label}</span>
              </li>
            );
          })}
        </ul>
      )}
      {computedAt && (
        <div className="footnote">Score recomputed {new Date(computedAt).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}.</div>
      )}
    </div>
  );
}
