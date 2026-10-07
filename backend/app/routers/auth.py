import threading
import time

from fastapi import APIRouter, HTTPException, Request, status

from app.auth import check_credentials, issue_token
from app.schemas import LoginIn, TokenOut

router = APIRouter(prefix="/auth", tags=["auth"])

# Brute-force guard (the site can be shared on the internet via share-online.bat):
# 5 wrong passwords from one client -> locked for 10 minutes.
MAX_FAILS, WINDOW_S = 5, 600
_fails: dict[str, list[float]] = {}
_lock = threading.Lock()


def _client(request: Request) -> str:
    # behind Cloudflare Tunnel every request comes from 127.0.0.1; the real visitor is in this header
    return request.headers.get("cf-connecting-ip") or (request.client.host if request.client else "?")


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, request: Request) -> TokenOut:
    who, now = _client(request), time.time()
    with _lock:
        recent = [t for t in _fails.get(who, []) if now - t < WINDOW_S]
        _fails[who] = recent
        if len(recent) >= MAX_FAILS:
            wait = int(WINDOW_S - (now - recent[0])) // 60 + 1
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                                detail={"code": "TOO_MANY_ATTEMPTS", "message": f"ใส่รหัสผิดหลายครั้ง ลองใหม่ในอีก {wait} นาที"})
    if not check_credentials(body.username, body.password):
        with _lock:
            _fails.setdefault(who, []).append(now)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "BAD_CREDENTIALS", "message": "Wrong username or password"})
    with _lock:
        _fails.pop(who, None)
    token, exp = issue_token()
    return TokenOut(access_token=token, expires_at=exp)