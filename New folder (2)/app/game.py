import json
import secrets
from decimal import Decimal, InvalidOperation

from flask import Blueprint, g, jsonify, request

from .auth import login_required, public_user
from .db import get_db, transaction, utc_now
from .security import require_csrf


bp = Blueprint("game", __name__, url_prefix="/api/game")

ROW_CONTENTS = (
    ("poop", "win", "win", "win"),
    ("poop", "win", "win", "win"),
    ("poop", "poop", "win", "win"),
    ("poop", "poop", "win", "win"),
    ("poop", "poop", "poop", "win"),
)
# Payout includes the original stake. The curve keeps roughly a 10% house edge
# across the first four rows while still rewarding the very first safe pick.
MULTIPLIERS = (120, 160, 320, 640, 2500)
MAX_STAKE = 1_000_000_000


def parse_positive_int(value) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not number.is_finite() or number != number.to_integral_value():
        return None
    result = int(number)
    return result if 0 < result <= MAX_STAKE else None


def generate_board() -> list[list[str]]:
    random = secrets.SystemRandom()
    board = []
    for template in ROW_CONTENTS:
        row = list(template)
        random.shuffle(row)
        board.append(row)
    return board


def active_round(db, user_id: int):
    return db.execute(
        "SELECT * FROM game_rounds WHERE user_id = ? AND status = 'active'", (user_id,)
    ).fetchone()


def payout_for(stake: int, completed_rows: int) -> int:
    if completed_rows < 1:
        return 0
    return stake * MULTIPLIERS[completed_rows - 1] // 100


def serialize_round(row, reveal_board: bool = False) -> dict | None:
    if row is None:
        return None
    revealed = json.loads(row["revealed_json"])
    board = json.loads(row["board_json"])
    terminal = row["status"] != "active"
    response = {
        "id": row["public_id"],
        "stake": row["stake"],
        "currentRow": row["current_row"],
        "completedRows": row["current_row"],
        "currentPayout": (
            payout_for(row["stake"], row["current_row"])
            if row["status"] == "active"
            else row["payout"]
        ),
        "status": row["status"],
        "payout": row["payout"],
        "revealed": revealed,
        "canWithdraw": row["status"] == "active" and row["current_row"] > 0,
    }
    if terminal or reveal_board:
        response["board"] = board
    return response


