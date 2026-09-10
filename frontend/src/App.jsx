import { useEffect, useMemo, useState, useCallback, useRef } from "react";
import { api, ApiError, tokenStore } from "./api";
import { scrollToSection } from "./scroll";
import IdentityBar from "./components/IdentityBar";
import Sidebar from "./components/Sidebar";
import MapPanel from "./components/MapPanel";
import SummaryBanner from "./components/SummaryBanner";
import RiskSummaryCards from "./components/RiskSummaryCards";
import RiskTrendChart from "./components/RiskTrendChart";
import ZoneHeatmap from "./components/ZoneHeatmap";
import ControlLeaderboard from "./components/ControlLeaderboard";
import AssetList from "./components/AssetList";
import DataQualityPanel from "./components/DataQualityPanel";
import AssetDrilldown from "./components/AssetDrilldown";
import ControlDrilldown from "./components/ControlDrilldown";
import ComparePanel from "./components/ComparePanel";
import "./App.css";

// No login screen -- the app signs itself in as a seeded demo persona and
// exposes the rest of them as a "viewing as" switcher, so every role's view
// of the RBAC model is still explorable without a credentials form. The
// password is the same well-known local-only demo seed documented in the
// README, not a real secret.
const DEMO_PASSWORD = "controlforge-demo-2026";
const DEMO_PERSONAS = [
  { id: "sarah.chen", label: "Sarah Chen — CISO (Chennai)" },
  { id: "miguel.alvarez", label: "Miguel Alvarez — Plant Manager (Chennai)" },
  { id: "priya.nair", label: "Priya Nair — OT Engineer (Chennai)" },
  { id: "tom.becker", label: "Tom Becker — CISO (Mumbai)" },
  { id: "lena.ortiz", label: "Lena Ortiz — Plant Manager (Pune)" },
  { id: "dev.patel", label: "Dev Patel — OT Engineer (Bengaluru)" },
  { id: "ravi.krishnan", label: "Ravi Krishnan — OT Engineer (Pune)" },
  { id: "james.cole", label: "James Cole — External Auditor" },
  { id: "amara.diallo", label: "Amara Diallo — Corporate Admin" },
];

