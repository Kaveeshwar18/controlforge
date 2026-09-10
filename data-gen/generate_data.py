"""
Synthetic multi-org dataset generator for the Control-Effectiveness Dashboard.

Seeds two manufacturing plants (+ a corporate wrapper org), demo user
identities with different roles/org access, and a realistic mix of assets,
controls, evidence, vulnerabilities, incidents and data-quality issues --
INCLUDING deliberately injected failure states (PRD section 7):
  1. missing telemetry (control marked completed, zero evidence rows)
  2. stale evidence (evidence exists but exceeds freshness threshold)
  3. conflicting source data (criticality disagreement between two sources)
  4. partial control rollout (in_progress with rollout_percentage < 100)
  5. regression (incident after a previously-verified control)
  6. unmonitored OT assets (has_telemetry=False)

Re-runnable: drops and recreates the sqlite db every run.
"""

import json
import os
import random
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.database import Base, engine, SessionLocal  # noqa: E402
from app import models, scoring, auth  # noqa: E402

random.seed(42)
TODAY = date.today()

# Local demo credential only -- see the note where accounts are seeded.
DEMO_PASSWORD = "controlforge-demo-2026"

ASSET_TYPES_OT = ["PLC", "HMI", "Historian", "SIS"]
ASSET_TYPES_IT = ["Workstation", "Server", "Switch"]
ZONES = ["OT", "IT", "DMZ"]

CONTROL_CATALOG = [
    ("Endpoint Detection & Response", "edr"),
    ("Patch Management Program", "patch_management"),
    ("IT/OT Network Segmentation", "network_segmentation"),
    ("Multi-Factor Authentication", "mfa"),
    ("Automated Backup & Recovery", "backup"),
    ("Application Allowlisting", "allowlisting"),
    ("Privileged Access Control", "access_control"),
]


def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def load_plant_config():
    """The plant network lives in plants.json, not in this file -- coordinates,
    site names and who can see what are data, so adding a site is an edit to
    that file rather than a code change."""
    path = os.path.join(os.path.dirname(__file__), "plants.json")
    with open(path) as f:
        return json.load(f)


def seed_orgs_and_users(db, config):
    corp_cfg = config["corporate"]
    db.add(models.Organization(
        id=corp_cfg["id"], name=corp_cfg["name"], org_type="corporate", parent_id=None
    ))

    for p in config["plants"]:
        db.add(models.Organization(
            id=p["id"], name=p["name"], org_type="plant", parent_id=corp_cfg["id"],
            city=p["city"], state=p["state"], lat=p["lat"], lon=p["lon"],
        ))
    db.commit()

    for u in config["users"]:
        db.add(models.User(id=u["id"], name=u["name"], role=u["role"], title=u.get("title")))
    db.commit()

    for u in config["users"]:
        for grant in u["orgs"]:
            db.add(models.UserOrgAccess(
                user_id=u["id"], org_id=grant["org"], redacted=grant.get("redacted", False)
            ))
    db.commit()

    # Login accounts for the demo personas. DEMO_PASSWORD is a well-known
    # seed value for local exploration only -- it exists so the different
    # roles can be signed into and compared. Never ship it anywhere real.
    for u in config["users"]:
        db.add(models.Account(
            username=u["id"],
            email=f"{u['id']}@example.com",
            password_hash=auth.hash_password(DEMO_PASSWORD),
            user_id=u["id"],
            created_at=datetime.utcnow(),
        ))
    db.commit()


def seed_assets(db, org_id: str, n_ot: int, n_it: int, n_dmz: int, conflict_indices, unmonitored_indices):
    assets = []
    ordinal = 0
    for zone, count, types in [("OT", n_ot, ASSET_TYPES_OT), ("IT", n_it, ASSET_TYPES_IT), ("DMZ", n_dmz, ASSET_TYPES_IT)]:
        for i in range(count):
            ordinal += 1
            atype = random.choice(types)
            base_crit = 5 if atype == "SIS" else (4 if atype in ("PLC", "HMI", "Historian") else random.choice([2, 3]))
            crit_a = base_crit
            crit_b = base_crit
            if ordinal in conflict_indices:
                crit_b = max(1, min(5, base_crit - random.choice([1, 2])))  # CMDB under-reports criticality

            impact = {
                "SIS": random.uniform(60, 100),
                "PLC": random.uniform(40, 80),
                "HMI": random.uniform(25, 55),
                "Historian": random.uniform(20, 45),
                "Server": random.uniform(15, 40),
                "Workstation": random.uniform(5, 20),
                "Switch": random.uniform(20, 50),
            }[atype]

            asset = models.Asset(
                id=f"{org_id}-A{ordinal:03d}",
                org_id=org_id,
                name=f"{org_id.title()}-{atype}-{zone}-{ordinal:03d}",
                asset_type=atype,
                zone=zone,
                criticality_scanner=crit_a,
                criticality_cmdb=crit_b,
                criticality_resolved=None,
                business_impact_weight=round(impact, 1),
                has_telemetry=(ordinal not in unmonitored_indices),
            )
            db.add(asset)
            assets.append(asset)
    db.commit()
    return assets


