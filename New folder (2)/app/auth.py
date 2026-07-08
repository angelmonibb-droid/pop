import re
from functools import wraps

from flask import Blueprint, g, jsonify, request, session
from werkzeug.security import check_password_hash

from .db import get_db
from .security import client_key, csrf_token, login_limiter, require_csrf


bp = Blueprint("auth", __name__, url_prefix="/api")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")


def public_user(row) -> dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "balance": row["balance"],
        "wins": row["wins"],
        "losses": row["losses"],
        "bestWin": row["best_win"],
        "isAdmin": bool(row["is_admin"]),
        "difficulty": row["difficulty"],
    }


@bp.before_app_request
def load_current_user():
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
        return
    g.user = get_db().execute(
        "SELECT * FROM users WHERE id = ? AND enabled = 1", (user_id,)
    ).fetchone()
    if g.user is None:
        session.clear()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return jsonify(error="برای ادامه وارد حساب شوید."), 401
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not g.user["is_admin"]:
            return jsonify(error="دسترسی مدیر لازم است."), 403
        return view(*args, **kwargs)

    return wrapped


@bp.get("/session")
def session_status():
    return jsonify(csrfToken=csrf_token(), user=public_user(g.user) if g.user else None)


@bp.post("/auth/login")
@require_csrf
def login():
    key = client_key()
    if not login_limiter.allow(key):
        return jsonify(error="تلاش‌های ورود بیش از حد است؛ چند دقیقه دیگر دوباره امتحان کنید."), 429

    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    if not USERNAME_RE.fullmatch(username) or not password:
        return jsonify(error="نام کاربری یا رمز عبور نادرست است."), 401

    user = get_db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if user is None or not user["enabled"] or not check_password_hash(user["password_hash"], password):
        return jsonify(error="نام کاربری یا رمز عبور نادرست است."), 401

    login_limiter.clear(key)
    session.clear()
    session.permanent = True
    session["user_id"] = user["id"]
    token = csrf_token()
    return jsonify(user=public_user(user), csrfToken=token)


@bp.post("/auth/logout")
@require_csrf
def logout():
    session.clear()
    return jsonify(ok=True)


@bp.get("/me")
@login_required
def me():
    return jsonify(user=public_user(g.user))

