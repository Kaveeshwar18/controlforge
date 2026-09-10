// Progress ring -- thick stroke with rounded caps, matching the donut style
// used across the dashboard. Hand-rolled SVG so it always renders.
export default function Gauge({ value, size = 120, stroke = 12 }) {
  const pct = Math.max(0, Math.min(100, value));
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  // keep a sliver visible at very low values so the ring never reads as broken
  const visiblePct = pct > 0 ? Math.max(pct, 2.5) : 0;
  const dash = (visiblePct / 100) * circumference;
  const center = size / 2;

  return (
    <div className="gauge-wrap" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <defs>
          <linearGradient id="gaugeGrad" x1="0%" y1="100%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#b9c0d4" />
            <stop offset="100%" stopColor="var(--ink)" />
          </linearGradient>
        </defs>
        <circle cx={center} cy={center} r={radius} fill="none" stroke="var(--surface-alt)" strokeWidth={stroke} />
        <circle
          cx={center} cy={center} r={radius}
          fill="none" stroke="url(#gaugeGrad)" strokeWidth={stroke}
          strokeDasharray={`${dash} ${circumference - dash}`}
          strokeLinecap="round"
          transform={`rotate(-90 ${center} ${center})`}
        />
      </svg>
      <div className="gauge-center">
        <div className="gauge-value">
          {Math.round(pct)}<span className="gauge-pct">%</span>
        </div>
      </div>
    </div>
  );
}
