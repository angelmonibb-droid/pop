import json

from flask import Blueprint, g, jsonify, request
from sqlite3 import IntegrityError
from werkzeug.security import generate_password_hash

from .auth import USERNAME_RE, admin_required, public_user
from .db import get_db, transaction, utc_now
from .security import require_csrf


bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def admin_user(row) -> dict:
    data = public_user(row)
    data.update(enabled=bool(row["enabled"]), version=row["version"], createdAt=row["created_at"])
    return data


def clean_nonnegative(value, field: str, maximum: int = 1_000_000_000) -> int:
    if isinstance(value, bool):
        raise ValueError(field)
    number = int(value)
    if number < 0 or number > maximum:
        raise ValueError(field)
    return number


def audit(db, action: str, target_id=None, details=None):
    db.execute(
        """INSERT INTO audit_log(actor_user_id, action, target_user_id, details, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (g.user["id"], action, target_id, json.dumps(details or {}, ensure_ascii=False), utc_now()),
    )


@bp.get("/users")
@admin_required
def users():
    rows = get_db().execute("SELECT * FROM users ORDER BY id").fetchall()
    return jsonify(items=[admin_user(row) for row in rows])


@bp.post("/users")
@admin_required
@require_csrf
def create_user():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    if not USERNAME_RE.fullmatch(username):
        return jsonify(error="نام کاربری باید ۳ تا ۳۲ نویسه و فقط شامل حروف انگلیسی، عدد یا ._- باشد."), 400
    if len(password) < 8 or len(password) > 128:
        return jsonify(error="رمز عبور باید بین ۸ تا ۱۲۸ نویسه باشد."), 400
    try:
        balance = clean_nonnegative(payload.get("balance", 0), "balance")
        difficulty = int(payload.get("difficulty", 3))
        if not 1 <= difficulty <= 6:
            raise ValueError("difficulty")
    except (ValueError, TypeError):
        return jsonify(error="مقادیر عددی واردشده معتبر نیستند."), 400

    db = get_db()
    now = utc_now()
    try:
        with transaction(db):
            cursor = db.execute(
                """INSERT INTO users
                   (username, password_hash, balance, difficulty, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (username, generate_password_hash(password), balance, difficulty, now, now),
            )
            user_id = cursor.lastrowid
            if balance:
                db.execute(
                    """INSERT INTO balance_ledger
                       (user_id, kind, amount, balance_after, note, created_at)
                       VALUES (?, 'admin_adjustment', ?, ?, 'account created', ?)""",
                    (user_id, balance, balance, now),
                )
            audit(db, "user.create", user_id, {"username": username, "balance": balance})
            user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    except IntegrityError:
        return jsonify(error="این نام کاربری قبلاً ثبت شده است."), 409
    return jsonify(user=admin_user(user)), 201


@bp.patch("/users/<int:user_id>")
@admin_required
@require_csrf
def update_user(user_id: int):
    payload = request.get_json(silent=True) or {}
    db = get_db()
    target = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if target is None:
        return jsonify(error="کاربر پیدا نشد."), 404

    username = str(payload.get("username", target["username"])).strip()
    if not USERNAME_RE.fullmatch(username):
        return jsonify(error="نام کاربری معتبر نیست."), 400
    try:
        balance = clean_nonnegative(payload.get("balance", target["balance"]), "balance")
        wins = clean_nonnegative(payload.get("wins", target["wins"]), "wins")
        losses = clean_nonnegative(payload.get("losses", target["losses"]), "losses")
        best = clean_nonnegative(payload.get("bestWin", target["best_win"]), "bestWin")
        difficulty = int(payload.get("difficulty", target["difficulty"]))
        if not 1 <= difficulty <= 6:
            raise ValueError("difficulty")
    except (ValueError, TypeError):
        return jsonify(error="مقادیر عددی واردشده معتبر نیستند."), 400

    enabled_value = payload.get("enabled", bool(target["enabled"]))
    if not isinstance(enabled_value, bool):
        return jsonify(error="وضعیت فعال بودن حساب معتبر نیست."), 400
    enabled = enabled_value
    if user_id == g.user["id"] and not enabled:
        return jsonify(error="نمی‌توانید حساب مدیرِ در حال استفاده را غیرفعال کنید."), 400
    password = str(payload.get("password", ""))
    if password and not 8 <= len(password) <= 128:
        return jsonify(error="رمز جدید باید بین ۸ تا ۱۲۸ نویسه باشد."), 400

    now = utc_now()
    try:
        with transaction(db):
            fields = [
                "username = ?", "balance = ?", "wins = ?", "losses = ?", "best_win = ?",
                "difficulty = ?", "enabled = ?", "version = version + 1", "updated_at = ?",
            ]
            values = [username, balance, wins, losses, best, difficulty, int(enabled), now]
            if password:
                fields.append("password_hash = ?")
                values.append(generate_password_hash(password))
            values.append(user_id)
            db.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", values)
            delta = balance - target["balance"]
            if delta:
                db.execute(
                    """INSERT INTO balance_ledger
                       (user_id, kind, amount, balance_after, note, created_at)
                       VALUES (?, 'admin_adjustment', ?, ?, 'admin update', ?)""",
                    (user_id, delta, balance, now),
                )
            audit(db, "user.update", user_id, {"balanceDelta": delta, "enabled": enabled})
            updated = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    except IntegrityError:
        return jsonify(error="این نام کاربری قبلاً ثبت شده است."), 409
    return jsonify(user=admin_user(updated))


@bp.delete("/users/<int:user_id>")
@admin_required
@require_csrf
def delete_user(user_id: int):
    if user_id == g.user["id"]:
        return jsonify(error="نمی‌توانید حساب مدیرِ در حال استفاده را حذف کنید."), 400
    db = get_db()
    target = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if target is None:
        return jsonify(error="کاربر پیدا نشد."), 404
    if target["is_admin"]:
        admin_count = db.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1").fetchone()[0]
        if admin_count <= 1:
            return jsonify(error="آخرین مدیر سامانه قابل حذف نیست."), 400
    with transaction(db):
        audit(db, "user.delete", user_id, {"username": target["username"]})
        db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    return jsonify(ok=True)


@bp.get("/audit")
@admin_required
def audit_history():
    rows = get_db().execute(
        """SELECT a.id, a.action, a.details, a.created_at,
                  actor.username AS actor, target.username AS target
           FROM audit_log a
           LEFT JOIN users actor ON actor.id = a.actor_user_id
           LEFT JOIN users target ON target.id = a.target_user_id
           ORDER BY a.id DESC LIMIT 50"""
    ).fetchall()
    return jsonify(items=[dict(row) for row in rows])
