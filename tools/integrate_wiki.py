#!/usr/bin/env python3
"""Connect the generated local player wiki to the existing static website."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup


MIRAHEZE_MAIN = "https://chronoromancer.miraheze.org/wiki/Main_Page"
SITE_ROOT = "https://chronoromancergame.com"
ZH_CATEGORIES = {
    "Overview": "概览",
    "Characters": "角色",
    "Game Systems": "游戏系统",
    "Reference": "参考资料",
    "Walkthroughs": "流程攻略",
    "World & Reference": "世界与参考资料",
}


def depth_prefix(root: Path, path: Path) -> str:
    relative = path.relative_to(root)
    return "../" * (len(relative.parts) - 1)


def update_html(root: Path) -> int:
    changed = 0
    for path in sorted(root.rglob("*.html")):
        relative = path.relative_to(root)
        if relative.parts and relative.parts[0] == "wiki":
            continue
        source = path.read_text(encoding="utf-8")
        if "community.wiki" not in source and MIRAHEZE_MAIN not in source:
            continue
        target = f"{depth_prefix(root, path)}wiki.html"

        def local_anchor(match: re.Match[str]) -> str:
            attributes = match.group(1)
            attributes = re.sub(r'\s+(?:data-config-link|href)="[^"]*"', "", attributes)
            attributes = re.sub(r'\s+target="_blank"', "", attributes)
            attributes = re.sub(r'\s+rel="noopener noreferrer"', "", attributes)
            return f'<a{attributes} href="{target}">'

        updated = re.sub(
            r'<a([^>]*\sdata-config-link="community\.wiki"[^>]*)>',
            local_anchor,
            source,
        )
        updated = re.sub(
            rf'<a([^>]*\shref="{re.escape(MIRAHEZE_MAIN)}"[^>]*)>',
            local_anchor,
            updated,
        )
        if path.name == "main.html":
            updated = updated.replace(
                "A useful community-maintained Miraheze wiki with player knowledge, tips, and possible story spoilers.",
                "A searchable bilingual library adapted from the living community wiki, with character routes, systems, tips, and possible story spoilers.",
            ).replace(
                "由玩家维护的实用 Miraheze Wiki，收录社区资料与游戏提示，其中可能包含剧情剧透。",
                "由持续更新的社区 Wiki 整理而成的中英双语资料库，收录角色路线、系统、提示，并可能包含剧情剧透。",
            ).replace(
                "Open the player wiki →",
                "Browse the player wiki →",
            ).replace(
                "打开玩家 Wiki →",
                "浏览玩家 Wiki →",
            )
        if updated != source:
            path.write_text(updated, encoding="utf-8", newline="\n")
            changed += 1
    return changed


def update_sitemap(root: Path) -> int:
    sitemap_path = root / "sitemap.xml"
    source = sitemap_path.read_text(encoding="utf-8")
    manifest = json.loads((root / "wiki-manifest.json").read_text(encoding="utf-8"))
    urls = [f"{SITE_ROOT}/wiki.html"] + [
        f"{SITE_ROOT}/wiki/{entry['slug']}.html" for entry in manifest.get("pages", [])
    ]
    existing = set(re.findall(r"<loc>(.*?)</loc>", source))
    additions = [url for url in urls if url not in existing]
    if not additions:
        return 0
    block = "\n".join(f"  <url><loc>{url}</loc></url>" for url in additions)
    updated = source.replace("</urlset>", f"{block}\n</urlset>")
    sitemap_path.write_text(updated, encoding="utf-8", newline="\n")
    return len(additions)


def normalize_wiki_filters(root: Path) -> int:
    path = root / "wiki.html"
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    changed = 0
    for button in soup.select("[data-wiki-filter]"):
        direct_spans = button.find_all("span", recursive=False)
        if len(direct_spans) == 2 and direct_spans[0].has_attr("data-copy-en"):
            continue
        count = direct_spans[-1].get_text(strip=True) if direct_spans else ""
        category = button.get("data-wiki-filter", "")
        english = "All" if category == "all" else category
        chinese = "全部" if category == "all" else ZH_CATEGORIES.get(category, english)
        button.clear()
        label = soup.new_tag("span")
        label["data-copy-en"] = english
        label["data-copy-zh"] = chinese
        label.string = english
        count_label = soup.new_tag("span")
        count_label.string = count
        button.append(label)
        button.append(" ")
        button.append(count_label)
        button.attrs.pop("data-copy-en", None)
        button.attrs.pop("data-copy-zh", None)
        changed += 1
    if changed:
        path.write_text(str(soup), encoding="utf-8", newline="\n")
    return changed


def remove_generated_comments(root: Path) -> int:
    """Discard parser/debug comments inherited from MediaWiki output."""
    changed = 0
    for path in sorted((root / "wiki").glob("*.html")):
        source = path.read_text(encoding="utf-8")
        updated = re.sub(r"<!--.*?-->", "", source, flags=re.DOTALL)
        if updated != source:
            path.write_text(updated, encoding="utf-8", newline="\n")
            changed += 1
    return changed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, nargs="?", default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    html_count = update_html(root)
    sitemap_count = update_sitemap(root)
    filter_count = normalize_wiki_filters(root)
    cleaned_count = remove_generated_comments(root)
    print(f"updated {html_count} existing HTML files")
    print(f"added {sitemap_count} wiki URLs to sitemap.xml")
    print(f"normalized {filter_count} bilingual wiki filters")
    print(f"removed inherited parser comments from {cleaned_count} wiki pages")


if __name__ == "__main__":
    main()