export default function App() {
  // -- session --
  const [account, setAccount] = useState(null);
  const [bootstrapping, setBootstrapping] = useState(true);

  const [me, setMe] = useState(null);
  const [orgs, setOrgs] = useState([]);
  const [currentOrgId, setCurrentOrgId] = useState(null);

  const [dashboard, setDashboard] = useState({ summary: null, trend: null, zones: null, controls: null, assets: null, dq: null, orgs: null });
  const [dashboardLoading, setDashboardLoading] = useState(false);
  const [dashboardError, setDashboardError] = useState(null);

  const [selectedAssetId, setSelectedAssetId] = useState(null);
  const [assetDetail, setAssetDetail] = useState(null);
  const [assetLoading, setAssetLoading] = useState(false);
  const [assetError, setAssetError] = useState(null);

  const [selectedControlId, setSelectedControlId] = useState(null);
  const [controlDetail, setControlDetail] = useState(null);
  const [controlLoading, setControlLoading] = useState(false);
  const [controlError, setControlError] = useState(null);

  const [showCompare, setShowCompare] = useState(false);
  const [compareData, setCompareData] = useState(null);
  const [compareError, setCompareError] = useState(null);

  const [searchQuery, setSearchQuery] = useState("");

  const [authError, setAuthError] = useState(null);

  const resetSessionState = () => {
    setMe(null);
    setOrgs([]);
    setCurrentOrgId(null);
    setShowCompare(false);
    setSearchQuery("");
    setDashboard({ summary: null, trend: null, zones: null, controls: null, assets: null, dq: null, orgs: null });
  };

  const signInAs = useCallback((personaId) => {
    setBootstrapping(true);
    setAuthError(null);
    resetSessionState();
    return api
      .login({ identifier: personaId, password: DEMO_PASSWORD })
      .then((session) => {
        tokenStore.set(session.token);
        setAccount(session.account);
      })
      .catch((e) => {
        tokenStore.clear();
        setAccount(null);
        setAuthError(e instanceof ApiError ? e.detail || e.message : e.message);
      })
      .finally(() => setBootstrapping(false));
  }, []);

  // -- restore an existing session, or fall back to the default demo persona
  // -- there is no login page, so the app always lands on a working account
  useEffect(() => {
    if (!tokenStore.get()) {
      signInAs(DEMO_PERSONAS[0].id);
      return;
    }
    api.me()
      .then(setAccount)
      .catch(() => {
        tokenStore.clear(); // expired or invalid -- fall back to the default persona
        signInAs(DEMO_PERSONAS[0].id);
      })
      .finally(() => setBootstrapping(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSwitchPersona = (personaId) => {
    signInAs(personaId);
  };

  // -- once signed in: load capabilities and the orgs this account may see --
  useEffect(() => {
    if (!account) return;
    let cancelled = false;
    Promise.all([api.capabilities(), api.listOrgs()])
      .then(([caps, orgList]) => {
        if (cancelled) return;
        // A custom/self-registered account with zero orgs is unusable (this
        // is exactly what a stale session from before the plant network's
        // US->India migration looked like -- see auth_routes.py's DEFAULT_ORG
        // fix). Rather than strand the user on a broken account, fall back
        // to a known-good demo persona. A seeded demo persona genuinely
        // having zero orgs would be a real data bug, so that case still
        // surfaces the error state below instead of looping.
        const isDemoPersona = DEMO_PERSONAS.some((p) => p.id === account.username);
        if (orgList.length === 0 && !isDemoPersona) {
          signInAs(DEMO_PERSONAS[0].id);
          return;
        }
        setMe(caps);
        setOrgs(orgList);
        setCurrentOrgId(orgList.length > 0 ? orgList[0].id : null);
      })
      .catch((e) => {
        if (cancelled) return;
        if (e instanceof ApiError && e.status === 401) signInAs(DEMO_PERSONAS[0].id);
        else setDashboardError(e.detail || e.message);
      });
    return () => { cancelled = true; };
  }, [account, signInAs]);

  const currentOrgName = useMemo(
    () => orgs.find((o) => o.id === currentOrgId)?.name || null,
    [orgs, currentOrgId]
  );

  // Guards against out-of-order responses: switching org fires a new request
  // before the previous one settles, and a slower stale request resolving
  // later must not clobber the fresher state it was superseded by.
  const loadRequestId = useRef(0);

  const loadDashboard = useCallback(() => {
    if (!account || !currentOrgId) return;
    const requestId = ++loadRequestId.current;
    setDashboardLoading(true);
    setDashboardError(null);
    Promise.all([
      api.riskSummary(currentOrgId),
      api.riskTrend(currentOrgId),
      api.zones(currentOrgId),
      api.controlLeaderboard(currentOrgId),
      api.topAssets(currentOrgId),
      api.dataQuality(currentOrgId),
      api.listOrgs(),
    ])
      .then(([summary, trend, zones, controls, assets, dq, orgList]) => {
        if (requestId !== loadRequestId.current) return; // superseded by a newer request
        setDashboard({ summary, trend, zones, controls, assets, dq, orgs: orgList });
      })
      .catch((e) => {
        if (requestId !== loadRequestId.current) return;
        if (e instanceof ApiError && e.status === 401) {
          signInAs(DEMO_PERSONAS[0].id);
          return;
        }
        if (e instanceof ApiError && e.status === 403) {
          setDashboardError(e.detail || "Not authorized to view this organization.");
        } else {
          setDashboardError(e.message || "Failed to load dashboard data.");
        }
        setDashboard({ summary: null, trend: null, zones: null, controls: null, assets: null, dq: null, orgs: null });
      })
      .finally(() => {
        if (requestId === loadRequestId.current) setDashboardLoading(false);
      });
  }, [account, currentOrgId, signInAs]);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  const openAsset = (assetId) => {
    setSelectedAssetId(assetId);
    setAssetLoading(true);
    setAssetError(null);
    setAssetDetail(null);
    api.assetDetail(currentOrgId, assetId)
      .then(setAssetDetail)
      .catch((e) => setAssetError(e.detail || e.message))
      .finally(() => setAssetLoading(false));
  };

  const openControl = (controlId) => {
    setSelectedControlId(controlId);
    setControlLoading(true);
    setControlError(null);
    setControlDetail(null);
    api.controlDetail(currentOrgId, controlId)
      .then(setControlDetail)
      .catch((e) => setControlError(e.detail || e.message))
      .finally(() => setControlLoading(false));
  };

  const handleResolveIssue = async (issueId) => {
    await api.resolveIssue(currentOrgId, issueId);
    // Resolving a conflict/stale/missing issue can change the risk score --
    // reload the whole dashboard so every card reflects the new state.
    loadDashboard();
  };

  const openCompare = () => {
    setShowCompare(true);
    setCompareError(null);
    setCompareData(null);
    api.compare()
      .then(setCompareData)
      .catch((e) => setCompareError(e.detail || e.message));
  };

  const toggleCompare = () => {
    if (showCompare) setShowCompare(false);
    else openCompare();
  };

  const filteredAssets = useMemo(() => {
    if (!dashboard.assets) return dashboard.assets;
    const q = searchQuery.trim().toLowerCase();
    if (!q) return dashboard.assets;
    return dashboard.assets.filter(
      (a) =>
        a.display_name.toLowerCase().includes(q) ||
        a.zone.toLowerCase().includes(q) ||
        a.asset_type.toLowerCase().includes(q)
    );
  }, [dashboard.assets, searchQuery]);

  if (bootstrapping) {
    return <div className="boot-screen">Loading…</div>;
  }

  if (!account) {
    return (
      <div className="boot-screen">
        {authError ? `Could not sign in: ${authError}` : "Loading…"}
      </div>
    );
  }

  return (
    <div className="app-shell">
      <Sidebar
        showControls={!!me?.capabilities?.technical_drilldown}
        onCompareClick={me?.capabilities?.cross_org ? toggleCompare : null}
        onExitCompare={() => setShowCompare(false)}
        showCompare={showCompare}
        openIssues={dashboard.summary?.open_data_quality_issues}
        onReviewIssues={() => scrollToSection("section-dataquality")}
      />

      <div className="app-body">
        <IdentityBar
          account={account}
          personas={DEMO_PERSONAS}
          onSwitchPersona={handleSwitchPersona}
          orgs={orgs}
          currentOrgId={currentOrgId}
          onOrgChange={setCurrentOrgId}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
        />

        <main className="app-main">
          {orgs.length === 0 && (
            <div className="error-state">
              This account has no plants assigned yet. Access must be granted explicitly — there is no default
              organization.
            </div>
          )}

          {showCompare ? (
            <ComparePanel data={compareData} error={compareError} />
          ) : (
            <>
              {dashboardLoading && <div className="empty-state">Loading dashboard…</div>}
              {dashboardError && !dashboardLoading && <div className="error-state">{dashboardError}</div>}

              {!dashboardLoading && !dashboardError && dashboard.summary && (
                <div className="workspace">
                  <div className="col-main">
                    <div id="section-overview">
                      <SummaryBanner summary={dashboard.summary} orgName={currentOrgName} />
                    </div>

                    <div className="split-row">
                      {/* Plant Manager / External Auditor don't get the
                          control-by-control breakdown -- they already have the
                          business-framed answer in the hero above. */}
                      {me?.capabilities?.technical_drilldown && (
                        <div id="section-controls">
                          <ControlLeaderboard data={dashboard.controls} onSelectControl={openControl} />
                        </div>
                      )}
                      <RiskSummaryCards summary={dashboard.summary} role={me?.role} />
                    </div>

                    <div id="section-map">
                      <MapPanel orgs={dashboard.orgs} currentOrgId={currentOrgId} onSelectOrg={setCurrentOrgId} />
                    </div>

                    <div id="section-assets">
                      <AssetList assets={filteredAssets} onSelectAsset={openAsset} />
                    </div>

                    <div id="section-dataquality">
                      <DataQualityPanel
                        issues={dashboard.dq}
                        canResolve={!!me?.capabilities?.can_resolve_issues}
                        onResolve={handleResolveIssue}
                      />
                    </div>
                  </div>

                  <aside className="col-side">
                    <div id="section-trend"><RiskTrendChart trend={dashboard.trend} /></div>
                    <div id="section-zones"><ZoneHeatmap zones={dashboard.zones} /></div>
                  </aside>
                </div>
              )}
            </>
          )}
        </main>
      </div>

      {selectedAssetId && (
        <AssetDrilldown
          asset={assetDetail}
          loading={assetLoading}
          error={assetError}
          onClose={() => { setSelectedAssetId(null); setAssetDetail(null); }}
        />
      )}
      {selectedControlId && (
        <ControlDrilldown
          control={controlDetail}
          loading={controlLoading}
          error={controlError}
          onClose={() => { setSelectedControlId(null); setControlDetail(null); }}
        />
      )}
    </div>
  );
}
