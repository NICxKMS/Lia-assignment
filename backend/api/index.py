"""Vercel serverless function entry point."""
from app.main import app

# Vercel uses this as the ASGI handler
handler = app
