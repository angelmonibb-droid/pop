"""Create a consistent online SQLite backup without stopping the server."""

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Back up the Poop Game database")
    parser.add_argument("--output-dir", default="backups", help="Backup destination directory")
    args = parser.parse_args()

    app = create_app()
    source_path = Path(app.config["DATABASE"])
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination_path = output_dir / f"poop-game-{stamp}.sqlite3"

    with sqlite3.connect(source_path) as source, sqlite3.connect(destination_path) as destination:
        source.backup(destination)
        result = destination.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise RuntimeError(f"Backup integrity check failed: {result}")

    print(destination_path)


if __name__ == "__main__":
    main()

