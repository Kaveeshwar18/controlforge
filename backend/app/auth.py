"""
Authentication: password hashing and session tokens.

Security notes:
  - Passwords are hashed with bcrypt and never stored, logged, or returned.
  - Login failures are deliberately vague ("invalid username or password")
    so the response can't be used to enumerate valid accounts.
  - The JWT secret comes from the CONTROLFORGE_SECRET env var. The generated
    fallback below is fine for local development only -- it changes on every
    restart, which invalidates existing tokens. Set the env var for anything
    that needs sessions to survive a restart.
  - Not implemented here (out of scope for a prototype, needed for real use):
    rate limiting / lockout on repeated failures, password reset, MFA,
    refresh-token rotation.
"""

import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session

from . import models
from .database import get_db

def _load_secret() -> str:
    """CONTROLFORGE_SECRET wins. Failing that, keep a generated secret in a
    local file so the dev server's auto-reload doesn't sign everyone out on
    every code edit. The file is local-only and must not be committed or
    reused as a production secret -- set the env var for real deployments."""
    env = os.environ.get("CONTROLFORGE_SECRET")
    if env:
        return env
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".dev-secret")
    try:
        if os.path.exists(path):
            existing = open(path).read().strip()
            if existing:
                return existing
        generated = secrets.token_urlsafe(48)
        with open(path, "w") as f:
            f.write(generated)
        os.chmod(path, 0o600)
        return generated
    except OSError:
        # read-only filesystem etc. -- fall back to per-process, which still
        # works, it just means restarts invalidate sessions
        return secrets.token_urlsafe(48)


SECRET = _load_secret()
ALGORITHM = "HS256"
TOKEN_TTL_HOURS = 12

MIN_PASSWORD_LENGTH = 8


def hash_password(raw: str) -> str:
    return bcrypt.hashpw(raw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(raw.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_token(account: models.Account) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(account.id),
        "usr": account.user_id,
        "iat": now,
        "exp": now + timedelta(hours=TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired -- please sign in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session token.")


def get_current_account(
    authorization: str = Header(None), db: Session = Depends(get_db)
) -> models.Account:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Not signed in.")
    payload = decode_token(authorization.split(" ", 1)[1].strip())
    account = db.query(models.Account).filter(models.Account.id == int(payload["sub"])).first()
    if not account:
        raise HTTPException(status_code=401, detail="Account no longer exists.")
    return account
