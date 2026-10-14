#!/usr/bin/env python3
"""Validate local links and assets across the static Chronoromancer website."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup


def validate(root: Path) -> None:
    errors: list[str] = []
    pages = sorted(root.rglob("*.html"))
    soups: dict[Path, BeautifulSoup] = {}

    def soup_for(path: Path) -> BeautifulSoup:
        resolved = path.resolve()
        if resolved not in soups:
            soups[resolved] = BeautifulSoup(resolved.read_text(encoding="utf-8"), "html.parser")
        return soups[resolved]

    for page in pages:
        soup = soup_for(page)
        for element, attribute in (
            *((link, "href") for link in soup.select("a[href]")),
            *((image, "src") for image in soup.select("img[src]")),
            *((script, "src") for script in soup.select("script[src]")),
            *((style, "href") for style in soup.select("link[rel='stylesheet'][href]")),
        ):
            reference = element.get(attribute, "").strip()
            parsed = urlsplit(reference)
            if not reference or parsed.scheme or parsed.netloc or reference.startswith(("#", "//")):
                continue
            relative_path = Path(unquote(parsed.path.replace("/", os.sep)))
            target = (root / str(relative_path).lstrip("\\/")) if parsed.path.startswith("/") else (page.parent / relative_path)
            if not parsed.path:
                target = page
            if target.is_dir():
                target = target / "index.html"
            target = target.resolve()
            try:
                target.relative_to(root.resolve())
            except ValueError:
                errors.append(f"{page.relative_to(root)}: reference leaves website root: {reference}")
                continue
            if not target.is_file():
                errors.append(f"{page.relative_to(root)}: missing local target: {reference}")
                continue
            if parsed.fragment and target.suffix.casefold() in {".html", ".htm"}:
                target_soup = soup_for(target)
                identifiers = {str(tag["id"]) for tag in target_soup.select("[id]")}
                if unquote(parsed.fragment) not in identifiers:
                    errors.append(
                        f"{page.relative_to(root)}: missing fragment in {target.relative_to(root)}: #{parsed.fragment}"
                    )

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    print(f"Validated {len(pages)} HTML pages with no missing local links, assets, or fragments.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, nargs="?", default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    validate(args.root.resolve())


if __name__ == "__main__":
    main()
