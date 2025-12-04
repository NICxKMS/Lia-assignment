# app/cli.py
import uvicorn
from alembic.config import main as alembic_main


def dev() -> None:
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


def start() -> None:
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)


def migrate() -> None:
    alembic_main(["upgrade", "head"])
