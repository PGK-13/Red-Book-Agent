"""Programmatic Alembic entrypoints used by tests and Docker."""

from __future__ import annotations

import argparse
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.config import settings


def build_alembic_config(database_url: str | None = None) -> Config:
    backend_dir = Path(__file__).resolve().parents[2]
    migrations_dir = Path(__file__).resolve().parent / "migrations"

    config = Config()
    config.set_main_option("script_location", str(migrations_dir))
    config.set_main_option("prepend_sys_path", str(backend_dir))
    config.set_main_option("sqlalchemy.url", database_url or settings.database_url)
    return config


def upgrade_database(database_url: str | None = None, revision: str = "head") -> None:
    command.upgrade(build_alembic_config(database_url), revision)


def downgrade_database(database_url: str | None = None, revision: str = "base") -> None:
    command.downgrade(build_alembic_config(database_url), revision)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Alembic migrations.")
    parser.add_argument("action", choices=["upgrade", "downgrade"])
    parser.add_argument("revision", nargs="?", default="head")
    parser.add_argument("--database-url", dest="database_url", default=None)
    args = parser.parse_args()

    if args.action == "upgrade":
        upgrade_database(database_url=args.database_url, revision=args.revision)
        return

    downgrade_database(database_url=args.database_url, revision=args.revision)


if __name__ == "__main__":
    main()
