from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, scoring
from ..database import get_db
from ..rbac import get_identity, Identity, require_org_access, is_redacted

router = APIRouter(tags=["controls"])


@router.get("/orgs/{org_id}/controls/{control_id}")
def control_drilldown(org_id: str, control_id: str, identity: Identity = Depends(get_identity), db: Session = Depends(get_db)):
    require_org_access(identity, org_id)
    control = db.query(models.Control).filter(models.Control.id == control_id, models.Control.org_id == org_id).first()
    if not control:
        raise HTTPException(status_code=404, detail="Control not found")

    today = date.today()
    as_of_dt = datetime.combine(today, datetime.min.time())
    ev = scoring.latest_evidence_state(db, control_id, as_of_dt)

    base = {
        "control_id": control_id,
        "name": control.name,
        "control_type": control.control_type,
        "status": control.status,
        "rollout_percentage": control.rollout_percentage,
        "planned_date": str(control.planned_date) if control.planned_date else None,
        "completion_date": str(control.completion_date) if control.completion_date else None,
        "evidence_state": {
            "has_evidence": ev.has_evidence,
            "freshness": ev.freshness,
            "confidence": ev.confidence,
            "verified": ev.verified,
        },
    }

    if not identity.caps["technical_drilldown"]:
        # External Auditor: "evidence package" -- verification status only, no raw evidence log
        base["evidence_package_statement"] = (
            "Independently verified" if ev.verified else
            "Not independently verified as of the report date" if ev.has_evidence else
            "No verification evidence on file"
        )
        return base

    all_evidence = db.query(models.Evidence).filter(models.Evidence.control_id == control_id).order_by(
        models.Evidence.timestamp.desc()
    ).all()
    base["evidence_log"] = [
        {"timestamp": e.timestamp.isoformat(), "source": e.source, "result": e.result} for e in all_evidence
    ]
    return base
