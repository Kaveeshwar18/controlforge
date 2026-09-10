export default function ComparePanel({ data, error }) {
  return (
    <div className="card panel">
      <div className="panel-header">
        <h3>Comparing every plant</h3>
        <span className="panel-sub">Corporate Admin only — for deciding where security investment is most needed</span>
      </div>

      {error && <div className="error-state">{error}</div>}

      {data && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Plant</th>
              <th>Risk before</th>
              <th>Risk today</th>
              <th>Change</th>
              <th>Progress to best achievable</th>
            </tr>
          </thead>
          <tbody>
            {data.map((o) => (
              <tr key={o.org_id}>
                <td>{o.org_name}</td>
                <td className="muted">{o.baseline_score}</td>
                <td><strong>{o.measured_score}</strong></td>
                <td className={o.reduction_pct >= 0 ? "metric-value-good" : "metric-value-bad"}>
                  {Math.abs(o.reduction_pct)}% {o.reduction_pct >= 0 ? "lower ↓" : "higher ↑"}
                </td>
                <td>{o.pct_of_target_achieved}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
