// Short, plain versions of the backend's confidence notes -- the full
// explanation is still available in the drill-down.
function shortConfidence(note) {
  if (note.startsWith("No verification")) return "Not verified — no credit given";
  if (note.startsWith("Last checked")) return "Check is out of date";
  if (note.startsWith("Self-attested")) return "Self-reported only";
  return "Independently verified";
}

function confidenceTone(note) {
  if (note.startsWith("No verification")) return "bad";
  if (note.startsWith("Last checked")) return "warn";
  if (note.startsWith("Self-attested")) return "warn";
  return "good";
}

export default function ControlLeaderboard({ data, onSelectControl }) {
  if (!data) return null;
  const { controls, residual_interaction_effect } = data;

  const total = controls.reduce((sum, c) => sum + Math.max(0, c.risk_reduction_attributed), 0);
  const top = controls.slice(0, 6);

  return (
    <div className="card panel">
      <div className="panel-header">
        <h3>Top performing controls</h3>
      </div>
      <div className="panel-help">Share of the risk reduction each one is credited with. Tap for the evidence.</div>

      {controls.length === 0 ? (
        <div className="empty-state">No completed controls with credited risk reduction yet.</div>
      ) : (
        <ul className="activity-list">
          {top.map((c) => {
            const share = total > 0 ? Math.round((Math.max(0, c.risk_reduction_attributed) / total) * 100) : 0;
            return (
              <li key={c.control_id} className="activity-row" onClick={() => onSelectControl(c.control_id)}>
                <div className="activity-copy">
                  <div className="activity-name">{c.name}</div>
                  <div className={`activity-meta tone-${confidenceTone(c.confidence_note)}`}>
                    {shortConfidence(c.confidence_note)}
                  </div>
                </div>
                <div className="activity-badge">{share}%</div>
              </li>
            );
          })}
        </ul>
      )}

      <div className="footnote">
        {residual_interaction_effect < 0
          ? `Shares are of credited reduction only. Controls overlap on the same equipment, so individual credit adds up to ${Math.abs(residual_interaction_effect)} more than the true total — the headline number already corrects for that.`
          : "Shares are of the total risk reduction credited to completed controls."}
      </div>
    </div>
  );
}
