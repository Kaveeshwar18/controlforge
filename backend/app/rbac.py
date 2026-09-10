"""
Role-based access & redaction (PRD section 2 & 6).

Identity is established by a signed session token (see auth.py) and resolved
against the `users` / `user_org_access` tables. Every router enforces org
scoping and field redaction through the helpers below rather than trusting
client input -- a caller cannot ask to be treated as a different persona.
"""

from dataclasses import dataclass
from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session

from . import models
from .auth import get_current_account
from .database import get_db

ROLES = ["CISO", "PLANT_MANAGER", "OT_ENGINEER", "EXTERNAL_AUDITOR", "CORP_ADMIN"]

# What each role is allowed to see, independent of org scoping
ROLE_CAPABILITIES = {
    "CISO": {"technical_drilldown": True, "raw_asset_ids": True, "cross_org": False, "can_resolve_issues": False, "business_framing": True},
    "PLANT_MANAGER": {"technical_drilldown": False, "raw_asset_ids": True, "cross_org": False, "can_resolve_issues": False, "business_framing": True},
    "OT_ENGINEER": {"technical_drilldown": True, "raw_asset_ids": True, "cross_org": False, "can_resolve_issues": True, "business_framing": False},
    "EXTERNAL_AUDITOR": {"technical_drilldown": False, "raw_asset_ids": False, "cross_org": False, "can_resolve_issues": False, "business_framing": True},
    "CORP_ADMIN": {"technical_drilldown": True, "raw_asset_ids": True, "cross_org": True, "can_resolve_issues": True, "business_framing": True},
}


@dataclass
class Identity:
    user: models.User
    accessible_org_ids: set
    redacted_org_ids: set  # subset of accessible_org_ids shown in redacted form

    @property
    def role(self) -> str:
        return self.user.role

    @property
    def caps(self) -> dict:
        return ROLE_CAPABILITIES[self.user.role]


def get_identity(
    account: models.Account = Depends(get_current_account), db: Session = Depends(get_db)
) -> Identity:
    """Identity comes from the signed session token -- never from a
    client-supplied header. The caller cannot choose which persona (and so
    which role and org access) they are evaluated as."""
    user = db.query(models.User).filter(models.User.id == account.user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Account is not linked to a valid user profile.")
    access_rows = db.query(models.UserOrgAccess).filter(models.UserOrgAccess.user_id == user.id).all()
    accessible = {r.org_id for r in access_rows}
    redacted = {r.org_id for r in access_rows if r.redacted}
    return Identity(user=user, accessible_org_ids=accessible, redacted_org_ids=redacted)


def require_org_access(identity: Identity, org_id: str):
    if org_id not in identity.accessible_org_ids:
        raise HTTPException(
            status_code=403,
            detail=f"Not authorized: role {identity.role} does not have access to organization '{org_id}'.",
        )


def is_redacted(identity: Identity, org_id: str) -> bool:
    return org_id in identity.redacted_org_ids or not identity.caps["raw_asset_ids"]


def redact_asset_name(identity: Identity, org_id: str, asset_type: str, zone: str, ordinal: int) -> str:
    if is_redacted(identity, org_id):
        return f"{asset_type}-{zone}-Unit{ordinal}"
    return None  # caller should fall back to the real name
