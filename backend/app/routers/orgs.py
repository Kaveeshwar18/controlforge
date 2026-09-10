from datetime import date, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, scoring
from ..database import get_db
from ..rbac import get_identity, Identity, is_redacted

router = APIRouter(tags=["orgs"])


@router.get("/orgs")
def list_accessible_orgs(identity: Identity = Depends(get_identity), db: Session = Depends(get_db)):
    """Only orgs this identity has been granted access to are ever returned --
    a Plant Manager scoped to one plant will not see other orgs exist at all.
    Plant-type orgs include their live risk score and coordinates so the
    network map can plot and color a real pin per facility."""
    orgs = db.query(models.Organization).filter(models.Organization.id.in_(identity.accessible_org_ids)).all()
    today = date.today()
    out = []
    for o in orgs:
        entry = {
            "id": o.id,
            "name": o.name,
            "org_type": o.org_type,
            "redacted": is_redacted(identity, o.id),
            "city": o.city,
            "state": o.state,
            "lat": o.lat,
            "lon": o.lon,
        }
        if o.org_type == "plant" and o.lat is not None:
            entry.update(_plant_metrics(db, o.id, today))
        out.append(entry)
    return out


BASELINE_WINDOW_DAYS = 180
CRITICAL_THRESHOLD = 4  # criticality 4-5 counts as a critical asset

# Banding for the map marker colour. Fixed (not relative to the current best
# and worst site) so a plant's colour only changes when that plant changes --
# it should not turn red because a sister site improved.
RISK_BAND_HIGH = 9.0
RISK_BAND_ELEVATED = 6.0


def risk_level(score: float) -> str:
    if score >= RISK_BAND_HIGH:
        return "high"
    if score >= RISK_BAND_ELEVATED:
        return "elevated"
    return "low"


def _plant_metrics(db: Session, org_id: str, today: date) -> dict:
    """Everything a map marker needs, in one pass.

    Deliberately uses the cheap scoring calls rather than
    compute_attribution(): the per-control counterfactual is far too
    expensive to run for every plant on every dashboard load, and the map
    only needs site-level totals. Drilling into a plant still gets the full
    attribution via the normal risk-summary endpoint.
    """
    baseline_date = today - timedelta(days=BASELINE_WINDOW_DAYS)
    measured = scoring.business_risk(db, org_id, today)
    baseline = scoring.business_risk(db, org_id, baseline_date)

    reduction_pct = (
        round((baseline.raw_score - measured.raw_score) / baseline.raw_score * 100, 1)
        if baseline.raw_score else 0.0
    )

    assets = db.query(models.Asset).filter(models.Asset.org_id == org_id).all()
    asset_ids = [a.id for a in assets]
    critical_assets = sum(
        1 for a in assets
        if max(a.criticality_scanner or 0, a.criticality_cmdb or 0) >= CRITICAL_THRESHOLD
    )
    unmonitored = sum(1 for a in assets if not a.has_telemetry)

    open_vulns = db.query(models.Vulnerability).filter(
        models.Vulnerability.asset_id.in_(asset_ids),
        models.Vulnerability.status == "open",
    ).count() if asset_ids else 0

    open_incidents = db.query(models.Incident).filter(
        models.Incident.asset_id.in_(asset_ids),
        models.Incident.resolved_date.is_(None),
    ).count() if asset_ids else 0

    # average confidence-weighted control effectiveness across monitored assets
    effs = [
        r.control_effect_avg
        for r, _weighted in measured.asset_results.values()
        if not r.missing_telemetry
    ]
    control_effectiveness = round(sum(effs) / len(effs) * 100, 1) if effs else 0.0

    return {
        "measured_score": round(measured.normalized_score, 1),
        "risk_level": risk_level(measured.normalized_score),
        "baseline_score": round(baseline.normalized_score, 1),
        "reduction_pct": reduction_pct,
        "asset_count": len(assets),
        "critical_assets": critical_assets,
        "unmonitored_assets": unmonitored,
        "open_vulnerabilities": open_vulns,
        "open_incidents": open_incidents,
        "control_effectiveness": control_effectiveness,
    }


@router.get("/me")
def whoami(identity: Identity = Depends(get_identity)):
    return {
        "id": identity.user.id,
        "name": identity.user.name,
        "role": identity.role,
        "capabilities": identity.caps,
        "accessible_org_ids": sorted(identity.accessible_org_ids),
    }
