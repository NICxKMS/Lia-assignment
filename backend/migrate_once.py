"""
Run Alembic migrations to head with a single command.

Usage:
    python migrate_once.py
"""

from pathlib import Path

from alembic import command
from alembic.config import Config


def main() -> None:
    """Upgrade database schema to the latest revision."""
    cfg = Config(str(Path(__file__).parent / "alembic.ini"))
    command.upgrade(cfg, "head")


if __name__ == "__main__":
    main()

