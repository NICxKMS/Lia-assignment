# app/cli.py
import os
import uvicorn
from alembic.config import main as alembic_main

def dev() -> None:
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

def start() -> None:
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)

def migrate() -> None:
    alembic_main(["upgrade", "head"])

def pytest() -> None:
    import pytest
    # Run all tests in the tests/ directory, stop after first failure
    pytest.main(["-x", "tests"])