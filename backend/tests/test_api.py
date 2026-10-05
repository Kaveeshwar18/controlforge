"""End-to-end API tests against the seeded dataset: authentication, RBAC
scoping and redaction (PRD section 6), and the engineer's resolve action
actually changing what every role sees next.

Everything here goes through HTTP with a real signed token -- these are the
checks that would catch a permission only being hidden in the UI.
"""

import pytest


# ---- authentication ------------------------------------------------------------

def test_no_token_is_rejected(client):
    assert client.get("/api/orgs").status_code == 401


def test_tampered_token_is_rejected(client, login):
    headers = login("sarah.chen")
    bad = {"Authorization": headers["Authorization"][:-4] + "abcd"}
    assert client.get("/api/orgs", headers=bad).status_code == 401


def test_wrong_password_gives_the_same_vague_error_as_unknown_user(client):
    a = client.post("/api/auth/login", json={"identifier": "sarah.chen", "password": "wrong-password"})
    b = client.post("/api/auth/login", json={"identifier": "nobody.here", "password": "wrong-password"})
    assert a.status_code == b.status_code == 401
    assert a.json()["detail"] == b.json()["detail"]


# ---- org scoping -----------------------------------------------------------------

def test_plant_manager_only_sees_their_own_plant_exists(client, login):
    orgs = client.get("/api/orgs", headers=login("miguel.alvarez")).json()
    assert [o["id"] for o in orgs] == ["chennai"]


def test_plant_manager_gets_explicit_403_for_another_plant(client, login):
    r = client.get("/api/orgs/pune/risk-summary", headers=login("miguel.alvarez"))
    assert r.status_code == 403
    assert "PLANT_MANAGER" in r.json()["detail"]  # a reason, not a bare 403


@pytest.mark.parametrize("path", ["risk-summary", "risk-trend", "zones", "controls", "assets", "data-quality", "feeds"])
def test_every_org_endpoint_enforces_scoping(client, login, path):
    r = client.get(f"/api/orgs/mumbai/{path}", headers=login("priya.nair"))
    assert r.status_code == 403


def test_corp_admin_sees_all_six_plants(client, login):
    orgs = client.get("/api/orgs", headers=login("amara.diallo")).json()
    assert len([o for o in orgs if o["org_type"] == "plant"]) == 6


def test_cross_org_compare_is_admin_only(client, login):
    assert client.get("/api/compare", headers=login("sarah.chen")).status_code == 403
    r = client.get("/api/compare", headers=login("amara.diallo"))
    assert r.status_code == 200 and len(r.json()) == 6


# ---- role-based field redaction -----------------------------------------------------

def test_auditor_sees_redacted_asset_names(client, login):
    assets = client.get("/api/orgs/chennai/assets", headers=login("james.cole")).json()
    assert assets, "auditor should still see the asset list"
    for a in assets:
        assert not a["display_name"].lower().startswith("chennai-")
        assert "-Unit" in a["display_name"]


