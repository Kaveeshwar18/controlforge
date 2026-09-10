const BASE_URL = "http://localhost:8000/api";
const TOKEN_KEY = "controlforge.token";

class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `Request failed (${status})`);
    this.status = status;
    this.detail = detail;
  }
}

// "Remember me" picks the backing store: localStorage survives closing the
// browser, sessionStorage is dropped when the tab closes.
let persistent = true;

export const tokenStore = {
  setPersistent: (value) => {
    persistent = !!value;
  },
  get: () => {
    try {
      return localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set: (token) => {
    try {
      // only ever one copy of the token, in whichever store was chosen
      localStorage.removeItem(TOKEN_KEY);
      sessionStorage.removeItem(TOKEN_KEY);
      (persistent ? localStorage : sessionStorage).setItem(TOKEN_KEY, token);
    } catch {
      /* private mode / storage blocked -- session just won't persist */
    }
  },
  clear: () => {
    try {
      localStorage.removeItem(TOKEN_KEY);
      sessionStorage.removeItem(TOKEN_KEY);
    } catch {
      /* ignore */
    }
  },
};

async function request(path, { method = "GET", body, auth = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth) {
    const token = tokenStore.get();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    let detail = null;
    try {
      const data = await res.json();
      // FastAPI validation errors come back as a list of field errors
      detail = Array.isArray(data.detail)
        ? data.detail.map((d) => d.msg).join("; ")
        : data.detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json();
}

export const api = {
  signup: (payload) => request("/auth/signup", { method: "POST", body: payload, auth: false }),
  login: (payload) => request("/auth/login", { method: "POST", body: payload, auth: false }),
  me: () => request("/auth/me"),

  capabilities: () => request("/me"),
  listOrgs: () => request("/orgs"),
  riskSummary: (orgId) => request(`/orgs/${orgId}/risk-summary`),
  riskTrend: (orgId) => request(`/orgs/${orgId}/risk-trend`),
  zones: (orgId) => request(`/orgs/${orgId}/zones`),
  controlLeaderboard: (orgId) => request(`/orgs/${orgId}/controls`),
  topAssets: (orgId) => request(`/orgs/${orgId}/assets`),
  assetDetail: (orgId, assetId) => request(`/orgs/${orgId}/assets/${assetId}`),
  controlDetail: (orgId, controlId) => request(`/orgs/${orgId}/controls/${controlId}`),
  dataQuality: (orgId) => request(`/orgs/${orgId}/data-quality`),
  resolveIssue: (orgId, issueId) =>
    request(`/orgs/${orgId}/data-quality/${issueId}/resolve`, { method: "POST" }),
  compare: () => request(`/compare`),
};

export { ApiError };
