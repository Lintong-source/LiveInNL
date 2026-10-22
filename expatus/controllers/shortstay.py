"""Public, read-only Shortstay routes. No scraper or admin action is exposed."""
from flask import Blueprint, current_app, jsonify, render_template, request
from expatus.repositories.shortstay import MARKETS, query_listings

blueprint = Blueprint("shortstay", __name__)

@blueprint.get("/shortstay")
def page():
    # Real, read-only server-rendered content for users and crawlers.
    # There is no scraper, Groq call or data mutation on a page view.
    initial = {"configured": False, "count": 0, "items": []}
    try:
        initial = query_listings("leiden", "30d")
    except Exception:
        # SEO must not make the public page unavailable when Turso is down.
        current_app.logger.exception("Shortstay initial HTML catalog read failed")
    return render_template(
        "pages/shortstay.html",
        active_section="shortstay",
        markets=MARKETS,
        ss_initial=initial,
    )

@blueprint.get("/api/shortstay/listings")
def listings():
    market = (request.args.get("market") or "leiden").strip().lower()
    mode = (request.args.get("mode") or "today").strip().lower()
    if market not in MARKETS or mode not in {"today", "30d"}:
        return jsonify(error="无效的城市或时间范围"), 400
    try:
        result = query_listings(market, mode)
    except Exception:
        current_app.logger.exception("Shortstay read failed")
        return jsonify(error="房源暂时无法读取，请稍后再试"), 503
    response = jsonify({"market": market, "mode": mode, "max_age_days": 30, **result})
    response.headers["Cache-Control"] = "public, max-age=60"
    return response