def test_auditor_can_still_drill_down_despite_redaction(client, login):
    """Regression test for the bug in failure-mode-analysis.md section A."""
    headers = login("james.cole")
    first = client.get("/api/orgs/chennai/assets", headers=headers).json()[0]
    r = client.get(f"/api/orgs/chennai/assets/{first['asset_id']}", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["asset_id"] == "REDACTED"
    assert "vulnerabilities" not in body and "controls_summary" in body


def test_auditor_gets_evidence_statement_not_raw_log(client, login):
    headers = login("james.cole")
    control_id = client.get("/api/orgs/chennai/controls", headers=login("sarah.chen")).json()["controls"][0]["control_id"]
    body = client.get(f"/api/orgs/chennai/controls/{control_id}", headers=headers).json()
    assert "evidence_package_statement" in body
    assert "evidence_log" not in body


def test_plant_manager_gets_business_summary_not_cves(client, login):
    headers = login("miguel.alvarez")
    asset_id = client.get("/api/orgs/chennai/assets", headers=headers).json()[0]["asset_id"]
    body = client.get(f"/api/orgs/chennai/assets/{asset_id}", headers=headers).json()
    assert "vulnerabilities" not in body and "controls" not in body
    assert "open_exposure_count" in body


def test_engineer_gets_full_technical_drilldown(client, login):
    headers = login("priya.nair")
    asset_id = client.get("/api/orgs/chennai/assets", headers=headers).json()[0]["asset_id"]
    body = client.get(f"/api/orgs/chennai/assets/{asset_id}", headers=headers).json()
    assert {"controls", "vulnerabilities", "incidents"} <= body.keys()


def test_auditor_feed_view_hides_internal_error_detail(client, login):
    feeds = client.get("/api/orgs/pune/feeds", headers=login("james.cole")).json()
    assert any(f["state"] == "stale" for f in feeds)  # still told the data is stale
    assert all(f["last_error"] is None for f in feeds)  # but not the internal reason
    eng = client.get("/api/orgs/pune/feeds", headers=login("ravi.krishnan")).json()
    assert any(f["last_error"] for f in eng)


# ---- freshness surfaced in the summary --------------------------------------------------

def test_summary_reports_degraded_feeds(client, login):
    s = client.get("/api/orgs/pune/risk-summary", headers=login("ravi.krishnan")).json()
    assert s["degraded_feeds"] == ["vuln_scanner"]
    assert s["measured_score_best_case"] <= s["measured_score"] <= s["measured_score_worst_case"]


def test_healthy_plant_reports_no_degraded_feeds(client, login):
    s = client.get("/api/orgs/bengaluru/risk-summary", headers=login("dev.patel")).json()
    assert s["degraded_feeds"] == []


# ---- the resolve workflow: one role's action changes everyone's view ---------------------

def test_only_engineer_or_admin_can_resolve(client, login, fresh_seed):
    issue = client.get("/api/orgs/chennai/data-quality", headers=login("sarah.chen")).json()[0]
    for who in ("sarah.chen", "miguel.alvarez", "james.cole"):
        r = client.post(f"/api/orgs/chennai/data-quality/{issue['id']}/resolve", headers=login(who))
        assert r.status_code == 403, who


def test_resolving_a_conflict_clears_it_for_every_role(client, login, fresh_seed):
    eng = login("priya.nair")
    conflict = next(i for i in client.get("/api/orgs/chennai/data-quality", headers=eng).json()
                    if i["issue_type"] == "conflict" and i["status"] == "open")
    asset_id = conflict["asset_id"]
    assert client.get(f"/api/orgs/chennai/assets/{asset_id}", headers=login("miguel.alvarez")).json()["criticality_conflict"]

    r = client.post(f"/api/orgs/chennai/data-quality/{conflict['id']}/resolve", headers=eng)
    assert r.status_code == 200

    for who in ("priya.nair", "miguel.alvarez", "sarah.chen"):
        body = client.get(f"/api/orgs/chennai/assets/{asset_id}", headers=login(who)).json()
        assert body["criticality_conflict"] is False, who


def test_resolving_a_feed_outage_narrows_the_worst_case(client, login, fresh_seed):
    eng = login("ravi.krishnan")
    before = client.get("/api/orgs/pune/risk-summary", headers=eng).json()
    outage = next(i for i in client.get("/api/orgs/pune/data-quality", headers=eng).json()
                  if i["issue_type"] == "feed_outage")
    assert client.post(f"/api/orgs/pune/data-quality/{outage['id']}/resolve", headers=eng).status_code == 200
    after = client.get("/api/orgs/pune/risk-summary", headers=eng).json()

    assert after["degraded_feeds"] == []
    assert after["measured_score_worst_case"] < before["measured_score_worst_case"]
    assert after["measured_score"] == before["measured_score"]  # centre doesn't move, only the band


def test_resolving_missing_evidence_increases_credited_reduction(client, login, fresh_seed):
    eng = login("ravi.krishnan")
    before = client.get("/api/orgs/pune/risk-summary", headers=eng).json()
    missing = next(i for i in client.get("/api/orgs/pune/data-quality", headers=eng).json()
                   if i["issue_type"] == "missing_feed" and i["control_id"])
    client.post(f"/api/orgs/pune/data-quality/{missing['id']}/resolve", headers=eng)
    after = client.get("/api/orgs/pune/risk-summary", headers=eng).json()
    assert after["measured_score"] <= before["measured_score"]
    assert after["reduction_pct"] >= before["reduction_pct"]


def test_resolving_twice_is_rejected(client, login, fresh_seed):
    eng = login("priya.nair")
    issue = next(i for i in client.get("/api/orgs/chennai/data-quality", headers=eng).json() if i["status"] == "open")
    assert client.post(f"/api/orgs/chennai/data-quality/{issue['id']}/resolve", headers=eng).status_code == 200
    assert client.post(f"/api/orgs/chennai/data-quality/{issue['id']}/resolve", headers=eng).status_code == 400


def test_auditor_summary_also_hides_feed_error_detail(client, login):
    """The summary embeds feed health too -- redaction must apply there, not
    only on the dedicated /feeds endpoint."""
    s = client.get("/api/orgs/pune/risk-summary", headers=login("james.cole")).json()
    assert s["degraded_feeds"] == ["vuln_scanner"]
    assert all(f["last_error"] is None for f in s["feed_health"])


def test_summary_separates_control_effect_from_total_change(client, login):
    s = client.get("/api/orgs/chennai/risk-summary", headers=login("sarah.chen")).json()
    assert s["controls_reduction_worst_pct"] <= s["controls_reduction_pct"] <= s["controls_reduction_best_pct"]
    assert isinstance(s["reportable"], bool)
