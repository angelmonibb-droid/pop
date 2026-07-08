"""Safely reset a locked-out administrator password from the server console."""

import argparse
from getpass import getpass

from werkzeug.security import generate_password_hash

from app import create_app
from app.db import get_db, transaction, utc_now


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset an administrator password")
    parser.add_argument("username", help="Administrator username")
    args = parser.parse_args()

    password = getpass("New password: ")
    repeated = getpass("Repeat password: ")
    if password != repeated:
        raise SystemExit("Passwords do not match")
    if not 12 <= len(password) <= 128:
        raise SystemExit("Password must contain 12 to 128 characters")

    app = create_app()
    with app.app_context():
        db = get_db()
        user = db.execute(
            "SELECT id, is_admin FROM users WHERE username = ?", (args.username,)
        ).fetchone()
        if user is None or not user["is_admin"]:
            raise SystemExit("Administrator not found")
        with transaction(db):
            db.execute(
                "UPDATE users SET password_hash = ?, version = version + 1, updated_at = ? WHERE id = ?",
                (generate_password_hash(password), utc_now(), user["id"]),
            )
    print("Administrator password updated")


if __name__ == "__main__":
    main()