def seed_controls_and_evidence(db, org_id: str, assets, zones_present, missing_evidence_quota, stale_evidence_quota, partial_quota, maturity=0.5):
    controls = []
    idx = 0
    missing_left = missing_evidence_quota
    stale_left = stale_evidence_quota
    partial_left = partial_quota

    # zone-level controls (segmentation, backup) + a spread of per-asset controls
    for zone in zones_present:
        idx += 1
        name, ctype = "IT/OT Network Segmentation", "network_segmentation"
        status = "completed"
        c = models.Control(
            id=f"{org_id}-C{idx:03d}", org_id=org_id, name=f"{name} ({zone})", control_type=ctype,
            scope_type="zone", scope_asset_id=None, scope_zone=zone,
            status=status, rollout_percentage=100.0,
            planned_date=TODAY - timedelta(days=200), completion_date=TODAY - timedelta(days=140),
        )
        db.add(c)
        controls.append(c)

    for a in assets:
        applicable = random.sample(CONTROL_CATALOG, k=random.choice([1, 2, 2, 3]))
        for name, ctype in applicable:
            idx += 1
            # mature sites have finished more of their control programme
            roll = random.choices(
                ["completed", "in_progress", "planned"],
                weights=[0.40 + 0.40 * maturity, 0.40 - 0.20 * maturity, 0.20 - 0.20 * maturity],
            )[0]
            planned = TODAY - timedelta(days=random.randint(120, 220))
            if roll == "completed":
                completion = planned + timedelta(days=random.randint(20, 90))
                rollout_pct = 100.0
            elif roll == "in_progress":
                completion = None
                rollout_pct = round(random.uniform(30, 85), 0)
            else:
                completion = None
                rollout_pct = 0.0
                planned = TODAY + timedelta(days=random.randint(10, 60))

            c = models.Control(
                id=f"{org_id}-C{idx:03d}", org_id=org_id, name=name, control_type=ctype,
                scope_type="asset", scope_asset_id=a.id, scope_zone=None,
                status=roll, rollout_percentage=rollout_pct,
                planned_date=planned, completion_date=completion,
            )
            db.add(c)
            controls.append(c)
    db.commit()

    # Evidence: only for completed/zone controls, with deliberate failure injection.
    # Anchored to each control's own completion_date (not a fixed "today minus N"
    # window) so historical/baseline reconstruction sees evidence appear right
    # around when a control was actually finished, instead of every completed
    # control looking "unverified" until some arbitrary global cutoff.
    for c in controls:
        if c.status != "completed":
            continue
        if missing_left > 0 and random.random() < 0.35:
            missing_left -= 1
            continue  # FAILURE STATE 1: completed, zero evidence rows ever recorded

        completion = c.completion_date or (TODAY - timedelta(days=100))
        initial_ts = completion + timedelta(days=random.randint(1, 10))
        if initial_ts > TODAY:
            initial_ts = TODAY
        initial_dt = datetime.combine(initial_ts, datetime.min.time())
        source1 = random.choices(
            ["automated_scan", "third_party_audit", "manual_attestation"], weights=[0.55, 0.15, 0.3]
        )[0]
        db.add(models.Evidence(control_id=c.id, timestamp=initial_dt, source=source1, result="pass"))

        if stale_left > 0 and random.random() < 0.4:
            stale_left -= 1
            continue  # FAILURE STATE 2: verified once, never re-checked since -> reads stale/aging today

        # healthy case: an ongoing-monitoring re-verification keeps evidence fresh today
        recent_ts = TODAY - timedelta(days=random.randint(0, 10))
        if recent_ts > initial_ts:
            source2 = random.choices(
                ["automated_scan", "third_party_audit", "manual_attestation"], weights=[0.55, 0.15, 0.3]
            )[0]
            db.add(models.Evidence(
                control_id=c.id, timestamp=datetime.combine(recent_ts, datetime.min.time()), source=source2, result="pass"
            ))

    db.commit()
    return controls


