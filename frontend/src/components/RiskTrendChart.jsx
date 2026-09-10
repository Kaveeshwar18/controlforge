import { LineChart, Line, XAxis, YAxis, Tooltip, ReferenceLine, ResponsiveContainer, CartesianGrid } from "recharts";

function shortDate(iso) {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short" });
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tip">
      <div className="chart-tip-label">Risk score</div>
      <div className="chart-tip-value">{payload[0].value}</div>
      <div className="chart-tip-date">{label}</div>
    </div>
  );
}

export default function RiskTrendChart({ trend }) {
  if (!trend) return null;
  const data = trend.history.map((p) => ({ ...p, month: shortDate(p.date) }));

  return (
    <div className="card panel">
      <div className="panel-header">
        <h3>Reports</h3>
        <span className="pill-static">Last 6 months</span>
      </div>

      <ResponsiveContainer width="100%" height={210}>
        <LineChart data={data} margin={{ top: 12, right: 10, left: -18, bottom: 0 }}>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis
            dataKey="month" tickLine={false} axisLine={false}
            tick={{ fontSize: 11, fill: "var(--text-faint)" }} dy={6}
          />
          <YAxis
            tickLine={false} axisLine={false}
            tick={{ fontSize: 11, fill: "var(--text-faint)" }} width={44}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ stroke: "var(--border-strong)", strokeDasharray: "3 3" }} />
          {trend.target_score != null && (
            <ReferenceLine
              y={trend.target_score}
              stroke="var(--good)"
              strokeDasharray="4 4"
              label={{ value: "target", position: "insideBottomRight", fontSize: 10, fill: "var(--good)" }}
            />
          )}
          <Line
            type="monotone" dataKey="score" stroke="var(--ink)" strokeWidth={2.5}
            dot={false} activeDot={{ r: 5, fill: "#fff", stroke: "var(--ink)", strokeWidth: 2.5 }}
          />
        </LineChart>
      </ResponsiveContainer>
      <div className="footnote">Dashed line is the best score achievable if the current control plan finishes.</div>
    </div>
  );
}
