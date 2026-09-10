import Gauge from "./Gauge";

function formatDate(iso) {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" });
}

// The hero card: the whole dashboard's finding in one plain-English sentence,
// so a non-technical reader gets the answer before any chart.
export default function SummaryBanner({ summary, orgName }) {
  if (!summary) return null;

  const {
    baseline_score, measured_score_best_case, measured_score_worst_case,
    reduction_pct, baseline_date, open_data_quality_issues, pct_of_target_achieved,
  } = summary;

  const improved = reduction_pct >= 0;
  const bestCasePct = baseline_score
    ? Math.round(((baseline_score - measured_score_best_case) / baseline_score) * 1000) / 10 : 0;
  const worstCasePct = baseline_score
    ? Math.round(((baseline_score - measured_score_worst_case) / baseline_score) * 1000) / 10 : 0;
  const wideBand = Math.abs(bestCasePct - worstCasePct) >= 10;

  return (
    <div className="hero">
      <div className="hero-copy">
        <div className="hero-eyebrow">In plain terms</div>
        <h2 className="hero-title">
          {orgName || "This plant"}'s business risk is{" "}
          <span className={improved ? "hero-em-good" : "hero-em-bad"}>
            {Math.abs(reduction_pct)}% {improved ? "lower" : "higher"}
          </span>{" "}
          than in {formatDate(baseline_date).replace(/,.*/, "")}
        </h2>
        <p className="hero-sub">
          Based on the security work completed since then.
          {wideBand && (
            <>
              {" "}It isn't fully proven yet — depending on how much can be independently verified, the real change
              ranges from a <b>{bestCasePct}% improvement</b> to{" "}
              <b>{worstCasePct >= 0 ? `only ${worstCasePct}%` : `a ${Math.abs(worstCasePct)}% increase in risk`}</b>.
            </>
          )}
          {open_data_quality_issues > 0 && (
            <> <b>{open_data_quality_issues} open data-quality issues</b> are limiting that confidence.</>
          )}
        </p>
      </div>

      <div className="hero-gauge">
        <Gauge value={pct_of_target_achieved} size={128} stroke={13} />
        <div className="hero-gauge-label">of the best achievable score reached</div>
      </div>
    </div>
  );
}
