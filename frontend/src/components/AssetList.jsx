import { FlagBadge } from "./StatusBadge";

export default function AssetList({ assets, onSelectAsset }) {
  if (!assets) return null;

  return (
    <div className="card panel">
      <div className="panel-header">
        <h3>Equipment driving the most risk</h3>
        <span className="panel-sub">Ranked by importance to the business, not just technical severity</span>
      </div>
      <div className="panel-help">Click any row for the evidence behind its score. "No telemetry" means we have no monitoring on that device at all.</div>

      {assets.length === 0 ? (
        <div className="empty-state">No assets found for this organization.</div>
      ) : (
        <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>Asset</th>
              <th>Zone</th>
              <th>Type</th>
              <th>Risk score</th>
              <th>Issues</th>
            </tr>
          </thead>
          <tbody>
            {assets.map((a) => (
              <tr key={a.asset_id} className="clickable-row" onClick={() => onSelectAsset(a.asset_id)}>
                <td>{a.display_name}</td>
                <td className="muted">{a.zone}</td>
                <td className="muted">{a.asset_type}</td>
                <td><strong>{a.weighted_risk}</strong></td>
                <td>
                  {a.criticality_conflict && <FlagBadge tone="bad">Data conflict</FlagBadge>}{" "}
                  {a.missing_telemetry && <FlagBadge tone="bad">No telemetry</FlagBadge>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      )}
    </div>
  );
}
