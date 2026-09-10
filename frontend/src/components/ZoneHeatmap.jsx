const SEGMENT_COLORS = ["#15171c", "#6b7280", "#b9c0d4"];

export default function ZoneHeatmap({ zones }) {
  if (!zones) return null;

  if (zones.length === 0) {
    return (
      <div className="card panel">
        <div className="panel-header"><h3>Risk by network zone</h3></div>
        <div className="empty-state">No zone data available for this organization.</div>
      </div>
    );
  }

  const total = zones.reduce((sum, z) => sum + z.risk_index, 0);
  const size = 168;
  const stroke = 20;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;

  // build the donut segments, each one sized by that zone's share of total risk
  let offset = 0;
  const segments = zones.map((z, i) => {
    const share = total > 0 ? z.risk_index / total : 0;
    const dash = share * circumference;
    const seg = {
      zone: z.zone,
      color: SEGMENT_COLORS[i % SEGMENT_COLORS.length],
      dash,
      gap: circumference - dash,
      offset: -offset,
      sharePct: Math.round(share * 100),
    };
    offset += dash;
    return seg;
  });

  const topZone = zones.reduce((a, b) => (b.risk_index > a.risk_index ? b : a), zones[0]);
  const topShare = total > 0 ? Math.round((topZone.risk_index / total) * 100) : 0;

  return (
    <div className="card panel">
      <div className="panel-header">
        <h3>Risk by network zone</h3>
      </div>

      <div className="donut-wrap">
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="var(--surface-alt)" strokeWidth={stroke} />
          {segments.map((s) => (
            <circle
              key={s.zone}
              cx={size / 2} cy={size / 2} r={radius}
              fill="none" stroke={s.color} strokeWidth={stroke}
              strokeDasharray={`${s.dash} ${s.gap}`}
              strokeDashoffset={s.offset}
              strokeLinecap="butt"
              transform={`rotate(-90 ${size / 2} ${size / 2})`}
            />
          ))}
        </svg>
        <div className="donut-center">
          <div className="donut-value">{topShare}<span className="gauge-pct">%</span></div>
          <div className="donut-label">in {topZone.zone}</div>
        </div>
      </div>

      <ul className="donut-legend">
        {zones.map((z, i) => (
          <li key={z.zone}>
            <span className="legend-dot" style={{ background: SEGMENT_COLORS[i % SEGMENT_COLORS.length] }} />
            <span className="legend-name">
              {z.zone}
              {z.unmonitored_assets > 0 && (
                <em className="legend-flag">{z.unmonitored_assets} unmonitored</em>
              )}
            </span>
            <span className="legend-value">{z.risk_index}</span>
          </li>
        ))}
      </ul>
      <div className="footnote">Higher score = more business risk concentrated in that zone.</div>
    </div>
  );
}
