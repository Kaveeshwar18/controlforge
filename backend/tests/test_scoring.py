"""Unit tests for the scoring engine's failure-state handling (PRD section 7).

Each test builds the smallest scenario that isolates one behaviour, so a
failure points at exactly one rule. Expected values come from the constants
in app/scoring.py, worked out by hand in the comments.
"""

from datetime import date, datetime, timedelta

import pytest

from app import models, scoring

TODAY = date.today()
NOW = datetime.combine(TODAY, datetime.min.time())


# ---- tiny scenario builders ------------------------------------------------

def make_org(db, org_id="t"):
    db.add(models.Organization(id=org_id, name="Test Plant", org_type="plant"))
    db.commit()
    return org_id


def make_asset(db, org_id="t", asset_id="t-A1", crit=(4, 4), impact=10.0, telemetry=True, zone="OT"):
    a = models.Asset(
        id=asset_id, org_id=org_id, name=asset_id, asset_type="PLC", zone=zone,
        criticality_scanner=crit[0], criticality_cmdb=crit[1], business_impact_weight=impact,
        has_telemetry=telemetry,
    )
    db.add(a)
    db.commit()
    return a


def make_control(db, asset, control_id="t-C1", status="completed", rollout=100.0, completed_days_ago=60):
    c = models.Control(
        id=control_id, org_id=asset.org_id, name=control_id, control_type="edr",
        scope_type="asset", scope_asset_id=asset.id, status=status, rollout_percentage=rollout,
        planned_date=TODAY - timedelta(days=completed_days_ago + 30),
        completion_date=(TODAY - timedelta(days=completed_days_ago)) if status == "completed" else None,
    )
    db.add(c)
    db.commit()
    return c


def add_evidence(db, control, days_ago, source="automated_scan", result="pass"):
    db.add(models.Evidence(control_id=control.id, timestamp=NOW - timedelta(days=days_ago), source=source, result=result))
    db.commit()


def add_vuln(db, asset, cvss=8.0, days_ago=10, vid="t-V1"):
    db.add(models.Vulnerability(
        id=vid, asset_id=asset.id, cve_ref="CVE-TEST", cvss=cvss,
        discovered_date=TODAY - timedelta(days=days_ago), status="open",
    ))
    db.commit()


def effectiveness(db, control, as_of=TODAY):
    ev = scoring.latest_evidence_state(db, control.id, datetime.combine(as_of, datetime.min.time()))
    return scoring.control_effectiveness(control, ev, as_of)


# ---- evidence freshness & confidence ----------------------------------------

@pytest.mark.parametrize("source,age,expected", [
    ("automated_scan", 0, "fresh"),
    ("automated_scan", 2, "fresh"),
    ("automated_scan", 3, "aging"),
    ("automated_scan", 14, "aging"),
    ("automated_scan", 15, "stale"),
    ("manual_attestation", 14, "fresh"),
    ("manual_attestation", 45, "aging"),
    ("manual_attestation", 46, "stale"),
])
def test_freshness_thresholds_are_source_specific(source, age, expected):
    assert scoring.freshness_state(NOW - timedelta(days=age), NOW, source) == expected


def test_completed_control_without_evidence_gets_zero_credit(db):
    """Failure state 1: 'completed' on paper, nothing proving it."""
    make_org(db)
    c = make_control(db, make_asset(db))
    assert effectiveness(db, c) == 0.0


def test_verified_evidence_gets_full_credit(db):
    make_org(db)
    c = make_control(db, make_asset(db))
    add_evidence(db, c, days_ago=1, source="automated_scan")
    assert effectiveness(db, c) == pytest.approx(1.0)  # verified weight 1.0 x fresh-automated 1.0


def test_self_attestation_earns_less_than_independent_verification(db):
    make_org(db)
    c = make_control(db, make_asset(db))
    add_evidence(db, c, days_ago=1, source="manual_attestation")
    # not "verified" -> completed weight 0.7, x fresh-manual confidence 0.7
    assert effectiveness(db, c) == pytest.approx(0.49)


def test_stale_evidence_is_discounted_not_zeroed(db):
    """Failure state 2: verified once, never re-checked."""
    make_org(db)
    c = make_control(db, make_asset(db))
    add_evidence(db, c, days_ago=30, source="automated_scan")
    # stale -> no longer counts as verified (0.7) x stale-automated 0.3
    assert effectiveness(db, c) == pytest.approx(0.21)


def test_partial_rollout_is_prorated(db):
    """Failure state 4: credit scales with rollout, not binary."""
    make_org(db)
    c = make_control(db, make_asset(db), status="in_progress", rollout=50.0)
    assert effectiveness(db, c) == pytest.approx(0.35)  # 0.7 x 50%


