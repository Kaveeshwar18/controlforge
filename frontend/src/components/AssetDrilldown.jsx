import Modal from "./Modal";
import { FreshnessBadge, StatusBadge, FlagBadge, sourceLabel } from "./StatusBadge";

export default function AssetDrilldown({ asset, loading, error, onClose }) {
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
  if (!asset) return null;

  const isSummaryOnly = !asset.controls;

  return (
    <Modal
      title={asset.display_name}
      subtitle={`${asset.zone} zone · ${asset.asset_type} · risk score ${asset.weighted_risk}`}
      onClose={onClose}
    >
      <div className="drilldown-flags">
        {asset.criticality_conflict && <FlagBadge tone="bad">Two source systems disagree on how critical this is — scored conservatively until resolved</FlagBadge>}
        {asset.missing_telemetry && <FlagBadge tone="bad">No monitoring feed — this risk score can't be independently checked</FlagBadge>}
      </div>

      {isSummaryOnly ? (
        <>
          <h4>Security controls covering this asset</h4>
          <div className="summary-grid summary-grid-compact">
            <div className="card metric-card">
              <div className="metric-label">Controls that apply</div>
              <div className="metric-value">{asset.controls_summary.applicable}</div>
            </div>
            <div className="card metric-card">
              <div className="metric-label">Verified</div>
              <div className="metric-value metric-value-good">{asset.controls_summary.verified}</div>
            </div>
            <div className="card metric-card">
              <div className="metric-label">Not yet verified</div>
              <div className="metric-value metric-value-bad">{asset.controls_summary.unverified_or_missing}</div>
            </div>
            <div className="card metric-card">
              <div className="metric-label">Open weaknesses</div>
              <div className="metric-value">{asset.open_exposure_count}</div>
            </div>
          </div>
          <p className="footnote">Technical details (specific vulnerabilities, verification logs) aren't shown at this level — this is the business summary.</p>
        </>
      ) : (
        <>
          <h4>Security controls covering this asset</h4>
          <table className="data-table">
            <thead>
              <tr><th>Control</th><th>Status</th><th>Evidence</th></tr>
            </thead>
            <tbody>
              {asset.controls.map((c) => (
                <tr key={c.control_id}>
                  <td>{c.name}{c.status === "in_progress" && <span className="muted"> ({c.rollout_percentage}% rolled out)</span>}</td>
                  <td><StatusBadge status={c.status} /></td>
                  <td><FreshnessBadge freshness={c.evidence.freshness} /> {c.evidence.source && <span className="muted small">via {sourceLabel(c.evidence.source)}</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <h4>Vulnerabilities</h4>
          {asset.vulnerabilities.length === 0 ? (
            <div className="empty-state">No vulnerabilities on file for this asset.</div>
          ) : (
            <table className="data-table">
              <thead><tr><th>CVE</th><th>CVSS</th><th>Status</th><th>Discovered</th></tr></thead>
              <tbody>
                {asset.vulnerabilities.map((v) => (
                  <tr key={v.id}>
                    <td>{v.cve_ref}</td>
                    <td>{v.cvss}</td>
                    <td className="muted">{v.status.replace(/_/g, " ")}</td>
                    <td className="muted">{v.discovered_date}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <h4>Incidents (last 90 days considered in scoring)</h4>
          {asset.incidents.length === 0 ? (
            <div className="empty-state">No incidents on file for this asset.</div>
          ) : (
            <table className="data-table">
              <thead><tr><th>Severity</th><th>Detected</th><th>Resolved</th><th>Root cause</th></tr></thead>
              <tbody>
                {asset.incidents.map((i) => (
                  <tr key={i.id}>
                    <td className="muted">{i.severity}</td>
                    <td className="muted">{i.detected_date}</td>
                    <td className="muted">{i.resolved_date || "Unresolved"}</td>
                    <td className="muted small">{i.root_cause}</td>
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
