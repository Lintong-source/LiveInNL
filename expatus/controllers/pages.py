"""Public content pages, canonical URLs and search-engine metadata endpoints."""

from __future__ import annotations

from datetime import date, timedelta

from flask import Blueprint, Response, abort, current_app, g, redirect, render_template, request, send_from_directory

from expatus.config import PROJECT_ROOT
from expatus.constants import (
    PLATFORM_AVATAR_KEYS,
    PLATFORM_BY_NAME,
    PROGRESS_PERCENT,
    STAGE_DESCRIPTIONS,
    STATUSES,
)
from expatus.repositories import favorites, properties, strategies
from expatus.services import account_data, progress_summary, strategy_engine
from expatus.services.security import login_required
from expatus.services.validation import safe_next


blueprint = Blueprint("pages", __name__)


@blueprint.get("/")
def home():
    names = favorites.names_for_user(g.user["id"]) if g.user else []
    return render_template(
        "pages/index.html",
        home_state={"authenticated": bool(g.user), "favorites": names},
        active_section="home",
    )


@blueprint.get("/auth")
def auth_page():
    requested_next = request.args.get("next")
    destination = safe_next(requested_next) if requested_next else "/workspace/strategy"
    if g.user:
        return redirect(destination)
    return render_template("pages/auth.html", next_url=destination)


@blueprint.get("/progress")
@login_required
def progress():
    items = [properties.serialize(row) for row in properties.list_for_user(g.user["id"])]
    state = {
        "properties": items,
        "statuses": STATUSES,
        "percent": PROGRESS_PERCENT,
        "descriptions": STAGE_DESCRIPTIONS,
    }
    return render_template("pages/my-rental-progress.html", progress_state=state, active_section="workspace")


@blueprint.get("/workspace/strategy")
@login_required
def strategy_workspace():
    latest = strategies.latest_for_user(g.user["id"])
    latest_profile = strategies.profile_from_row(latest) if latest else None
    current_progress = progress_summary.for_user(g.user["id"])
    current_strategy = (
        strategy_engine.generate(latest_profile, current_progress) if latest_profile else None
    )
    return render_template(
        "pages/my-housing-strategy.html",
        strategy_state={
            "used_today": strategies.count_today(g.user["id"]),
            "daily_limit": 3,
            "latest_profile": latest_profile,
            "strategy": current_strategy,
        },
        default_move_date=(date.today() + timedelta(days=60)).isoformat(),
        active_section="workspace",
    )


@blueprint.get("/favorites")
@login_required
def favorites_page():
    names = favorites.names_for_user(g.user["id"])
    platforms = [
        {**PLATFORM_BY_NAME[name], "avatar_key": PLATFORM_AVATAR_KEYS.get(name, "room")}
        for name in names
        if name in PLATFORM_BY_NAME
    ]
    return render_template(
        "pages/favorites.html",
        favorite_platforms=platforms,
        favorite_names=names,
        active_section="workspace",
    )


@blueprint.get("/account/data")
@login_required
def account_data_page():
    return render_template(
        "pages/account-data.html",
        personal_data=account_data.collect(g.user),
        active_section="workspace",
    )


CONTENT_PAGES = {
    "/city/leiden": ("leiden-rental-guide.html", "cities"),
    "/city/den-haag": ("den-haag-rental-guide.html", "cities"),
    "/rental-channels": ("housing-market.html", "guides"),
    "/housing-strategy": ("housing-strategy.html", "guides"),
    "/rental-materials": ("rental-materials.html", "guides"),
    "/housing-plan-b": ("plan-b.html", "guides"),
    "/deposit-return-netherlands.html": ("deposit-return-netherlands.html", "guides"),
    "/contact": ("contact.html", "contact"),
}


def _make_content_view(template_name: str, section: str):
    def content_view():
        return render_template(f"pages/{template_name}", active_section=section)

    return content_view


for route, (template_name, section) in CONTENT_PAGES.items():
    endpoint = "content_" + template_name.removesuffix(".html").replace("-", "_")
    blueprint.add_url_rule(route, endpoint, _make_content_view(template_name, section))