def test_evidence_recorded_after_the_scored_date_is_not_back_credited(db):
    """Evidence-time-awareness: a past score can't use proof that came later."""
    make_org(db)
    c = make_control(db, make_asset(db), completed_days_ago=60)
    add_evidence(db, c, days_ago=0)
    past = TODAY - timedelta(days=30)
    ev = scoring.latest_evidence_state(db, c.id, datetime.combine(past, datetime.min.time()))
    assert ev.freshness == "missing"
    assert effectiveness(db, c, as_of=past) == 0.0


# ---- asset-level failure states ----------------------------------------------

def test_unmonitored_asset_is_not_scored_as_safe(db):
    """Failure state 6: no telemetry must read as elevated risk, not zero."""
    make_org(db)
    blind = make_asset(db, asset_id="t-blind", telemetry=False, crit=(4, 4))
    seen = make_asset(db, asset_id="t-seen", telemetry=True, crit=(4, 4))  # no vulns on file
    blind_r = scoring.asset_risk(db, blind, TODAY)
    seen_r = scoring.asset_risk(db, seen, TODAY)
    assert blind_r.missing_telemetry is True
    assert blind_r.raw_score == pytest.approx(4 * scoring.UNMONITORED_EXPOSURE)  # crit x fixed elevated exposure
    assert seen_r.raw_score == 0.0
    assert blind_r.raw_score > seen_r.raw_score


def test_criticality_conflict_scores_conservatively(db):
    """Failure state 3: two sources disagree -> use the higher value, flag it."""
    make_org(db)
    a = make_asset(db, crit=(5, 3))
    add_vuln(db, a)
    r = scoring.asset_risk(db, a, TODAY)
    assert r.criticality_conflict is True
    assert r.criticality_used == 5


def test_resolved_conflict_clears_flag(db):
    make_org(db)
    a = make_asset(db, crit=(5, 3))
    a.criticality_resolved = 5
    db.commit()
    assert scoring.asset_risk(db, a, TODAY).criticality_conflict is False


@pytest.mark.parametrize("days_ago,factor", [(10, 1.0), (60, 1.3), (120, 1.6)])
def test_older_open_vulnerabilities_weigh_more(db, days_ago, factor):
    make_org(db)
    a = make_asset(db)
    add_vuln(db, a, cvss=10.0, days_ago=days_ago)
    assert scoring.exposure_factor(db, a.id, TODAY) == pytest.approx(factor)


def test_unresolved_incident_raises_risk(db):
    make_org(db)
    a = make_asset(db)
    add_vuln(db, a)
    before = scoring.asset_risk(db, a, TODAY).raw_score
    db.add(models.Incident(id="t-I1", asset_id=a.id, severity="high", detected_date=TODAY - timedelta(days=5)))
    db.commit()
    after = scoring.asset_risk(db, a, TODAY).raw_score
    assert after == pytest.approx(before * (1 + scoring.INCIDENT_WEIGHT))


# ---- source-feed outage (failure state 7) -------------------------------------

def make_feed(db, org_id, feed_type, hours_ago, interval):
    f = models.DataFeed(
        id=f"{org_id}-F-{feed_type}", org_id=org_id, feed_type=feed_type, name=feed_type,
        expected_interval_hours=interval,
        last_sync=None if hours_ago is None else datetime.now() - timedelta(hours=hours_ago),
    )
    db.add(f)
    db.commit()
    return f


@pytest.mark.parametrize("hours_ago,expected", [(1, "fresh"), (35, "fresh"), (60, "aging"), (100, "stale"), (None, "missing")])
def test_feed_state_thresholds(db, hours_ago, expected):
    make_org(db)
    f = make_feed(db, "t", "vuln_scanner", hours_ago, interval=24)
    assert scoring.feed_state(f, datetime.now()) == expected


def test_stale_scanner_widens_worst_case_but_not_point_estimate(db):
    make_org(db)
    a = make_asset(db)
    add_vuln(db, a, cvss=8.0)
    point_before = scoring.business_risk(db, "t", TODAY).raw_score
    worst_before = scoring.business_risk(db, "t", TODAY, confidence_bias="low").raw_score

    make_feed(db, "t", "vuln_scanner", hours_ago=200, interval=24)
    point_after = scoring.business_risk(db, "t", TODAY).raw_score
    worst_after = scoring.business_risk(db, "t", TODAY, confidence_bias="low").raw_score

    assert point_after == pytest.approx(point_before)
    assert worst_after == pytest.approx(worst_before * scoring.STALE_SCANNER_EXPOSURE_UPLIFT)