def seed_vulnerabilities_and_incidents(db, org_id: str, assets, controls, maturity=0.5):
    vuln_idx = 0
    inc_idx = 0
    regression_asset = None
    verified_completed = [c for c in controls if c.status == "completed" and c.scope_asset_id]
    if verified_completed:
        regression_asset = random.choice(verified_completed)

    for a in assets:
        n_vulns = random.choices([0, 1, 2, 3, 4], weights=[0.1, 0.25, 0.3, 0.2, 0.15])[0]
        for _ in range(n_vulns):
            vuln_idx += 1
            # Most exposure is legacy debt already on the books before the
            # remediation window started (discovered >180d ago); a smaller
            # share is discovered during the window itself (ongoing scanning
            # keeps finding new things even while old ones get closed out) --
            # this is what keeps the baseline->measured curve from being a
            # suspiciously clean straight line while still trending down.
            if random.random() < 0.68:
                discovered = TODAY - timedelta(days=random.randint(181, 320))
            else:
                discovered = TODAY - timedelta(days=random.randint(1, 179))
            cvss = round(random.uniform(3.0, 9.8), 1)
            # mature sites have worked more of their backlog down
            status = random.choices(
                ["open", "mitigated", "accepted_risk"],
                weights=[0.42 - 0.28 * maturity, 0.48 + 0.28 * maturity, 0.10],
            )[0]
            resolved = None
            if status == "mitigated":
                # remediation catching up on legacy debt happens mostly within
                # the observation window, biased toward the more recent half
                candidate = discovered + timedelta(days=random.randint(60, 280))
                if candidate > TODAY:
                    # remediation hasn't actually finished yet -- leave it open
                    # rather than artificially clamping the date to "today",
                    # which would pile up a fake wave of same-day resolutions
                    status = "open"
                else:
                    resolved = candidate
            db.add(models.Vulnerability(
                id=f"{org_id}-V{vuln_idx:04d}", asset_id=a.id, cve_ref=f"CVE-2025-{random.randint(10000,99999)}",
                cvss=cvss, discovered_date=discovered, status=status, resolved_date=resolved,
            ))

        if random.random() < 0.18:
            inc_idx += 1
            detected = TODAY - timedelta(days=random.randint(1, 85))
            resolved = detected + timedelta(days=random.randint(1, 14)) if random.random() < 0.7 else None
            if resolved and resolved > TODAY:
                resolved = TODAY
            related = regression_asset.id if (regression_asset and regression_asset.scope_asset_id == a.id) else None
            db.add(models.Incident(
                id=f"{org_id}-I{inc_idx:03d}", asset_id=a.id,
                severity=random.choices(["low", "medium", "high", "critical"], weights=[0.3, 0.35, 0.25, 0.1])[0],
                detected_date=detected, resolved_date=resolved,
                root_cause=random.choice([
                    "Phishing-delivered malware on shared workstation",
                    "Exploited unpatched vulnerability",
                    "Misconfigured remote access into OT zone",
                    "Compromised vendor VPN credential",
                    "USB-borne malware on engineering laptop",
                ]),
                related_control_id=related,
            ))
    db.commit()
    return regression_asset


def seed_data_quality_issues(db, org_id: str, assets, controls, regression_asset):
    issue_idx = 0

    for a in assets:
        if a.criticality_scanner != a.criticality_cmdb:
            issue_idx += 1
            db.add(models.DataQualityIssue(
                id=f"{org_id}-DQ{issue_idx:03d}", org_id=org_id, issue_type="conflict", asset_id=a.id,
                description=(
                    f"Criticality mismatch for {a.name}: vulnerability scanner reports {a.criticality_scanner}, "
                    f"CMDB reports {a.criticality_cmdb}. Risk score uses the higher value until resolved."
                ),
                status="open", created_date=TODAY - timedelta(days=random.randint(5, 40)),
            ))
        if not a.has_telemetry:
            issue_idx += 1
            db.add(models.DataQualityIssue(
                id=f"{org_id}-DQ{issue_idx:03d}", org_id=org_id, issue_type="missing_feed", asset_id=a.id,
                description=f"{a.name} has no monitoring agent or telemetry feed configured -- risk cannot be independently verified.",
                status="open", created_date=TODAY - timedelta(days=random.randint(30, 120)),
            ))

    as_of_dt = datetime.combine(TODAY, datetime.min.time())
    for c in controls:
        if c.status != "completed":
            continue
        ev = scoring.latest_evidence_state(db, c.id, as_of_dt)
        if ev.freshness == "missing":
            issue_idx += 1
            db.add(models.DataQualityIssue(
                id=f"{org_id}-DQ{issue_idx:03d}", org_id=org_id, issue_type="missing_feed", control_id=c.id,
                description=f"Control '{c.name}' is marked completed but has no verification evidence on file.",
                status="open", created_date=TODAY - timedelta(days=random.randint(5, 30)),
            ))
        elif ev.freshness == "stale":
            issue_idx += 1
            db.add(models.DataQualityIssue(
                id=f"{org_id}-DQ{issue_idx:03d}", org_id=org_id, issue_type="stale_evidence", control_id=c.id,
                description=f"Verification evidence for '{c.name}' is older than the freshness threshold; confidence downgraded.",
                status="open", created_date=TODAY - timedelta(days=random.randint(1, 15)),
            ))

    if regression_asset:
        issue_idx += 1
        db.add(models.DataQualityIssue(
            id=f"{org_id}-DQ{issue_idx:03d}", org_id=org_id, issue_type="regression",
            asset_id=regression_asset.scope_asset_id, control_id=regression_asset.id,
            description=(
                f"Asset previously covered by verified control '{regression_asset.name}' has a new incident -- "
                "control effectiveness is under review, historical risk-reduction credit flagged."
            ),
            status="open", created_date=TODAY - timedelta(days=random.randint(1, 10)),
        ))
    db.commit()


