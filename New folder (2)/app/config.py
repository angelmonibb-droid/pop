import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path) -> None:
    """A tiny .env reader so deployment does not depend on another package."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def build_config() -> dict:
    load_dotenv(BASE_DIR / ".env")
    environment = os.getenv("APP_ENV", "development").lower()
    secret = os.getenv("SECRET_KEY", "dev-only-change-me-before-production")
    admin_password = os.getenv("ADMIN_PASSWORD", "13888831")
    if environment == "production" and (len(secret) < 32 or secret.startswith("replace-")):
        raise RuntimeError("SECRET_KEY must contain at least 32 characters in production")
    if environment == "production" and (len(admin_password) < 12 or admin_password.startswith("replace-")):
        raise RuntimeError("ADMIN_PASSWORD must be a strong non-placeholder password in production")

    database = Path(os.getenv("DATABASE_PATH", "instance/poop_game.sqlite3"))
    if not database.is_absolute():
        database = BASE_DIR / database

    return {
        "ENV_NAME": environment,
        "DEBUG": environment == "development",
        "SECRET_KEY": secret,
        "DATABASE": str(database),
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SESSION_COOKIE_SECURE": environment == "production",
        "PERMANENT_SESSION_LIFETIME": 60 * 60 * 12,
        "MAX_CONTENT_LENGTH": 32 * 1024,
        "ADMIN_USERNAME": os.getenv("ADMIN_USERNAME", "adminmor"),
        "ADMIN_PASSWORD": admin_password,
        "ADMIN_INITIAL_BALANCE": int(os.getenv("ADMIN_INITIAL_BALANCE", "1000000")),
        "PORT": int(os.getenv("PORT", "8000")),
        "TRUST_PROXY": os.getenv("TRUST_PROXY", "0").lower() in {"1", "true", "yes"},
    }
