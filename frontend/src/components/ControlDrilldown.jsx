import Modal from "./Modal";
import { StatusBadge, FreshnessBadge, sourceLabel } from "./StatusBadge";

export default function ControlDrilldown({ control, loading, error, onClose }) {
  if (loading) {
    return (
      <Modal title="Loading…" onClose={onClose}>
        <div className="empty-state">Fetching evidence…</div>
      </Modal>
    );
  }
  if (error) {
    return (
      <Modal title="Not available" onClose={onClose}>
        <div className="error-state">{error}</div>
      </Modal>
    );
  }
  if (!control) return null;

  return (
    <Modal
      title={control.name}
      subtitle={`${control.control_type.replace(/_/g, " ")} · ${control.rollout_percentage}% rolled out`}
      onClose={onClose}
    >
      <div className="drilldown-flags">
        <StatusBadge status={control.status} />
        <FreshnessBadge freshness={control.evidence_state.freshness} />
      </div>

      <div className="summary-grid summary-grid-compact">
        <div className="card metric-card">
          <div className="metric-label">Planned</div>
          <div className="metric-value" style={{ fontSize: 16 }}>{control.planned_date || "—"}</div>
        </div>
        <div className="card metric-card">
          <div className="metric-label">Completed</div>
          <div className="metric-value" style={{ fontSize: 16 }}>{control.completion_date || "—"}</div>
        </div>
        <div className="card metric-card">
          <div className="metric-label">Verified</div>
          <div className="metric-value" style={{ fontSize: 16 }}>{control.evidence_state.verified ? "Yes" : "No"}</div>
        </div>
        <div className="card metric-card">
          <div className="metric-label">How sure we are</div>
          <div className="metric-value" style={{ fontSize: 16 }}>{Math.round(control.evidence_state.confidence * 100)}%</div>
        </div>
      </div>

      {control.evidence_package_statement ? (
        <>
          <h4>Verification summary</h4>
          <p>{control.evidence_package_statement}</p>
          <p className="footnote">This role sees a verification summary, not the underlying monitoring detail.</p>
        </>
      ) : (
        <>
          <h4>Verification history</h4>
          {control.evidence_log.length === 0 ? (
            <div className="empty-state">No verification evidence on file for this control.</div>
          ) : (
            <table className="data-table">
              <thead><tr><th>When</th><th>How it was checked</th><th>Result</th></tr></thead>
              <tbody>
                {control.evidence_log.map((e, idx) => (
                  <tr key={idx}>
                    <td className="muted">{e.timestamp.replace("T", " ")}</td>
                    <td className="muted">{sourceLabel(e.source)}</td>
                    <td className="muted">{e.result}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </Modal>
  );
}
