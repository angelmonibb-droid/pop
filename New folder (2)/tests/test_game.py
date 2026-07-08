import json
from concurrent.futures import ThreadPoolExecutor

from app.db import get_db
from conftest import login


def start(client, token, stake=1000):
    return client.post("/api/game/start", json={"stake": stake}, headers={"X-CSRF-Token": token})


def board_for(app):
    with app.app_context():
        row = get_db().execute("SELECT board_json FROM game_rounds ORDER BY id DESC LIMIT 1").fetchone()
        return json.loads(row[0])


def test_start_is_atomic_and_duplicate_start_does_not_double_charge(app, client):
    _, token = login(client)
    first = start(client, token, 1000)
    assert first.status_code == 201
    assert first.get_json()["user"]["balance"] == 9000

    duplicate = start(client, token, 1000)
    assert duplicate.status_code == 409
    me = client.get("/api/me").get_json()["user"]
    assert me["balance"] == 9000

    with app.app_context():
        entries = get_db().execute("SELECT amount FROM balance_ledger WHERE kind = 'stake'").fetchall()
        assert [row[0] for row in entries] == [-1000]


def test_loss_is_persisted_without_zeroing_unrelated_balance(app, client):
    _, token = login(client)
    start(client, token, 500)
    board = board_for(app)
    losing_column = board[0].index("poop")
    result = client.post(
        "/api/game/pick",
        json={"row": 0, "column": losing_column},
        headers={"X-CSRF-Token": token},
    )
    data = result.get_json()
    assert result.status_code == 200
    assert data["game"]["status"] == "lost"
    assert data["game"]["completedRows"] == 0
    assert data["game"]["currentPayout"] == 0
    assert data["user"]["balance"] == 9500
    assert data["user"]["losses"] == 1

    repeated = client.post(
        "/api/game/pick",
        json={"row": 0, "column": losing_column},
        headers={"X-CSRF-Token": token},
    )
    assert repeated.status_code == 409
    assert client.get("/api/me").get_json()["user"]["losses"] == 1


def test_first_safe_pick_can_be_withdrawn_with_profit(app, client):
    _, token = login(client)
    start(client, token, 1000)
    board = board_for(app)

    first_win = board[0].index("win")
    pick = client.post(
        "/api/game/pick",
        json={"row": 0, "column": first_win},
        headers={"X-CSRF-Token": token},
    )
    assert pick.get_json()["game"]["currentPayout"] == 1200
    assert pick.get_json()["game"]["canWithdraw"] is True

    withdrawn = client.post("/api/game/withdraw", headers={"X-CSRF-Token": token})
    data = withdrawn.get_json()
    assert data["game"]["payout"] == 1200
    assert data["user"]["balance"] == 10_200
    assert data["user"]["wins"] == 1


def test_board_is_hidden_while_round_is_active(app, client):
    _, token = login(client)
    response = start(client, token, 100)
    assert "board" not in response.get_json()["game"]
    state = client.get("/api/game/state").get_json()["game"]
    assert "board" not in state


def test_new_multiplier_curve_is_available_after_every_safe_row(app, client):
    _, token = login(client)
    start(client, token, 1000)
    board = board_for(app)
    expected_payouts = [1200, 1600, 3200, 6400, 25_000]

    for row, expected in enumerate(expected_payouts):
        winning_column = board[row].index("win")
        response = client.post(
            "/api/game/pick",
            json={"row": row, "column": winning_column},
            headers={"X-CSRF-Token": token},
        )
        game = response.get_json()["game"]
        assert response.status_code == 200
        assert game["currentPayout"] == expected
        if row < 4:
            assert game["canWithdraw"] is True
            assert game["status"] == "active"
        else:
            assert game["status"] == "won"
            assert game["payout"] == 25_000


def test_two_simultaneous_starts_only_charge_once(app):
    first_client = app.test_client()
    second_client = app.test_client()
    _, first_token = login(first_client)
    _, second_token = login(second_client)

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda pair: start(*pair, 1000), [
            (first_client, first_token),
            (second_client, second_token),
        ]))

    assert sorted(response.status_code for response in responses) == [201, 409]
    with app.app_context():
        user = get_db().execute("SELECT balance FROM users WHERE username = 'adminmor'").fetchone()
        assert user["balance"] == 9000
