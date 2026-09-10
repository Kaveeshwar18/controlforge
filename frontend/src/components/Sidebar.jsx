import { scrollToSection as scrollToId } from "../scroll";

const ICONS = {
  overview: <path d="M4 13h6V4H4v9Zm0 7h6v-5H4v5Zm10 0h6V11h-6v9Zm0-16v5h6V4h-6Z" />,
  map: <path d="M9 3 3 5v16l6-2 6 2 6-2V3l-6 2-6-2Zm0 0v16m6-16v16" fill="none" strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round" />,
  controls: <path d="M9 12l2 2 4-4M4 7l8-4 8 4v6c0 4.4-3.4 7.7-8 8-4.6-.3-8-3.6-8-8V7Z" fill="none" strokeWidth="1.8" strokeLinejoin="round" />,
  trend: <path d="M4 19h16M6 15l4-5 3 3 5-7" strokeLinecap="round" strokeLinejoin="round" fill="none" strokeWidth="1.8" />,
  assets: <path d="M4 5h16v4H4V5Zm0 6h16v4H4v-4Zm0 6h16v2H4v-2Z" fill="none" strokeWidth="1.6" />,
  quality: <path d="M12 3 2 20h20L12 3Zm0 6v5m0 3h.01" strokeLinecap="round" strokeLinejoin="round" fill="none" strokeWidth="1.8" />,
  compare: <path d="M8 4v16M16 4v16M4 8h4m8 0h4M4 16h4m8 0h4" strokeLinecap="round" fill="none" strokeWidth="1.8" />,
};

function NavItem({ name, label, active, onClick }) {
  return (
    <button className={`nav-item ${active ? "nav-item-active" : ""}`} onClick={onClick}>
      <svg width="19" height="19" viewBox="0 0 24 24" stroke="currentColor" fill={name === "overview" || name === "assets" ? "currentColor" : "none"}>
        {ICONS[name]}
      </svg>
      <span>{label}</span>
    </button>
  );
}

export default function Sidebar({
  showControls, showCompare, onCompareClick, onExitCompare, openIssues, onReviewIssues,
}) {
  // Every in-page nav target lives on the dashboard, so leave the compare
  // view first -- otherwise these buttons scroll a page that isn't shown.
  const goTo = (id) => {
    if (showCompare) onExitCompare();
    // let the dashboard mount before measuring its offsets
    requestAnimationFrame(() => scrollToId(id));
  };

  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark">
          <i className="mark-sq" /><i className="mark-ci" /><i className="mark-tr" />
        </span>
        <div className="brand-name"><strong>Control</strong>Forge</div>
      </div>

      <nav className="sidebar-nav">
        <NavItem name="overview" label="Dashboard" active={!showCompare} onClick={() => goTo("section-overview")} />
        <NavItem name="map" label="Facilities" onClick={() => goTo("section-map")} />
        <NavItem name="trend" label="Trend" onClick={() => goTo("section-trend")} />
        {showControls && <NavItem name="controls" label="Controls" onClick={() => goTo("section-controls")} />}
        <NavItem name="assets" label="Equipment" onClick={() => goTo("section-assets")} />
        <NavItem name="quality" label="Data quality" onClick={() => goTo("section-dataquality")} />
        {onCompareClick && <NavItem name="compare" label="Compare" active={showCompare} onClick={onCompareClick} />}
      </nav>

      {/* the promo slot in a consumer app -- here it carries the one thing
          that actually needs acting on, rather than an advert */}
      <div className="side-cta">
        <div className="side-cta-count">{openIssues ?? 0}</div>
        <div className="side-cta-text">
          open data-quality {openIssues === 1 ? "issue is" : "issues are"} limiting confidence in these numbers
        </div>
        <button className="side-cta-btn" onClick={onReviewIssues}>Review them</button>
      </div>
    </aside>
  );
}
