import { useState } from "react";
import { ComposableMap, Geographies, Geography, Marker } from "react-simple-maps";
import worldTopo from "world-atlas/countries-50m.json";

// India plus its neighbours, so the country doesn't float in empty space.
const INDIA_ID = "356";
const CONTEXT_COUNTRIES = new Set([
  "586", // Pakistan
  "050", // Bangladesh
  "144", // Sri Lanka
  "524", // Nepal
  "064", // Bhutan
  "104", // Myanmar
  "156", // China
  "004", // Afghanistan
]);

const LEVEL_COLOR = { high: "var(--bad)", elevated: "var(--warn)", low: "var(--good)" };
const LEVEL_LABEL = { high: "High risk", elevated: "Elevated", low: "Low risk" };

function Stat({ label, value, tone }) {
  return (
    <div className="plant-stat">
      <div className="plant-stat-label">{label}</div>
      <div className={`plant-stat-value ${tone ? `tone-${tone}` : ""}`}>{value}</div>
    </div>
  );
}

export default function MapPanel({ orgs, currentOrgId, onSelectOrg }) {
  const plants = (orgs || []).filter((o) => o.org_type === "plant" && o.lat != null);
  const [selectedId, setSelectedId] = useState(null);

  const selected = plants.find((p) => p.id === selectedId) || null;

  return (
    <div className="card panel">
      <div className="panel-header">
        <h3>Plant network</h3>
        <span className="pill-static">
          {plants.length} site{plants.length === 1 ? "" : "s"}
        </span>
      </div>
      <div className="panel-help">
        Marker colour is the site's current risk band. Select a marker for its detail, or open it to switch the whole
        dashboard to that plant.
      </div>

      {plants.length === 0 ? (
        <div className="empty-state">No facilities with location data are accessible to this role.</div>
      ) : (
        <div className="map-layout">
          <div className="map-frame">
            <ComposableMap
              projection="geoMercator"
              projectionConfig={{ center: [82.5, 21], scale: 780 }}
              width={420}
              height={430}
              style={{ width: "100%", height: "auto" }}
            >
              <Geographies geography={worldTopo}>
                {({ geographies }) =>
                  geographies
                    .filter((geo) => geo.id === INDIA_ID || CONTEXT_COUNTRIES.has(geo.id))
                    .map((geo) => {
                      const isIndia = geo.id === INDIA_ID;
                      return (
                        <Geography
                          key={geo.rsmKey}
                          geography={geo}
                          fill={isIndia ? "#dee2ec" : "#f2f3f7"}
                          stroke="#ffffff"
                          strokeWidth={isIndia ? 1 : 0.7}
                          style={{
                            default: { outline: "none" },
                            hover: { outline: "none", fill: isIndia ? "#d3d8e6" : "#f2f3f7" },
                            pressed: { outline: "none" },
                          }}
                        />
                      );
                    })
                }
              </Geographies>

              {plants.map((p) => {
                const color = LEVEL_COLOR[p.risk_level] || "var(--text-muted)";
                const isActive = p.id === currentOrgId;
                const isSelected = p.id === selectedId;
                return (
                  <Marker
                    key={p.id}
                    coordinates={[p.lon, p.lat]}
                    onClick={() => setSelectedId(isSelected ? null : p.id)}
                  >
                    <g className={`map-pin ${isActive ? "map-pin-active" : ""}`} style={{ cursor: "pointer" }}>
                      <circle r={isSelected ? 13 : 9} fill={color} fillOpacity={0.2} />
                      <circle
                        r={isSelected ? 6.5 : 5}
                        fill={color}
                        stroke="#fff"
                        strokeWidth={isSelected ? 2.5 : 1.8}
                      />
                      <text className="map-pin-label" textAnchor="middle" y={-15}>
                        {p.city}
                      </text>
                    </g>
                  </Marker>
                );
              })}
            </ComposableMap>

            <div className="map-legend">
              <span><i style={{ background: "var(--good)" }} /> Low</span>
              <span><i style={{ background: "var(--warn)" }} /> Elevated</span>
              <span><i style={{ background: "var(--bad)" }} /> High</span>
            </div>
          </div>

          <div className="plant-detail">
            {!selected ? (
              <div className="plant-detail-empty">
                <strong>Select a plant</strong>
                <p>Tap any marker to see its risk, findings and control effectiveness.</p>
                <ul className="plant-mini-list">
                  {[...plants]
                    .sort((a, b) => b.measured_score - a.measured_score)
                    .map((p) => (
                      <li key={p.id} onClick={() => setSelectedId(p.id)}>
                        <span className="legend-dot" style={{ background: LEVEL_COLOR[p.risk_level] }} />
                        <span className="legend-name">{p.city}</span>
                        <span className="legend-value">{p.measured_score}</span>
                      </li>
                    ))}
                </ul>
              </div>
            ) : (
              <>
                <div className="plant-detail-head">
                  <div>
                    <h4>{selected.name}</h4>
                    <p>{selected.city}, {selected.state}</p>
                  </div>
                  <span
                    className="plant-band"
                    style={{ color: LEVEL_COLOR[selected.risk_level], borderColor: LEVEL_COLOR[selected.risk_level] }}
                  >
                    {LEVEL_LABEL[selected.risk_level]}
                  </span>
                </div>

                <div className="plant-stat-grid">
                  <Stat label="Risk today" value={selected.measured_score} />
                  <Stat label="Baseline" value={selected.baseline_score} />
                  <Stat
                    label="Reduction"
                    value={`${selected.reduction_pct >= 0 ? "" : "+"}${Math.abs(selected.reduction_pct)}%`}
                    tone={selected.reduction_pct >= 0 ? "good" : "bad"}
                  />
                  <Stat label="Control effectiveness" value={`${selected.control_effectiveness}%`} />
                  <Stat label="Critical assets" value={`${selected.critical_assets} of ${selected.asset_count}`} />
                  <Stat label="Open vulnerabilities" value={selected.open_vulnerabilities} />
                  <Stat label="Unresolved incidents" value={selected.open_incidents} />
                  <Stat
                    label="Unmonitored"
                    value={selected.unmonitored_assets}
                    tone={selected.unmonitored_assets > 0 ? "bad" : null}
                  />
                </div>

                {selected.id !== currentOrgId ? (
                  <button className="btn-small plant-open-btn" onClick={() => onSelectOrg(selected.id)}>
                    Open this plant's dashboard
                  </button>
                ) : (
                  <div className="plant-current-note">Currently shown across the dashboard.</div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
