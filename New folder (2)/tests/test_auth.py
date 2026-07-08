from werkzeug.security import check_password_hash

from app.db import get_db
from conftest import csrf, login


def test_admin_logs_in_once_and_password_is_never_returned(app, client):
    response, token = login(client)
    assert response.status_code == 200
    assert response.get_json()["user"]["isAdmin"] is True
    assert "password" not in response.get_data(as_text=True).lower()

    users = client.get("/api/admin/users")
    assert users.status_code == 200
    assert users.get_json()["items"][0]["username"] == "adminmor"

    with app.app_context():
        stored = get_db().execute("SELECT password_hash FROM users WHERE username = 'adminmor'").fetchone()[0]
        assert stored != "test-admin-password"
        assert check_password_hash(stored, "test-admin-password")


def test_login_requires_csrf_and_rejects_bad_password(client):
    missing = client.post("/api/auth/login", json={"username": "adminmor", "password": "x"})
    assert missing.status_code == 403

    token = csrf(client)
    bad = client.post(
        "/api/auth/login",
        json={"username": "adminmor", "password": "wrong"},
        headers={"X-CSRF-Token": token},
    )
    assert bad.status_code == 401
    assert "adminmor" not in bad.get_data(as_text=True)


def test_security_headers_are_set(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_americano_brand_and_support_link_are_rendered(client):
    html = client.get("/").get_data(as_text=True)
    assert "آمریکانو" in html
    assert 'href="https://t.me/Bussof"' in html
    assert 'rel="noopener noreferrer"' in html