def test_cmdb_outage_is_flagged_but_does_not_move_the_score(db):
    make_org(db)
    a = make_asset(db)
    add_vuln(db, a)
    worst_before = scoring.business_risk(db, "t", TODAY, confidence_bias="low").raw_score
    make_feed(db, "t", "cmdb", hours_ago=2000, interval=168)
    health = scoring.feed_health(db, "t", datetime.now())
    assert health[0]["state"] == "stale" and health[0]["widens_worst_case"] is False
    assert scoring.business_risk(db, "t", TODAY, confidence_bias="low").raw_score == pytest.approx(worst_before)


# ---- whole-engine invariants on the seeded dataset -----------------------------

PLANTS = ["chennai", "coimbatore", "bengaluru", "hyderabad", "pune", "mumbai"]


@pytest.fixture(scope="module")
def seeded_db(seeded):
    from app.database import SessionLocal
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture(scope="module")
def attributions(seeded_db):
    baseline = TODAY - timedelta(days=180)
    return {p: scoring.compute_attribution(seeded_db, p, baseline, TODAY) for p in PLANTS}


@pytest.mark.parametrize("plant", PLANTS)
def test_confidence_band_brackets_the_point_estimate(attributions, plant):
    a = attributions[plant]
    best, point, worst = a.measured_high.raw_score, a.measured_point.raw_score, a.measured_low.raw_score
    assert best <= point + 1e-9 <= worst + 1e-9


@pytest.mark.parametrize("plant", PLANTS)
def test_target_is_never_worse_than_measured(attributions, plant):
    a = attributions[plant]
    assert a.target.raw_score <= a.measured_point.raw_score + 1e-9


@pytest.mark.parametrize("plant", PLANTS)
def test_unverified_controls_get_zero_attributed_credit(attributions, plant):
    for c in attributions[plant].per_control:
        if c.confidence_note.startswith("No verification"):
            assert c.delta_point == c.delta_low == c.delta_high == 0.0


def test_every_plant_has_a_method_version(attributions):
    assert all(a.method_version == scoring.METHOD_VERSION for a in attributions.values())


@pytest.mark.parametrize("plant", PLANTS)
def test_best_case_reduction_is_never_smaller_than_worst_case(attributions, plant):
    """Regression test: the fields used to be called reduction_low/high with
    'low' meaning the larger number, and the notebook reported them swapped."""
    a = attributions[plant]
    assert a.reduction_best_case >= a.reduction_point >= a.reduction_worst_case


# ---- method v1.1 behaviours ------------------------------------------------------

def test_failed_verification_earns_no_credit_even_when_recent(db):
    make_org(db)
    c = make_control(db, make_asset(db))
    add_evidence(db, c, days_ago=0, source="automated_scan", result="fail")
    ev = scoring.latest_evidence_state(db, c.id, NOW)
    assert ev.failed is True and ev.verified is False
    assert effectiveness(db, c) == 0.0


def test_worst_case_keeps_full_credit_for_verified_evidence(db):
    """v1.0 halved even fresh, independently verified evidence in the worst
    case, so the band widened as a plant added good controls."""
    make_org(db)
    a = make_asset(db)
    add_vuln(db, a)
    c = make_control(db, a)
    add_evidence(db, c, days_ago=1, source="automated_scan")
    point = scoring.business_risk(db, "t", TODAY).raw_score
    worst = scoring.business_risk(db, "t", TODAY, confidence_bias="low").raw_score
    assert worst == pytest.approx(point)


def test_worst_case_gives_self_attestation_no_credit(db):
    make_org(db)
    a = make_asset(db)
    add_vuln(db, a)
    c = make_control(db, a)
    add_evidence(db, c, days_ago=1, source="manual_attestation")
    r = scoring.asset_risk(db, a, TODAY, confidence_bias="low")
    assert r.control_effect_avg == 0.0


def test_unmonitored_asset_gets_an_uncertainty_band_not_a_point(db):
    """Total blindness must not produce a zero-width ("certain") band."""
    make_org(db)
    make_asset(db, telemetry=False)
    best = scoring.business_risk(db, "t", TODAY, confidence_bias="high").raw_score
    point = scoring.business_risk(db, "t", TODAY).raw_score
    worst = scoring.business_risk(db, "t", TODAY, confidence_bias="low").raw_score
    assert best < point < worst


@pytest.mark.parametrize("plant", PLANTS)
def test_control_attributable_reduction_is_bounded_and_ordered(attributions, plant):
    a = attributions[plant]
    assert 0.0 <= a.controls_reduction_worst_pct <= a.controls_reduction_pct <= a.controls_reduction_best_pct <= 100.0
