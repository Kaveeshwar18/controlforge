import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from .. import models
from ..auth import (
    MIN_PASSWORD_LENGTH, create_token, get_current_account, hash_password, verify_password,
)
from ..database import get_db

router = APIRouter(tags=["auth"])

USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{3,32}$")

# New self-registered accounts land here. Real provisioning would be
# admin-driven; this keeps the prototype usable without granting anything
# beyond the most limited business-facing role on the demo plant.
# Kept as a plain constant (not derived from plants.json) so it fails loudly
# in signup() below if the referenced org is ever removed, instead of
# silently granting access to a dangling org_id -- which is exactly the bug
# that shipped when the plant network moved from Riverside/Dover to India
# and this constant wasn't updated alongside it.
DEFAULT_ROLE = "PLANT_MANAGER"
DEFAULT_ORG = "chennai"


class SignupPayload(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=200)
    accepted_terms: bool = False


class LoginPayload(BaseModel):
    identifier: str = Field(min_length=1, max_length=200)  # username or email
    password: str = Field(min_length=1, max_length=200)


def _session_response(db: Session, account: models.Account) -> dict:
    user = db.query(models.User).filter(models.User.id == account.user_id).first()
    return {
        "token": create_token(account),
        "account": {
            "id": account.id,
            "username": account.username,
            "email": account.email,
            "user_id": account.user_id,
            "name": user.name if user else account.username,
            "role": user.role if user else None,
        },
    }


@router.post("/auth/signup", status_code=201)
def signup(payload: SignupPayload, db: Session = Depends(get_db)):
    if not payload.accepted_terms:
        raise HTTPException(status_code=400, detail="You must accept the terms of service to sign up.")
    if not USERNAME_RE.match(payload.username):
        raise HTTPException(
            status_code=400,
            detail="Username must be 3-32 characters, letters/numbers/dot/dash/underscore only.",
        )

    username = payload.username.strip()
    email = payload.email.strip().lower()

    if db.query(models.Account).filter(models.Account.username == username).first():
        raise HTTPException(status_code=409, detail="That username is already taken.")
    if db.query(models.Account).filter(models.Account.email == email).first():
        raise HTTPException(status_code=409, detail="That email is already registered.")

    # every account needs a persona to carry its role and org access
    persona_id = f"acct.{username.lower()}"
    if not db.query(models.User).filter(models.User.id == persona_id).first():
        if not db.query(models.Organization).filter(models.Organization.id == DEFAULT_ORG).first():
            # fail loudly rather than granting access to a dangling org_id --
            # this is exactly the bug that shipped when the plant network
            # moved from Riverside/Dover to India without updating DEFAULT_ORG
            raise HTTPException(
                status_code=500,
                detail=f"Signup is misconfigured: default org '{DEFAULT_ORG}' does not exist.",
            )
        db.add(models.User(
            id=persona_id, name=username, role=DEFAULT_ROLE,
            title=f"{DEFAULT_ROLE.replace('_', ' ').title()} (self-registered)",
        ))
        db.add(models.UserOrgAccess(user_id=persona_id, org_id=DEFAULT_ORG, redacted=False))

    account = models.Account(
        username=username,
        email=email,
        password_hash=hash_password(payload.password),
        user_id=persona_id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return _session_response(db, account)


@router.post("/auth/login")
def login(payload: LoginPayload, db: Session = Depends(get_db)):
    identifier = payload.identifier.strip()
    account = (
        db.query(models.Account)
        .filter(
            (models.Account.username == identifier)
            | (models.Account.email == identifier.lower())
        )
        .first()
    )
    # same message and same work either way -- don't leak which accounts exist
    if not account or not verify_password(payload.password, account.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    return _session_response(db, account)


@router.get("/auth/me")
def me(account: models.Account = Depends(get_current_account), db: Session = Depends(get_db)):
    return _session_response(db, account)["account"]
