from datetime import date, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, scoring
from ..database import get_db
from ..rbac import get_identity, Identity, require_org_access

router = APIRouter(tags=["risk"])

OBSERVATION_WINDOW_DAYS = 180


def _baseline_date() -> date:
    return date.today() - timedelta(days=OBSERVATION_WINDOW_DAYS)


def _freshness_overview(db: Session, org_id: str, as_of) -> dict:
    """Evidence freshness only means something for controls that are supposed
    to HAVE evidence -- i.e. status == completed. An in_progress or planned
    control showing 'missing' isn't a failure state, it's just not done yet,
    so it's excluded here rather than inflating the missing-evidence count."""
    from datetime import datetime
    counts = {"fresh": 0, "aging": 0, "stale": 0, "missing": 0}
    controls = db.query(models.Control).filter(
        models.Control.org_id == org_id, models.Control.status == "completed"
    ).all()
    as_of_dt = datetime.combine(as_of, datetime.min.time())
    for c in controls:
        ev = scoring.latest_evidence_state(db, c.id, as_of_dt)
        counts[ev.freshness] += 1
    unmonitored = db.query(models.Asset).filter(
        models.Asset.org_id == org_id, models.Asset.has_telemetry == False  # noqa: E712
    ).count()
    total_assets = db.query(models.Asset).filter(models.Asset.org_id == org_id).count()
    return {
        "control_evidence": counts,
        "completed_controls_checked": len(controls),
        "unmonitored_assets": unmonitored,
        "total_assets": total_assets,
    }


@router.get("/orgs/{org_id}/risk-summary")
def risk_summary(org_id: str, identity: Identity = Depends(get_identity), db: Session = Depends(get_db)):
    require_org_access(identity, org_id)
    today = date.today()
    baseline_date = _baseline_date()
    attribution = scoring.compute_attribution(db, org_id, baseline_date, today)

    open_issues = db.query(models.DataQualityIssue).filter(
        models.DataQualityIssue.org_id == org_id, models.DataQualityIssue.status == "open"
    ).count()

    result = {
        "org_id": org_id,
        "method_version": attribution.method_version,
        "as_of_date": str(today),
        "baseline_date": str(baseline_date),
        "baseline_score": round(attribution.baseline.normalized_score, 1),
        "target_score": round(attribution.target.normalized_score, 1),
        "measured_score": round(attribution.measured_point.normalized_score, 1),
        # named by what the number IS (best/worst case), not by which internal
        # confidence-bias parameter produced it -- best_case is always the
        # lower (less risky) number, worst_case always the higher one
        "measured_score_best_case": round(attribution.measured_high.normalized_score, 1),
        "measured_score_worst_case": round(attribution.measured_low.normalized_score, 1),
        "reduction_pct": attribution.reduction_pct,
        "pct_of_target_achieved": attribution.pct_of_target_achieved,
        "open_data_quality_issues": open_issues,
        "freshness_overview": _freshness_overview(db, org_id, today),
    }
    return result


@router.get("/orgs/{org_id}/risk-trend")
def risk_trend(org_id: str, identity: Identity = Depends(get_identity), db: Session = Depends(get_db)):
    require_org_access(identity, org_id)
    rows = db.query(models.RiskSnapshot).filter(
        models.RiskSnapshot.org_id == org_id, models.RiskSnapshot.snapshot_type == "historical"
    ).order_by(models.RiskSnapshot.as_of_date).all()
    points = [{"date": str(r.as_of_date), "score": round(r.score_normalized, 1)} for r in rows]

    today = date.today()
    measured = scoring.business_risk(db, org_id, today)
    points.append({"date": str(today), "score": round(measured.normalized_score, 1)})

    target_row = db.query(models.RiskSnapshot).filter(
        models.RiskSnapshot.org_id == org_id, models.RiskSnapshot.snapshot_type == "target"
    ).first()
    return {
        "history": points,
        "target_score": round(target_row.score_normalized, 1) if target_row else None,
    }


@router.get("/orgs/{org_id}/zones")
def risk_by_zone(org_id: str, identity: Identity = Depends(get_identity), db: Session = Depends(get_db)):
    require_org_access(identity, org_id)
    today = date.today()
    result = scoring.business_risk(db, org_id, today)
    zones: dict[str, dict] = {}
    for asset_id, (r, weighted) in result.asset_results.items():
        asset = db.query(models.Asset).filter(models.Asset.id == asset_id).first()
        z = zones.setdefault(asset.zone, {"zone": asset.zone, "raw_total": 0.0, "asset_count": 0, "unmonitored": 0})
        z["raw_total"] += weighted
        z["asset_count"] += 1
        if r.missing_telemetry:
            z["unmonitored"] += 1
    ref = scoring.max_reference_score(db, org_id)
    out = []
    for z in zones.values():
        out.append({
            "zone": z["zone"],
            "risk_index": round(min(100.0, z["raw_total"] / ref * 100.0), 1),
            "asset_count": z["asset_count"],
            "unmonitored_assets": z["unmonitored"],
        })
    out.sort(key=lambda x: x["risk_index"], reverse=True)
    return out


@router.get("/orgs/{org_id}/controls")
def control_leaderboard(org_id: str, identity: Identity = Depends(get_identity), db: Session = Depends(get_db)):
    require_org_access(identity, org_id)
    today = date.today()
    baseline_date = _baseline_date()
    attribution = scoring.compute_attribution(db, org_id, baseline_date, today)
    redacted = org_id in identity.redacted_org_ids

    out = []
    for pc in attribution.per_control:
        item = {
            "control_id": pc.control_id,
            "name": pc.name,
            "control_type": pc.control_type,
            "status": pc.status,
            "risk_reduction_attributed": pc.delta_point,
            "risk_reduction_low": pc.delta_low,
            "risk_reduction_high": pc.delta_high,
            "confidence_note": pc.confidence_note,
        }
        out.append(item)

    return {
        "controls": out,
        "residual_interaction_effect": attribution.residual,
    }
