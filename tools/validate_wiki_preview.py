#!/usr/bin/env python3
"""Validate a generated Chronoromancer website-wiki preview."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup


def validate(root: Path) -> None:
    manifest_path = root / "wiki-manifest.json"
    wiki_dir = root / "wiki"
    errors: list[str] = []
    warnings: list[str] = []

    if not manifest_path.is_file():
        raise SystemExit(f"missing manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = manifest.get("pages", [])
    slugs = [entry.get("slug", "") for entry in entries]
    if len(slugs) != len(set(slugs)):
        errors.append("manifest contains duplicate slugs")

    files = sorted(wiki_dir.glob("*.html"))
    if len(files) != len(entries):
        errors.append(f"manifest has {len(entries)} pages but wiki directory has {len(files)} HTML files")

    expected = {f"{slug}.html" for slug in slugs}
    for entry in entries:
        if not entry.get("revision_id"):
            errors.append(f"{entry.get('title')}: missing live revision ID")

    unresolved_articles: set[str] = set()
    page_ids: dict[str, set[str]] = {}
    page_links: list[tuple[str, str]] = []
    for path in files:
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        ids = [str(tag["id"]) for tag in soup.select("[id]")]
        if len(ids) != len(set(ids)):
            errors.append(f"{path.name}: duplicate document IDs")
        page_ids[path.name] = set(ids)
        if not soup.select_one(".wiki-page-hero h1"):
            errors.append(f"{path.name}: missing page heading")
        english = soup.select_one(".wiki-source-content[data-lang-panel='en']")
        chinese = soup.select_one(".wiki-source-content[data-lang-panel='zh']")
        content = english
        if content is None:
            errors.append(f"{path.name}: missing imported English article content")
            continue
        if chinese is None or not chinese.get_text(" ", strip=True):
            errors.append(f"{path.name}: missing imported Simplified Chinese article content")
        else:
            chinese_text = chinese.get_text(" ", strip=True)
            if re.search(r"\[\s*NAME\s*\d+\s*\]|NAME\d+|<\s*x\s*\d+\s*>|(?:\\x){3,}", chinese_text, re.I):
                errors.append(f"{path.name}: leaked translation marker or corrupted placeholder")
            if any(marker in chinese_text for marker in ("NewPP limit report", "新PP限制报告", "Saved in parser cache", "Render ID")):
                errors.append(f"{path.name}: inherited MediaWiki parser diagnostics are visible")
            if re.search(r"(.{2,16})(?:\s*\1){5,}", chinese_text) or re.search(r"(\S{2,20})(?:\s+\1){5,}", chinese_text):
                errors.append(f"{path.name}: probable repeated translation output")
        if content.select("script, style, iframe, form, input, button"):
            errors.append(f"{path.name}: unsafe interactive markup remained inside imported content")

        for link in soup.select("a[href]"):
            href = link.get("href", "")
            parsed = urlparse(href)
            if href.startswith("/"):
                errors.append(f"{path.name}: root-relative link remained: {href}")
            if parsed.scheme in {"http", "https", "mailto"}:
                if (
                    "chronoromancer.miraheze.org/wiki/" in href
                    and not any(marker in href for marker in ("/wiki/File:", "/wiki/Special:", "/wiki/Talk:", "/wiki/User:"))
                    and "wiki-source-line" not in " ".join(link.parent.get("class", []))
                ):
                    unresolved_articles.add(href)
                continue
            if parsed.scheme:
                warnings.append(f"{path.name}: unusual link scheme: {href}")
                continue
            target_name = Path(parsed.path).name
            if parsed.fragment and (not parsed.path or target_name in expected):
                page_links.append((path.name, href))
            if target_name.endswith(".html") and target_name not in expected and target_name != "wiki.html":
                # Shell navigation targets live outside the preview's wiki folder.
                if not href.startswith("../"):
                    errors.append(f"{path.name}: missing local article target: {href}")

        for image in content.select("img[src]"):
            source = image.get("src", "")
            if source.startswith(("http://", "https://")):
                errors.append(f"{path.name}: remote article image was not localized: {source}")
            elif not source.startswith("../assets/images/wiki/"):
                errors.append(f"{path.name}: unsupported image source: {source}")
            else:
                target = (path.parent / source).resolve()
                if not target.is_file():
                    errors.append(f"{path.name}: missing localized article image: {source}")

    for source_name, href in page_links:
        parsed = urlparse(href)
        target_name = Path(parsed.path).name or source_name
        if target_name in page_ids and parsed.fragment not in page_ids[target_name]:
            errors.append(f"{source_name}: missing fragment target in {target_name}: #{parsed.fragment}")

    index_path = root / "wiki.html"
    if not index_path.is_file():
        errors.append("missing wiki.html index")
    else:
        index = BeautifulSoup(index_path.read_text(encoding="utf-8"), "html.parser")
        card_count = len(index.select("[data-wiki-card]"))
        expected_cards = len(entries)
        if card_count != expected_cards:
            errors.append(f"wiki index has {card_count} cards; expected {expected_cards}")

    if unresolved_articles:
        warnings.append(f"{len(unresolved_articles)} unresolved or redirecting Miraheze article links remain")

    print(f"Validated {len(files)} wiki article pages and {len(entries)} manifest records.")
    for warning in warnings:
        print(f"WARNING: {warning}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    print("Wiki preview validation passed.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, help="Directory containing wiki.html, wiki/, and wiki-manifest.json")
    args = parser.parse_args()
    validate(args.root.resolve())


if __name__ == "__main__":
    main()
