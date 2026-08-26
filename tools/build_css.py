#!/usr/bin/env python3
"""Build one browser-ready CSS bundle per page from reusable source modules."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "static" / "css" / "src"
DIST = ROOT / "static" / "css" / "dist"
IMPORT_RE = re.compile(r'@import\s+url\(["\'](.*?)["\']\)\s*;', re.I)
URL_RE = re.compile(r'url\(\s*(["\']?)([^"\')]+)\1\s*\)', re.I)


def rebase_urls(source: str, module: Path, output: Path) -> str:
    def replace(match: re.Match[str]) -> str:
        value = match.group(2).strip()
        if value.startswith(("http://", "https://", "data:", "#")):
            return match.group(0)
        target = (module.parent / value).resolve()
        relative = os.path.relpath(target, output.parent).replace(os.sep, "/")
        return f'url("{relative}")'

    return URL_RE.sub(replace, source)


def expand(entry: Path, output: Path) -> tuple[str, list[str], list[str]]:
    active: set[Path] = set()
    modules: list[str] = []
    external: list[str] = []

    def walk(path: Path) -> str:
        path = path.resolve()
        if path in active:
            raise RuntimeError(f"CSS import cycle: {path}")
        if not path.exists():
            raise RuntimeError(f"Missing CSS module: {path}")
        active.add(path)
        modules.append(path.relative_to(ROOT).as_posix())
        source = path.read_text(encoding="utf-8")
        cursor = 0
        chunks: list[str] = []
        for match in IMPORT_RE.finditer(source):
            chunks.append(rebase_urls(source[cursor : match.start()], path, output))
            value = match.group(1)
            if value.startswith(("http://", "https://")):
                external.append(value)
            else:
                chunks.append(walk(path.parent / value))
            cursor = match.end()
        chunks.append(rebase_urls(source[cursor:], path, output))
        active.remove(path)
        return "".join(chunks)

    return walk(entry), modules, external


def main() -> None:
    DIST.mkdir(parents=True, exist_ok=True)
    manifest = {"bundles": {}}
    for entry in sorted((SRC / "pages").glob("*.css")):
        output = DIST / entry.name
        content, modules, external = expand(entry, output)
        banner = (
            f"/* Generated from static/css/src/pages/{entry.name}.\n"
            " * Edit source modules and run: python tools/build_css.py\n"
            " */\n"
        )
        built = banner + content.strip() + "\n"
        output.write_text(built, encoding="utf-8")
        manifest["bundles"][entry.name] = {
            "sha256": hashlib.sha256(built.encode()).hexdigest(),
            "source_modules": modules,
            "external_stylesheets": list(dict.fromkeys(external)),
        }
    (DIST / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Built {len(manifest['bundles'])} CSS page bundles")


if __name__ == "__main__":
    main()
