"""WSGI entry point retained for Gunicorn and later Vercel integration."""

from expatus import create_app


app = create_app()
