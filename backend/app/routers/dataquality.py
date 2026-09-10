from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..rbac import get_identity, Identity, require_org_access

router = APIRouter(tags=["data-quality"])


@router.get("/orgs/{org_id}/data-quality")
def list_data_quality_issues(org_id: str, identity: Identity = Depends(get_identity), db: Session = Depends(get_db)):
    require_org_access(identity, org_id)
    issues = db.query(models.DataQualityIssue).filter(models.DataQualityIssue.org_id == org_id).order_by(
        models.DataQualityIssue.status, models.DataQualityIssue.created_date.desc()
    ).all()
    return [
        {
            "id": i.id, "issue_type": i.issue_type, "asset_id": i.asset_id, "control_id": i.control_id,
            "description": i.description, "status": i.status,
            "created_date": str(i.created_date),
            "resolved_date": str(i.resolved_date) if i.resolved_date else None,
            "resolved_by": i.resolved_by,
        }
        for i in issues
    ]


@router.post("/orgs/{org_id}/data-quality/{issue_id}/resolve")
def resolve_data_quality_issue(
    org_id: str, issue_id: str, identity: Identity = Depends(get_identity), db: Session = Depends(get_db)
):
    """Only OT Engineer / Corp Admin can resolve. Resolving an issue doesn't
    just close a ticket -- it writes back to the underlying record the risk
    score is computed from, so the next read of risk-summary/leaderboard/zones
    reflects it immediately for every role. This is the interaction the PRD
    calls out explicitly: an engineer's action changes what everyone sees next.
    """
    require_org_access(identity, org_id)
    if not identity.caps["can_resolve_issues"]:
        raise HTTPException(
            status_code=403,
            detail=f"Role {identity.role} is not authorized to resolve data-quality issues.",
        )
    issue = db.query(models.DataQualityIssue).filter(
        models.DataQualityIssue.id == issue_id, models.DataQualityIssue.org_id == org_id
    ).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    if issue.status == "resolved":
        raise HTTPException(status_code=400, detail="Issue already resolved")

    if issue.issue_type == "conflict" and issue.asset_id:
        asset = db.query(models.Asset).filter(models.Asset.id == issue.asset_id).first()
        if asset:
            # conservative resolution: take the higher (more cautious) of the two reported values
            asset.criticality_resolved = max(asset.criticality_scanner or 1, asset.criticality_cmdb or 1)

    elif issue.issue_type == "missing_feed" and issue.control_id:
        # engineer performed the missing verification just now -- record it as
        # real evidence rather than only dismissing the ticket
        db.add(models.Evidence(control_id=issue.control_id, timestamp=datetime.utcnow(), source="manual_attestation", result="pass"))

    elif issue.issue_type == "missing_feed" and issue.asset_id and not issue.control_id:
        # asset itself had no telemetry feed at all -- engineer just connected one
        asset = db.query(models.Asset).filter(models.Asset.id == issue.asset_id).first()
        if asset:
            asset.has_telemetry = True

    elif issue.issue_type == "stale_evidence" and issue.control_id:
        # engineer re-ran verification now, refreshing the evidence trail
        db.add(models.Evidence(control_id=issue.control_id, timestamp=datetime.utcnow(), source="automated_scan", result="pass"))

    # "regression" issues are a factual record of what happened -- resolving
    # one means the review is complete, not that the incident is erased, so
    # no underlying record changes beyond the issue itself being closed out.

    issue.status = "resolved"
    issue.resolved_date = date.today()
    issue.resolved_by = identity.user.id
    db.commit()
    return {"status": "resolved", "issue_id": issue_id}
