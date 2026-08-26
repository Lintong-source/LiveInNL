"""Expatus Flask application factory.

Controllers own HTTP concerns, repositories own SQL, and services contain
reusable security, privacy, email and domain behavior.
"""

from __future__ import annotations

from datetime import timedelta

from flask import Flask, g, render_template

from expatus.config import PROJECT_ROOT, load_settings
from expatus.database import init_app as init_database
from expatus.services.security import after_request, before_request, csrf_token


def create_app(overrides: dict | None = None) -> Flask:
    settings = load_settings(overrides)
    app = Flask(
        __name__,
        root_path=str(PROJECT_ROOT),
        template_folder="templates",
        static_folder="static",
        static_url_path="/static",
    )
    app.secret_key = settings.secret_key
    app.config.update(
        EXPATUS_SETTINGS=settings,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=settings.cookie_secure,
        MAX_CONTENT_LENGTH=128 * 1024,
        TEMPLATES_AUTO_RELOAD=not settings.is_production,
    )
    app.permanent_session_lifetime = timedelta(days=30)

    init_database(app)
    app.before_request(before_request)
    app.after_request(after_request)

    from expatus.controllers.admin import blueprint as admin_blueprint
    from expatus.controllers.auth import blueprint as auth_blueprint
    from expatus.controllers.pages import blueprint as pages_blueprint
    from expatus.controllers.submissions import blueprint as submissions_blueprint
    from expatus.controllers.workspace import blueprint as workspace_blueprint

    for blueprint in (
        pages_blueprint,
        auth_blueprint,
        workspace_blueprint,
        submissions_blueprint,
        admin_blueprint,
    ):
        app.register_blueprint(blueprint)

    @app.context_processor
    def inject_context():
        return {
            "current_user": getattr(g, "user", None),
            "csrf_token": csrf_token,
            "settings": settings,
            "base_url": settings.base_url,
        }

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("pages/404.html"), 404

    return app
