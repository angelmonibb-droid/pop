import secrets
import time
from collections import defaultdict, deque
from functools import wraps

from flask import jsonify, request, session


class LoginRateLimiter:
    def __init__(self, attempts: int = 8, window_seconds: int = 300):
        self.attempts = attempts
        self.window_seconds = window_seconds
        self._hits = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and hits[0] <= now - self.window_seconds:
            hits.popleft()
        if len(hits) >= self.attempts:
            return False
        hits.append(now)
        return True

    def clear(self, key: str) -> None:
        self._hits.pop(key, None)


login_limiter = LoginRateLimiter()


def csrf_token() -> str:
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def require_csrf(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        supplied = request.headers.get("X-CSRF-Token", "")
        expected = session.get("csrf_token", "")
        if not expected or not secrets.compare_digest(supplied, expected):
            return jsonify(error="درخواست نامعتبر است؛ صفحه را تازه‌سازی کنید."), 403
        return view(*args, **kwargs)

    return wrapped


def client_key() -> str:
    # REMOTE_ADDR remains trustworthy unless ProxyFix is explicitly configured.
    return request.remote_addr or "unknown"

