# app/cli.py
import os

import uvicorn
from alembic.config import main as alembic_main


def dev() -> None:
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

def start() -> None:
    """Start server (single worker, good for containers like Render/Railway)."""
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)

def prod() -> None:
    """Start production server with multiple workers."""
    port = int(os.environ.get("PORT", 8000))
    workers = int(os.environ.get("WORKERS", 4))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, workers=workers)

def prod_granian() -> None:
    """Run production server with Granian (Rust-based, faster)."""
    try:
        from granian import Granian  # pyright: ignore[reportMissingImports]
        server = Granian(
            "app.main:app",
            address="0.0.0.0",
            port=int(os.environ.get("PORT", "8000")),
            workers=int(os.environ.get("WEB_CONCURRENCY", "2")),
            interface="asgi",
        )
        server.serve()
    except ImportError:
        print("Granian not installed. Install with: uv pip install 'lia-backend[prod]'")
        print("Falling back to uvicorn...")
        prod()

def migrate() -> None:
    alembic_main(["upgrade", "head"])

def pytest() -> None:
    import pytest
    # Run all tests in the tests/ directory, stop after first failure
    pytest.main(["-x", "tests"])
