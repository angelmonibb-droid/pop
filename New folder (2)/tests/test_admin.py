from conftest import login


def test_admin_can_create_update_and_delete_user(client):
    _, token = login(client)
    created = client.post(
        "/api/admin/users",
        json={"username": "player1", "password": "strong-pass", "balance": 750, "difficulty": 3},
        headers={"X-CSRF-Token": token},
    )
    assert created.status_code == 201
    user_id = created.get_json()["user"]["id"]

    updated = client.patch(
        f"/api/admin/users/{user_id}",
        json={"balance": 900, "wins": 2, "losses": 1, "bestWin": 400, "enabled": True},
        headers={"X-CSRF-Token": token},
    )
    assert updated.status_code == 200
    assert updated.get_json()["user"]["balance"] == 900

    deleted = client.delete(f"/api/admin/users/{user_id}", headers={"X-CSRF-Token": token})
    assert deleted.status_code == 200


def test_admin_cannot_delete_current_account(client):
    response, token = login(client)
    admin_id = response.get_json()["user"]["id"]
    deleted = client.delete(f"/api/admin/users/{admin_id}", headers={"X-CSRF-Token": token})
    assert deleted.status_code == 400