def seed_risk_snapshots(db, org_id: str):
    # stop at 30 days out -- "today" is always computed live by the API so the
    # trend line reflects any data-quality fixes made through the UI
    for m in range(180, 0, -30):
        as_of = TODAY - timedelta(days=m)
        result = scoring.business_risk(db, org_id, as_of)
        db.add(models.RiskSnapshot(
            org_id=org_id, as_of_date=as_of, snapshot_type="historical",
            score_raw=result.raw_score, score_normalized=result.normalized_score,
            method_version=scoring.METHOD_VERSION,
        ))
    target = scoring.target_business_risk(db, org_id, TODAY)
    db.add(models.RiskSnapshot(
        org_id=org_id, as_of_date=TODAY, snapshot_type="target",
        score_raw=target.raw_score, score_normalized=target.normalized_score,
        method_version=scoring.METHOD_VERSION,
    ))
    db.commit()


def build_org(db, plant: dict):
    """`maturity` (0-1, from plants.json) is the one knob that makes sites
    differ: a mature site has more verified evidence and fewer unmonitored
    assets, so the map shows a genuine spread of risk rather than six
    identical pins."""
    org_id = plant["id"]
    maturity = plant.get("maturity", 0.5)
    n_ot = plant["assets"]["ot"]
    n_it = plant["assets"]["it"]
    n_dmz = plant["assets"]["dmz"]

    total = n_ot + n_it + n_dmz
    # weaker sites carry more conflicting records and more blind spots
    n_conflicts = max(1, round(4 - 3 * maturity))
    n_unmonitored = max(0, round(5 - 5 * maturity))

    conflict_indices = set(random.sample(range(1, total + 1), min(n_conflicts, total)))
    remaining = [i for i in range(1, total + 1) if i not in conflict_indices]
    unmonitored_indices = set(random.sample(remaining, min(n_unmonitored, len(remaining))))

    assets = seed_assets(db, org_id, n_ot, n_it, n_dmz, conflict_indices, unmonitored_indices)
    controls = seed_controls_and_evidence(
        db, org_id, assets, zones_present=["IT", "OT"],
        missing_evidence_quota=max(0, round(6 - 6 * maturity)),
        stale_evidence_quota=max(0, round(7 - 6 * maturity)),
        partial_quota=5,
        maturity=maturity,
    )
    regression_asset = seed_vulnerabilities_and_incidents(db, org_id, assets, controls, maturity=maturity)
    seed_data_quality_issues(db, org_id, assets, controls, regression_asset)
    seed_risk_snapshots(db, org_id)


def main():
    print("Resetting database...")
    reset_db()
    config = load_plant_config()
    db = SessionLocal()
    try:
        print(f"Seeding {config['corporate']['name']} & users...")
        seed_orgs_and_users(db, config)

        for plant in config["plants"]:
            print(f"Building {plant['name']} ({plant['city']}, {plant['state']})...")
            build_org(db, plant)

        print("Done.")
        print(f"  Plants: {len(config['plants'])}")
        print(f"  Assets: {db.query(models.Asset).count()}")
        print(f"  Controls: {db.query(models.Control).count()}")
        print(f"  Evidence rows: {db.query(models.Evidence).count()}")
        print(f"  Vulnerabilities: {db.query(models.Vulnerability).count()}")
        print(f"  Incidents: {db.query(models.Incident).count()}")
        print(f"  Data quality issues: {db.query(models.DataQualityIssue).count()}")
        print(f"  Risk snapshots: {db.query(models.RiskSnapshot).count()}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
