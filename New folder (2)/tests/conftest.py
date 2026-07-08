import pytest

from app import create_app


@pytest.fixture()
def app(tmp_path):
    application = create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "test.sqlite3"),
            "SECRET_KEY": "test-secret-key",
            "ADMIN_USERNAME": "adminmor",
            "ADMIN_PASSWORD": "test-admin-password",
            "ADMIN_INITIAL_BALANCE": 10_000,
        }
    )
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()


def csrf(client):
    return client.get("/api/session").get_json()["csrfToken"]


def login(client, username="adminmor", password="test-admin-password"):
    token = csrf(client)
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
        headers={"X-CSRF-Token": token},
    )
    data = response.get_json()
    return response, data.get("csrfToken", token)

