"""WSGI entry point for Vercel. Local app.py startup remains available."""
from app import create_app

app = create_app()
