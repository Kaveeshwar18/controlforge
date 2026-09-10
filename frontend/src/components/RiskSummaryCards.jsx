export default function RiskSummaryCards({ summary, role }) {
  if (!summary) return null;

  const businessFraming = role === "PLANT_MANAGER" || role === "EXTERNAL_AUDITOR";
  const improved = summary.reduction_pct >= 0;

  return (
    <div className="score-stack">
      <div className="score-card score-card-dark">
        <div className="score-label">Risk today</div>
        <div className="score-value">{summary.measured_score}</div>
        <div className="score-range">
          likely between {summary.measured_score_best_case} and {summary.measured_score_worst_case}
        </div>
        <div className="score-foot">
          <span>{businessFraming ? "Business risk" : "Attributed to controls"}</span>
          <span className={improved ? "score-delta-good" : "score-delta-bad"}>
            {improved ? "↓" : "↑"} {Math.abs(summary.reduction_pct)}%
          </span>
        </div>
      </div>

      <div className="score-card">
        <div className="score-label">Where it started</div>
        <div className="score-value score-value-light">{summary.baseline_score}</div>
        <div className="score-range">on {summary.baseline_date}, before this period's work</div>
        <div className="score-foot">
          <span>Best achievable</span>
          <span className="score-target">{summary.target_score}</span>
        </div>
      </div>
    </div>
  );
}
