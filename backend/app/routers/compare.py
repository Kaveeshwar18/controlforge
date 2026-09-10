from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, scoring
from ..database import get_db
from ..rbac import get_identity, Identity

router = APIRouter(tags=["compare"])


@router.get("/compare")
def cross_org_comparison(identity: Identity = Depends(get_identity), db: Session = Depends(get_db)):
    """Cross-org comparison view -- only available to CORP_ADMIN. Every other
    role gets a 403 with an explicit reason, not a partial/empty result."""
    if not identity.caps["cross_org"]:
        raise HTTPException(
            status_code=403,
            detail=f"Cross-organization comparison is not available to role {identity.role}.",
        )
    today = date.today()
    baseline_date = today - timedelta(days=180)
    out = []
    orgs = db.query(models.Organization).filter(
        models.Organization.id.in_(identity.accessible_org_ids), models.Organization.org_type == "plant"
    ).all()
    for o in orgs:
        # This view only needs site-level totals, so it deliberately avoids
        # compute_attribution(): that runs a counterfactual re-score per
        # completed control and the per-control result would be discarded
        # here. Across a whole plant network that dominated the response time.
        measured = scoring.business_risk(db, o.id, today)
        baseline = scoring.business_risk(db, o.id, baseline_date)
        target = scoring.target_business_risk(db, o.id, today)

        reduction = baseline.raw_score - measured.raw_score
        achievable = baseline.raw_score - target.raw_score
        out.append({
            "org_id": o.id,
            "org_name": o.name,
            "measured_score": round(measured.normalized_score, 1),
            "baseline_score": round(baseline.normalized_score, 1),
            "reduction_pct": round(reduction / baseline.raw_score * 100, 1) if baseline.raw_score else 0.0,
            "pct_of_target_achieved": round(reduction / achievable * 100, 1) if achievable > 1e-9 else 0.0,
        })
    out.sort(key=lambda x: x["measured_score"], reverse=True)
    return out
