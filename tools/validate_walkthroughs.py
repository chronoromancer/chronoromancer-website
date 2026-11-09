from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup


SITE = Path(__file__).resolve().parents[1]
SOURCE = Path(r"D:\GAME_MAKER\Chronoromancer\game\walkthroughs")
MANIFEST = SITE / "assets" / "data" / "walkthroughs.json"


errors: list[str] = []
manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
mapping_path = SITE / "editorial/wiki/parallel-guides.json"
if mapping_path.is_file():
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    english = sorted(Path(row["path"]).stem.casefold() for row in mapping["guides"])
else:
    english = sorted(path.stem.casefold() for path in SOURCE.glob("*.md"))
generated = sorted(path.stem.casefold() for path in (SITE / "guides").glob("*.html"))

if english != generated:
    errors.append("Generated guide filenames do not match the English source set.")
if manifest["total"] != len(english):
    errors.append("Manifest total does not match the source count.")

pages = [SITE / "walkthroughs.html", *sorted((SITE / "guides").glob("*.html"))]
for page in pages:
    text = page.read_text(encoding="utf-8")
    soup = BeautifulSoup(text, "html.parser")
    ids = [str(tag["id"]) for tag in soup.find_all(id=True)]
    if len(ids) != len(set(ids)):
        errors.append(f"Duplicate IDs in {page.relative_to(SITE)}")
    for element in soup.find_all(["a", "link", "script", "img"]):
        attribute = "href" if element.name in {"a", "link"} else "src"
        value = element.get(attribute)
        if not value or value.startswith(("http://", "https://", "mailto:", "data:", "javascript:")):
            continue
        if attribute == "href" and urlsplit(value).path.lower().endswith(".md"):
            errors.append(f"Unconverted Markdown link in {page.relative_to(SITE)}: {value}")
        parts = urlsplit(value)
        if not parts.path:
            target = page
        else:
            target = (page.parent / unquote(parts.path)).resolve()
        if not target.exists():
            errors.append(f"Missing local target from {page.relative_to(SITE)}: {value}")
            continue
        if parts.fragment and target.suffix.lower() == ".html":
            target_soup = soup if target == page.resolve() else BeautifulSoup(target.read_text(encoding="utf-8"), "html.parser")
            if target_soup.find(id=unquote(parts.fragment)) is None:
                errors.append(f"Missing anchor from {page.relative_to(SITE)}: {value}")

    if page.parent.name == "guides":
        if not soup.select_one('[data-lang-panel="en"] .markdown-body, .markdown-body[data-lang-panel="en"], .wiki-source-content[data-lang-panel="en"]'):
            errors.append(f"Missing English content panel in {page.name}")
        if not soup.select_one('[data-lang-panel="zh"] .markdown-body, .markdown-body[data-lang-panel="zh"], .wiki-source-content[data-lang-panel="zh"]'):
            errors.append(f"Missing Chinese content panel in {page.name}")

for filename in ["main.html", "story.html", "characters.html", "screenshots.html", "privacy.html", "terms.html"]:
    text = (SITE / filename).read_text(encoding="utf-8")
    if 'href="walkthroughs.html" data-i18n="navGuides"' not in text:
        errors.append(f"Guides navigation missing from {filename}")

if errors:
    print("Validation failed:")
    for error in errors:
        print(f"- {error}")
    raise SystemExit(1)

print(f"Validated {len(pages) - 1} guide pages, the library index, local assets, internal links, anchors, and navigation.")