def fresh_user(db, user_id: int):
    return db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def ledger(db, user_id, round_id, kind, amount, balance, note=""):
    db.execute(
        """INSERT INTO balance_ledger
           (user_id, round_id, kind, amount, balance_after, note, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (user_id, round_id, kind, amount, balance, note, utc_now()),
    )


@bp.get("/state")
@login_required
def state():
    db = get_db()
    row = db.execute(
        "SELECT * FROM game_rounds WHERE user_id = ? ORDER BY id DESC LIMIT 1", (g.user["id"],)
    ).fetchone()
    return jsonify(game=serialize_round(row), user=public_user(fresh_user(db, g.user["id"])))


@bp.post("/start")
@login_required
@require_csrf
def start():
    payload = request.get_json(silent=True) or {}
    stake = parse_positive_int(payload.get("stake"))
    if stake is None:
        return jsonify(error="مبلغ شرط باید یک عدد صحیح مثبت باشد."), 400

    db = get_db()
    now = utc_now()
    with transaction(db):
        if active_round(db, g.user["id"]):
            return jsonify(error="یک دور فعال دارید؛ ابتدا همان دور را تمام کنید."), 409
        changed = db.execute(
            """UPDATE users SET balance = balance - ?, version = version + 1, updated_at = ?
               WHERE id = ? AND enabled = 1 AND balance >= ?""",
            (stake, now, g.user["id"], stake),
        ).rowcount
        if changed != 1:
            return jsonify(error="موجودی برای این مبلغ کافی نیست."), 409

        board = generate_board()
        public_id = secrets.token_urlsafe(18)
        cursor = db.execute(
            """INSERT INTO game_rounds
               (public_id, user_id, stake, board_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (public_id, g.user["id"], stake, json.dumps(board), now, now),
        )
        user = fresh_user(db, g.user["id"])
        ledger(db, g.user["id"], cursor.lastrowid, "stake", -stake, user["balance"], "round started")
        game = db.execute("SELECT * FROM game_rounds WHERE id = ?", (cursor.lastrowid,)).fetchone()

    return jsonify(game=serialize_round(game), user=public_user(user)), 201


@bp.post("/pick")
@login_required
@require_csrf
def pick():
    payload = request.get_json(silent=True) or {}
    row_index = payload.get("row")
    column = payload.get("column")
    if isinstance(row_index, bool) or isinstance(column, bool):
        return jsonify(error="انتخاب خانه نامعتبر است."), 400
    if not isinstance(row_index, int) or not isinstance(column, int):
        return jsonify(error="انتخاب خانه نامعتبر است."), 400
    if not 0 <= row_index < len(ROW_CONTENTS) or not 0 <= column < 4:
        return jsonify(error="انتخاب خانه خارج از صفحه است."), 400

    db = get_db()
    now = utc_now()
    with transaction(db):
        game = active_round(db, g.user["id"])
        if game is None:
            return jsonify(error="دور فعالی وجود ندارد."), 409
        if game["current_row"] != row_index:
            return jsonify(error="این ردیف اکنون قابل انتخاب نیست."), 409

        board = json.loads(game["board_json"])
        revealed = json.loads(game["revealed_json"])
        outcome = board[row_index][column]
        revealed.append({"row": row_index, "column": column, "outcome": outcome})
        next_row = row_index
        status = "active"
        payout = 0

        if outcome == "poop":
            status = "lost"
            db.execute(
                "UPDATE users SET losses = losses + 1, version = version + 1, updated_at = ? WHERE id = ?",
                (now, g.user["id"]),
            )
        else:
            next_row = row_index + 1

        if outcome == "win" and next_row == len(ROW_CONTENTS):
            status = "won"
            payout = payout_for(game["stake"], next_row)
            db.execute(
                """UPDATE users SET balance = balance + ?, wins = wins + 1,
                   best_win = MAX(best_win, ?), version = version + 1, updated_at = ? WHERE id = ?""",
                (payout, payout, now, g.user["id"]),
            )

        db.execute(
            """UPDATE game_rounds SET current_row = ?, revealed_json = ?, status = ?,
               payout = ?, updated_at = ? WHERE id = ? AND status = 'active'""",
            (next_row, json.dumps(revealed), status, payout, now, game["id"]),
        )
        user = fresh_user(db, g.user["id"])
        if payout:
            ledger(db, g.user["id"], game["id"], "payout", payout, user["balance"], "completed all rows")
        updated = db.execute("SELECT * FROM game_rounds WHERE id = ?", (game["id"],)).fetchone()

    return jsonify(
        outcome=outcome,
        game=serialize_round(updated),
        user=public_user(user),
    )


@bp.post("/withdraw")
@login_required
@require_csrf
def withdraw():
    db = get_db()
    now = utc_now()
    with transaction(db):
        game = active_round(db, g.user["id"])
        if game is None:
            return jsonify(error="دور فعالی وجود ندارد."), 409
        if game["current_row"] < 1:
            return jsonify(error="پیش از برداشت باید دست‌کم یک ردیف را ببرید."), 409
        payout = payout_for(game["stake"], game["current_row"])
        changed = db.execute(
            """UPDATE game_rounds SET status = 'withdrawn', payout = ?, updated_at = ?
               WHERE id = ? AND status = 'active'""",
            (payout, now, game["id"]),
        ).rowcount
        if changed != 1:
            return jsonify(error="این دور قبلاً تسویه شده است."), 409
        db.execute(
            """UPDATE users SET balance = balance + ?, wins = wins + 1,
               best_win = MAX(best_win, ?), version = version + 1, updated_at = ? WHERE id = ?""",
            (payout, payout, now, g.user["id"]),
        )
        user = fresh_user(db, g.user["id"])
        ledger(db, g.user["id"], game["id"], "payout", payout, user["balance"], "player withdrew")
        updated = db.execute("SELECT * FROM game_rounds WHERE id = ?", (game["id"],)).fetchone()

    return jsonify(game=serialize_round(updated), user=public_user(user))


@bp.post("/abandon")
@login_required
@require_csrf
def abandon():
    db = get_db()
    now = utc_now()
    with transaction(db):
        game = active_round(db, g.user["id"])
        if game is None:
            return jsonify(ok=True, game=None, user=public_user(fresh_user(db, g.user["id"])))
        db.execute(
            "UPDATE game_rounds SET status = 'abandoned', updated_at = ? WHERE id = ?",
            (now, game["id"]),
        )
        db.execute(
            "UPDATE users SET losses = losses + 1, version = version + 1, updated_at = ? WHERE id = ?",
            (now, g.user["id"]),
        )
        updated = db.execute("SELECT * FROM game_rounds WHERE id = ?", (game["id"],)).fetchone()
        user = fresh_user(db, g.user["id"])
    return jsonify(ok=True, game=serialize_round(updated), user=public_user(user))


@bp.get("/ledger")
@login_required
def balance_history():
    rows = get_db().execute(
        """SELECT kind, amount, balance_after, note, created_at
           FROM balance_ledger WHERE user_id = ? ORDER BY id DESC LIMIT 25""",
        (g.user["id"],),
    ).fetchall()
    return jsonify(items=[dict(row) for row in rows])
