# app/cli.py
import os

import uvicorn
from alembic.config import main as alembic_main


def dev() -> None:
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


def start() -> None:
    # Use PORT env var (required by Render, Heroku, etc.) or default to 8000
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)


def migrate() -> None:
    alembic_main(["upgrade", "head"])
