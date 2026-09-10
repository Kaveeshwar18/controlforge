from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, scoring
from ..database import get_db
from ..rbac import get_identity, Identity, require_org_access, is_redacted

router = APIRouter(tags=["assets"])


def _display_name(identity: Identity, org_id: str, asset: models.Asset, ordinal: int) -> str:
    if is_redacted(identity, org_id):
        return f"{asset.asset_type}-{asset.zone}-Unit{ordinal}"
    return asset.name


@router.get("/orgs/{org_id}/assets")
def top_risk_assets(org_id: str, identity: Identity = Depends(get_identity), db: Session = Depends(get_db)):
    require_org_access(identity, org_id)
    today = date.today()
    result = scoring.business_risk(db, org_id, today)
    assets = {a.id: a for a in db.query(models.Asset).filter(models.Asset.org_id == org_id).all()}

    rows = []
    for i, (asset_id, (r, weighted)) in enumerate(result.asset_results.items(), start=1):
        a = assets[asset_id]
        rows.append({
            # asset_id stays the real key even in redacted views -- it's an
            # opaque lookup token the UI never displays, only display_name is
            # shown to the user. Redacting it too would break drill-down.
            "asset_id": asset_id,
            "display_name": _display_name(identity, org_id, a, i),
            "zone": a.zone,
            "asset_type": a.asset_type,
            "weighted_risk": round(weighted, 1),
            "criticality_conflict": r.criticality_conflict,
            "missing_telemetry": r.missing_telemetry,
        })
    rows.sort(key=lambda x: x["weighted_risk"], reverse=True)
    return rows[:25]


@router.get("/orgs/{org_id}/assets/{asset_id}")
def asset_drilldown(org_id: str, asset_id: str, identity: Identity = Depends(get_identity), db: Session = Depends(get_db)):
    require_org_access(identity, org_id)
    asset = db.query(models.Asset).filter(models.Asset.id == asset_id, models.Asset.org_id == org_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    today = date.today()
    r = scoring.asset_risk(db, asset, today)
    redacted = is_redacted(identity, org_id)

    base = {
        "asset_id": asset_id if not redacted else "REDACTED",
        "display_name": _display_name(identity, org_id, asset, 1),
        "zone": asset.zone,
        "asset_type": asset.asset_type,
        "criticality_used": r.criticality_used,
        "criticality_conflict": r.criticality_conflict,
        "missing_telemetry": r.missing_telemetry,
        "weighted_risk": round(r.raw_score * asset.business_impact_weight, 1),
    }

    if not identity.caps["technical_drilldown"]:
        # Plant Manager / External Auditor: business summary only, no raw CVE/evidence tables
        base["controls_summary"] = {
            "applicable": len(r.controls),
            "verified": sum(1 for c in r.controls if c.evidence.verified),
            "unverified_or_missing": sum(1 for c in r.controls if not c.evidence.verified),
        }
        vuln_count = db.query(models.Vulnerability).filter(
            models.Vulnerability.asset_id == asset_id, models.Vulnerability.status == "open"
        ).count()
        base["open_exposure_count"] = vuln_count
        return base

    # CISO / OT Engineer / Corp Admin: full technical drilldown
    vulns = db.query(models.Vulnerability).filter(models.Vulnerability.asset_id == asset_id).all()
    incidents = db.query(models.Incident).filter(models.Incident.asset_id == asset_id).all()

    base["controls"] = [
        {
            "control_id": c.control_id, "name": c.name, "status": c.status,
            "rollout_percentage": c.rollout_percentage,
            "effectiveness": round(c.effectiveness, 2),
            "evidence": {
                "has_evidence": c.evidence.has_evidence,
                "freshness": c.evidence.freshness,
                "source": c.evidence.source,
                "confidence": c.evidence.confidence,
                "verified": c.evidence.verified,
            },
        }
        for c in r.controls
    ]
    base["vulnerabilities"] = [
        {
            "id": v.id, "cve_ref": v.cve_ref, "cvss": v.cvss, "status": v.status,
            "discovered_date": str(v.discovered_date), "resolved_date": str(v.resolved_date) if v.resolved_date else None,
        }
        for v in vulns
    ]
    base["incidents"] = [
        {
            "id": i.id, "severity": i.severity, "detected_date": str(i.detected_date),
            "resolved_date": str(i.resolved_date) if i.resolved_date else None,
            "root_cause": i.root_cause, "related_control_id": i.related_control_id,
        }
        for i in incidents
    ]
    return base