@blueprint.get("/privacy")
def privacy():
    return render_template(
        "pages/privacy.html",
        active_section="privacy",
        acknowledgement_requested=bool(request.args.get("acknowledge")),
        acknowledgement_next=safe_next(request.args.get("next") or "/workspace/strategy"),
    )


@blueprint.get("/leiden-rental-guide/")
def legacy_leiden_directory():
    return redirect("/city/leiden", code=301)


@blueprint.get("/deposit-return-netherlands/")
def legacy_deposit_directory():
    return redirect("/deposit-return-netherlands.html", code=301)


@blueprint.get("/preview-pages")
def preview_pages():
    if current_app.config["EXPATUS_SETTINGS"].is_production:
        abort(404)
    return render_template("pages/preview-pages.html")


@blueprint.get("/robots.txt")
def robots():
    settings = current_app.config["EXPATUS_SETTINGS"]
    content = (
        "User-agent: *\nAllow: /\n"
        "Disallow: /admin\nDisallow: /auth\nDisallow: /progress\n"
        "Disallow: /favorites\nDisallow: /workspace\nDisallow: /account\nDisallow: /api\n\n"
        f"Sitemap: {settings.base_url}/sitemap.xml\n"
    )
    return Response(content, mimetype="text/plain")


@blueprint.get("/sitemap.xml")
def sitemap():
    settings = current_app.config["EXPATUS_SETTINGS"]
    pages = [
        ("/", "weekly", "1.0"),
        ("/city/leiden", "monthly", "0.9"),
        ("/city/den-haag", "monthly", "0.9"),
        ("/shortstay", "daily", "0.8"),
        ("/rental-channels", "monthly", "0.8"),
        ("/housing-strategy", "monthly", "0.8"),
        ("/rental-materials", "monthly", "0.8"),
        ("/housing-plan-b", "monthly", "0.7"),
        ("/deposit-return-netherlands.html", "monthly", "0.8"),
        ("/contact", "yearly", "0.3"),
        ("/privacy", "yearly", "0.2"),
    ]
    entries = "".join(
        f"<url><loc>{settings.base_url}{path}</loc>"
        f"<changefreq>{frequency}</changefreq><priority>{priority}</priority></url>"
        for path, frequency, priority in pages
    )
    return Response(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{entries}</urlset>",
        mimetype="application/xml",
    )


ROOT_ASSETS = {
    "favicon.ico",
    "favicon-32x32.png",
    "favicon-48x48.png",
    "favicon-96x96.png",
    "apple-touch-icon.png",
    "icon-192x192.png",
    "icon-512x512.png",
    "logo-mark.png",
    "og-image.png",
    "site.webmanifest",
}


@blueprint.get("/<path:asset_name>")
def root_asset(asset_name: str):
    if asset_name in ROOT_ASSETS:
        return send_from_directory(PROJECT_ROOT / "static", asset_name)
    aliases = {
        "index.html": "/",
        "auth.html": "/auth",
        "account-login.html": "/auth",
        "my-housing-strategy.html": "/workspace/strategy",
        "my-rental-progress.html": "/progress",
        "favorites.html": "/favorites",
        "leiden-rental-guide.html": "/city/leiden",
        "den-haag-rental-guide.html": "/city/den-haag",
        "housing-market.html": "/rental-channels",
        "housing-strategy.html": "/housing-strategy",
        "rental-materials.html": "/rental-materials",
        "plan-b.html": "/housing-plan-b",
        "contact.html": "/contact",
        "privacy.html": "/privacy",
    }
    if asset_name in aliases:
        suffix = f"?{request.query_string.decode()}" if request.query_string else ""
        return redirect(aliases[asset_name] + suffix, code=301)
    abort(404)


@blueprint.get("/downloads/<path:file_name>")
def download(file_name: str):
    if file_name not in {"contract-checklist.pdf", "move-in-checklist.pdf"}:
        abort(404)
    return send_from_directory(PROJECT_ROOT / "static" / "downloads", file_name, as_attachment=True)
