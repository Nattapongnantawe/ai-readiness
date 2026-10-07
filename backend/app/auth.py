"""Minimal admin auth: one admin account from .env, JWT bearer tokens (FR-AU-01)."""
import hmac
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

bearer = HTTPBearer(auto_error=False)
ALGO = "HS256"


def check_credentials(username: str, password: str) -> bool:
    return hmac.compare_digest(username, settings.admin_username) and hmac.compare_digest(password, settings.admin_password)


def issue_token() -> tuple[str, datetime]:
    exp = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    token = jwt.encode({"sub": settings.admin_username, "role": "admin", "exp": exp}, settings.jwt_secret, algorithm=ALGO)
    return token, exp


def require_admin(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> None:
    if not settings.auth_enabled:
        return
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "AUTH_REQUIRED", "message": "Sign in as admin first"})
    try:
        payload = jwt.decode(creds.credentials, settings.jwt_secret, algorithms=[ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "TOKEN_EXPIRED", "message": "Session expired, sign in again"})
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "TOKEN_INVALID", "message": "Invalid token"})
    if payload.get("role") != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail={"code": "FORBIDDEN", "message": "Admin only"})
