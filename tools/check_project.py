#!/usr/bin/env python3
"""Run dependency-free structural checks before sharing a local test build."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    failures = []
    source_files = sorted((ROOT / "expatus").rglob("*.py"))
    for path in source_files + [ROOT / "app.py", ROOT / "wsgi.py"]:
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as error:
            failures.append(f"Python syntax: {path.relative_to(ROOT)}: {error}")

    page_files = sorted((ROOT / "templates" / "pages").glob("*.html"))
    for path in page_files:
        text = path.read_text(encoding="utf-8")
        if "https://expatus.nl" in text:
            failures.append(f"Apex canonical/domain remains in {path.relative_to(ROOT)}")
        if "googletagmanager.com/gtag/js" in text:
            failures.append(f"Direct analytics script remains in {path.relative_to(ROOT)}")
        if "<style" in text.lower():
            failures.append(f"Inline style block remains in {path.relative_to(ROOT)}")
        for relative in re.findall(r'href="(/static/css/dist/[^\"]+)"', text):
            if not (ROOT / relative.lstrip("/")).is_file():
                failures.append(f"Missing CSS bundle {relative} used by {path.name}")

    strategy_script = (ROOT / "static" / "js" / "my-housing-strategy.js").read_text(encoding="utf-8")
    if "expatus-progress-preview" in strategy_script or "localStorage" in strategy_script:
        failures.append("Strategy workspace must not read or write account-agnostic browser storage")
    if "/api/strategies/current" not in strategy_script:
        failures.append("Strategy workspace does not request a complete account-owned backend strategy")
    for rule_name in ("statusFor", "channelData", "effortData", "progressDiagnosis"):
        if re.search(rf"function\s+{rule_name}\s*\(", strategy_script):
            failures.append(f"Frontend still contains backend strategy rule: {rule_name}")
    favorites_page = (ROOT / "templates" / "pages" / "favorites.html").read_text(encoding="utf-8")
    if "expatus-avatar--dynamic" in favorites_page:
        failures.append("Favorites still use an undefined dynamic avatar style")

    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    production_release = (ROOT / "VERSION").is_file()
    required_values = (
        ("APP_ENV=production", "DATABASE_BACKEND=turso", "ANALYTICS_ENABLED=0", "BASE_URL=https://www.expatus.nl")
        if production_release
        else ("APP_ENV=development", "DATABASE_BACKEND=sqlite", "ANALYTICS_ENABLED=0", "BASE_URL=https://www.expatus.nl")
    )
    for required in required_values:
        if required not in env_example:
            failures.append(f"Unsafe or missing local default: {required}")

    if failures:
        for failure in failures:
            print("FAIL:", failure)
        return 1
    print(f"Checked {len(source_files)} application modules and {len(page_files)} HTML pages.")
    print("Local SQLite isolation, disabled analytics, canonical domain and CSS bundles: OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
