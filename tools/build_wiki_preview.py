#!/usr/bin/env python3
"""Build a local static preview from the live Chronoromancer Miraheze wiki.

This deliberately writes outside the public website by default.  It is the
first stage of the bilingual website-wiki pipeline: fetch the current public
revision, clean MediaWiki-only controls, rewrite links, and render the result
inside the Chronoromancer website design.  Publishing and Chinese translation
are separate, explicit stages.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from bs4 import BeautifulSoup, Tag


API = "https://chronoromancer.miraheze.org/w/api.php"
WIKI_ROOT = "https://chronoromancer.miraheze.org"
USER_AGENT = "ChronoromancerWebsiteWikiPreview/1.0 (official website build tool)"
DEFAULT_TITLES = (
    "Main Page",
    "Character:Miki",
    "Game Systems:Brothel",
    "Items",
    "Walkthrough:Early Game",
)


@dataclass(frozen=True)
class PageInfo:
    title: str
    slug: str
    revision_id: int
    revision_timestamp: str
    html: str
    image_count: int
    category: str


def api_get(params: dict[str, str], attempts: int = 4) -> dict:
    query = urllib.parse.urlencode({**params, "format": "json", "formatversion": "2"})
    request = urllib.request.Request(f"{API}?{query}", headers={"User-Agent": USER_AGENT})
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError):
            if attempt + 1 == attempts:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("unreachable")


def page_slug(title: str) -> str:
    value = title.casefold().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "page"


def page_category(title: str) -> str:
    if title == "Main Page":
        return "Overview"
    if title.startswith("Character:"):
        return "Characters"
    if title.startswith("Game Systems:"):
        return "Game Systems"
    if title.startswith("Walkthrough:"):
        return "Walkthroughs"
    if title in {"Items", "Skills", "Locations", "FAQ"}:
        return "Reference"
    return "World & Reference"


def fetch_all_titles() -> list[str]:
    titles: list[str] = []
    continuation: dict[str, str] = {}
    while True:
        payload = api_get(
            {
                "action": "query",
                "generator": "allpages",
                "gapnamespace": "0",
                "gaplimit": "max",
                "prop": "info",
                **continuation,
            }
        )
        for page in payload.get("query", {}).get("pages", []):
            if not page.get("redirect"):
                titles.append(page["title"])
        if "continue" not in payload:
            break
        continuation = payload["continue"]
    return sorted(set(titles), key=str.casefold)


def fetch_redirect_map() -> dict[str, str]:
    redirect_titles: list[str] = []
    continuation: dict[str, str] = {}
    while True:
        payload = api_get(
            {
                "action": "query",
                "list": "allpages",
                "apnamespace": "0",
                "apfilterredir": "redirects",
                "aplimit": "max",
                **continuation,
            }
        )
        redirect_titles.extend(page["title"] for page in payload.get("query", {}).get("allpages", []))
        if "continue" not in payload:
            break
        continuation = payload["continue"]

    redirect_map: dict[str, str] = {}
    for batch in chunks(redirect_titles, 50):
        payload = api_get(
            {
                "action": "query",
                "redirects": "1",
                "titles": "|".join(batch),
            }
        )
        for item in payload.get("query", {}).get("redirects", []):
            redirect_map[item["from"].casefold()] = item["to"]
    return redirect_map


def chunks(values: list[str], size: int) -> Iterable[list[str]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def fetch_revisions(titles: list[str]) -> dict[str, tuple[int, str]]:
    revisions: dict[str, tuple[int, str]] = {}
    for batch in chunks(titles, 50):
        payload = api_get(
            {
                "action": "query",
                "prop": "revisions",
                "rvprop": "ids|timestamp",
                "titles": "|".join(batch),
            }
        )
        for page in payload.get("query", {}).get("pages", []):
            revision = page.get("revisions", [{}])[0]
            revisions[page["title"].casefold()] = (
                int(revision.get("revid", 0)),
                revision.get("timestamp", ""),
            )
    return revisions


def fetch_page(title: str, revision: tuple[int, str] = (0, "")) -> PageInfo:
    parsed = api_get(
        {
            "action": "parse",
            "page": title,
            "prop": "text|images|displaytitle",
        }
    )["parse"]
    revision_id, revision_timestamp = revision
    return PageInfo(
        title=title,
        slug=page_slug(title),
        revision_id=revision_id,
        revision_timestamp=revision_timestamp,
        html=parsed["text"],
        image_count=len(parsed.get("images", [])),
        category=page_category(title),
    )


def normalize_wiki_title(href: str) -> tuple[str, str] | None:
    parsed = urllib.parse.urlparse(href)
    if parsed.netloc and parsed.netloc not in {
        "chronoromancer.miraheze.org",
        "www.chronoromancer.miraheze.org",
    }:
        return None
    if not parsed.path.startswith("/wiki/"):
        return None
    title = urllib.parse.unquote(parsed.path.removeprefix("/wiki/")).replace("_", " ")
    return title, parsed.fragment


def clean_article(page: PageInfo, known_slugs: dict[str, str]) -> tuple[str, list[dict[str, str]]]:
    soup = BeautifulSoup(page.html, "html.parser")
    root = soup.select_one(".mw-parser-output") or soup

    for selector in (
        ".mw-editsection",
        ".mw-jump-link",
        "meta",
        "script",
        "style",
        "noscript",
    ):
        for element in root.select(selector):
            element.decompose()

    # Miraheze articles often contain their own decorated title and navigation
    # box. The website shell supplies both, so keeping these would create a
    # duplicated title and two competing tables of contents.
    display_title = page.title.split(":", 1)[-1].strip().casefold()
    for block in list(root.find_all("div", recursive=False)):
        block_text = block.get_text(" ", strip=True)
        normalized = re.sub(r"\s+", " ", block_text).strip().casefold()
        style = block.get("style", "").casefold()
        link_count = len(block.find_all("a"))
        if normalized == display_title and "font-size:1.5em" in style:
            block.decompose()
            continue
        if "quick navigation" in normalized[:80] and link_count >= 2:
            block.decompose()

    for element in root.find_all(True):
        for attribute in list(element.attrs):
            lowered = attribute.casefold()
            if lowered.startswith("on") or lowered in {"contenteditable", "srcset"}:
                del element.attrs[attribute]

    for image in root.find_all("img"):
        source = image.get("src", "")
        if source.startswith("//"):
            image["src"] = "https:" + source
        elif source.startswith("/"):
            image["src"] = WIKI_ROOT + source
        image["loading"] = "lazy"
        image["decoding"] = "async"
        if not image.get("alt"):
            image["alt"] = ""

    for link in root.find_all("a", href=True):
        href = link["href"]
        if "redlink=1" in href:
            link.unwrap()
            continue
        target = normalize_wiki_title(href)
        if target is None:
            if href.startswith("//"):
                link["href"] = "https:" + href
            elif href.startswith("/"):
                link["href"] = WIKI_ROOT + href
            continue
        title, fragment = target
        if title.startswith(("File:", "Special:", "Talk:", "User:")):
            link["href"] = WIKI_ROOT + href
            link["target"] = "_blank"
            link["rel"] = "noopener noreferrer"
            continue
        slug = known_slugs.get(title.casefold())
        if slug:
            link["href"] = f"{slug}.html" + (f"#{fragment}" if fragment else "")
        else:
            link["href"] = WIKI_ROOT + href
            link["target"] = "_blank"
            link["rel"] = "noopener noreferrer"

    headings: list[dict[str, str]] = []
    used_ids: set[str] = set()
    for heading in root.find_all(["h2", "h3"]):
        label = heading.get_text(" ", strip=True)
        if not label:
            continue
        identifier = heading.get("id") or page_slug(label)
        base = identifier
        suffix = 2
        while identifier in used_ids:
            identifier = f"{base}-{suffix}"
            suffix += 1
        heading["id"] = identifier
        used_ids.add(identifier)
        headings.append({"id": identifier, "label": label, "level": heading.name})

    return str(root), headings


def relative_time_label(timestamp: str) -> str:
    if not timestamp:
        return "Unknown revision date"
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    utc_value = parsed.astimezone(timezone.utc)
    return f"{utc_value.strftime('%B')} {utc_value.day}, {utc_value.year}"


def shell_head(title: str, depth: int = 1) -> str:
    prefix = "../" * depth
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{html.escape(title)} — Chronoromancer player knowledge in English and Simplified Chinese.">
  <link rel="icon" type="image/png" href="{prefix}assets/images/v2/favicon.png">
  <link rel="stylesheet" href="{prefix}assets/css/style.css"><link rel="stylesheet" href="{prefix}assets/css/wiki.css">
  <title>{html.escape(title)} | Chronoromancer Wiki</title></head>'''


def site_header(depth: int = 1, active: bool = True) -> str:
    prefix = "../" * depth
    active_class = ' class="is-active"' if active else ""
    return f'''<a class="skip-link" href="#content" data-copy-en="Skip to content" data-copy-zh="跳至正文">Skip to content</a>
  <div class="maturity-bar" data-copy-en="18+ adults-only game · Wiki pages may contain story and gameplay spoilers" data-copy-zh="18+ 仅限成人游戏 · Wiki 页面可能包含剧情与玩法剧透">18+ adults-only game · Wiki pages may contain story and gameplay spoilers</div>
  <header class="site-header"><div class="container header-inner">
    <a class="brand" href="{prefix}main.html" aria-label="Chronoromancer home"><img src="{prefix}assets/images/v2/logo.png" alt="Chronoromancer"></a>
    <button class="nav-toggle" type="button" data-nav-toggle aria-expanded="false" aria-label="Open navigation"><span></span><span></span><span></span></button>
    <nav class="site-nav" data-nav-menu aria-label="Primary navigation">
      <a href="{prefix}main.html" data-i18n="navHome">Home</a><a href="{prefix}story.html" data-i18n="navStory">Story</a>
      <a href="{prefix}characters.html" data-i18n="navCharacters">Characters</a><a href="{prefix}walkthroughs.html" data-i18n="navGuides">Guides</a>
      <a href="{prefix}screenshots.html" data-i18n="navGallery">Gallery</a><a{active_class} href="{prefix}wiki.html" data-i18n="navWiki">Player Wiki</a>
      <a href="{prefix}main.html#download" data-i18n="navDownload">Download</a>
      <div class="language-switch" role="group" aria-label="Language"><button type="button" data-language="en" aria-pressed="true">EN</button><button type="button" data-language="zh" aria-pressed="false">简体中文</button></div>
    </nav>
  </div></header>'''


def site_footer(depth: int = 1) -> str:
    prefix = "../" * depth
    return f'''<footer class="site-footer"><div class="container"><div class="footer-grid">
    <div class="footer-brand"><img src="{prefix}assets/images/v2/logo.png" alt="Chronoromancer"><p data-i18n="footerDescription">An adults-only time-travel sandbox RPG. Public website artwork is SFW.</p></div>
    <div class="footer-column"><h2 data-i18n="footerExplore">Explore</h2><a href="{prefix}story.html" data-i18n="navStory">Story</a><a href="{prefix}characters.html" data-i18n="navCharacters">Characters</a><a href="{prefix}walkthroughs.html" data-i18n="navGuides">Guides</a><a href="{prefix}wiki.html" data-i18n="navWiki">Player Wiki</a></div>
    <div class="footer-column"><h2 data-i18n="footerCommunity">Community</h2><a data-config-link="community.discord" target="_blank" rel="noopener noreferrer">Discord</a><a data-config-link="community.telegram" target="_blank" rel="noopener noreferrer">Telegram</a><a data-config-link="community.patreon" target="_blank" rel="noopener noreferrer">Patreon</a></div>
    <div class="footer-column"><h2 data-i18n="footerLegal">Legal</h2><a href="{prefix}privacy.html" data-i18n="footerPrivacy">Privacy</a><a href="{prefix}terms.html" data-i18n="footerTerms">Terms</a></div>
  </div><div class="footer-bottom"><span>© <span data-current-year></span> <span data-i18n="copyright">Chronoromancer Studio. All rights reserved.</span></span><span data-copy-en="Player knowledge · English / Simplified Chinese" data-copy-zh="玩家资料 · English / 简体中文">Player knowledge · English / Simplified Chinese</span></div></div></footer>'''


def scripts(depth: int = 1) -> str:
    prefix = "../" * depth
    return f'''<script src="{prefix}assets/js/site-config.js"></script><script src="{prefix}assets/js/site.js"></script><script src="{prefix}assets/js/wiki.js"></script>'''


def article_page(page: PageInfo, article_html: str, headings: list[dict[str, str]]) -> str:
    display_title = page.title.split(":", 1)[-1]
    source_url = WIKI_ROOT + "/wiki/" + urllib.parse.quote(page.title.replace(" ", "_"), safe=":_()')")
    toc = "".join(
        f'<a class="wiki-toc-{entry["level"]}" href="#{html.escape(entry["id"])}">{html.escape(entry["label"])}</a>'
        for entry in headings
    )
    updated = relative_time_label(page.revision_timestamp)
    return f'''{shell_head(display_title)}
<body class="wiki-article-page" data-title-en="{html.escape(display_title)} | Chronoromancer Wiki" data-title-zh="{html.escape(display_title)} | Chronoromancer 玩家 Wiki">
  {site_header()}
  <main id="content">
    <section class="wiki-page-hero"><div class="container">
      <nav class="breadcrumb" aria-label="Breadcrumb"><a href="../wiki.html" data-copy-en="Player Wiki" data-copy-zh="玩家 Wiki">Player Wiki</a><span>/</span><span>{html.escape(page.category)}</span></nav>
      <p class="eyebrow" data-copy-en="Community knowledge, preserved on the official site" data-copy-zh="社区知识，保存于官方网站">Community knowledge, preserved on the official site</p>
      <h1>{html.escape(display_title)}</h1>
      <div class="wiki-source-line"><span data-copy-en="Live wiki revision {page.revision_id} · {html.escape(updated)}" data-copy-zh="玩家 Wiki 修订版 {page.revision_id} · {html.escape(updated)}">Live wiki revision {page.revision_id} · {html.escape(updated)}</span><a href="{html.escape(source_url)}" target="_blank" rel="noopener noreferrer" data-copy-en="View or improve the source →" data-copy-zh="查看或完善原始页面 →">View or improve the source →</a></div>
    </div></section>
    <section class="section wiki-reading-section"><div class="container wiki-reading-layout">
      <aside class="wiki-toc"><div class="wiki-toc-inner"><button class="wiki-toc-toggle" type="button" data-wiki-toc-toggle aria-expanded="false"><span data-copy-en="On this page" data-copy-zh="本页目录">On this page</span><span aria-hidden="true">+</span></button><p class="wiki-toc-heading" data-copy-en="On this page" data-copy-zh="本页目录">On this page</p><div class="wiki-toc-links" data-wiki-toc-links>{toc or '<span class="wiki-toc-empty">Single-section article</span>'}</div></div></aside>
      <article class="wiki-article">
        <div class="spoiler-notice"><strong data-copy-en="Player wiki notice" data-copy-zh="玩家 Wiki 提示">Player wiki notice</strong><span data-copy-en="This community-maintained page may contain gameplay, story, and mature-content spoilers." data-copy-zh="此社区维护页面可能包含玩法、剧情及成人内容剧透。">This community-maintained page may contain gameplay, story, and mature-content spoilers.</span></div>
        <div class="wiki-language-note" data-lang-panel="zh" hidden><strong>简体中文版本正在制作中</strong><p>此预览用于确认页面结构和图片。完整中文译文通过审核前，不会发布到正式网站。</p></div>
        <div class="wiki-source-content" data-lang-panel="en">{article_html}</div>
      </article>
    </div></section>
  </main>
  {site_footer()}{scripts()}
</body></html>'''


def index_page(pages: Iterable[PageInfo]) -> str:
    page_list = list(pages)
    cards = []
    for page in page_list:
        title = page.title.split(":", 1)[-1]
        cards.append(
            f'''<article class="wiki-card" data-wiki-card data-category="{html.escape(page.category)}" data-search="{html.escape((page.title + ' ' + page.category).casefold())}">
              <div><span class="wiki-card-category">{html.escape(page.category)}</span><span class="wiki-card-images">{page.image_count} image{'s' if page.image_count != 1 else ''}</span></div>
              <h2>{html.escape(title)}</h2><p>Live revision {page.revision_id}</p><a href="wiki/{page.slug}.html">Read article →</a>
            </article>'''
        )
    categories = sorted({page.category for page in page_list})
    filters = ['<button class="filter-button is-active" type="button" data-wiki-filter="all"><span data-copy-en="All" data-copy-zh="全部">All</span> <span>' + str(len(cards)) + '</span></button>']
    for category in categories:
        count = sum(1 for page in page_list if page.category == category)
        filters.append(f'<button class="filter-button" type="button" data-wiki-filter="{html.escape(category)}"><span>{html.escape(category)}</span> <span>{count}</span></button>')
    return f'''{shell_head("Player Wiki", depth=0)}
<body class="wiki-library" data-title-en="Player Wiki | Chronoromancer" data-title-zh="玩家 Wiki | Chronoromancer">
  {site_header(depth=0)}
  <main id="content">
    <section class="wiki-library-hero"><div class="container wiki-library-hero-inner"><div>
      <p class="eyebrow" data-copy-en="Official mirror of community knowledge" data-copy-zh="社区知识的官方镜像">Official mirror of community knowledge</p>
      <h1 data-copy-en="Every timeline, one searchable library." data-copy-zh="每一条时间线，尽在一个可搜索的资料库。">Every timeline, one searchable library.</h1>
      <p data-copy-en="Character routes, systems, items, locations, and player discoveries from the living Chronoromancer wiki—presented in a fast, mobile-friendly format." data-copy-zh="汇集持续更新的 Chronoromancer Wiki 中的角色路线、系统、道具、地点与玩家发现，并以快速、适合手机阅读的方式呈现。">Character routes, systems, items, locations, and player discoveries from the living Chronoromancer wiki—presented in a fast, mobile-friendly format.</p>
      <div class="guide-library-stats"><span><strong>{len(cards)}</strong><span data-copy-en="live articles" data-copy-zh="篇实时文章">live articles</span></span><span><strong>{sum(p.image_count for p in page_list)}</strong><span data-copy-en="referenced images" data-copy-zh="张引用图片">referenced images</span></span><span><strong>{len(categories)}</strong><span data-copy-en="organized collections" data-copy-zh="个资料分类">organized collections</span></span></div>
    </div><aside class="wiki-feature-art"><img src="assets/images/v2/hero-splash.png" alt="Chronoromancer characters"><div><span data-copy-en="Community + game verification" data-copy-zh="社区资料 + 游戏内容核对">Community + game verification</span><strong data-copy-en="Readable knowledge without losing player discoveries." data-copy-zh="保留玩家发现，整理成清晰易读的资料。">Readable knowledge without losing player discoveries.</strong></div></aside></div></section>
    <section class="section wiki-browser"><div class="container">
      <div class="wiki-tools"><div class="wiki-filter-row">{''.join(filters)}</div><label class="guide-search"><span class="sr-only" data-copy-en="Search wiki" data-copy-zh="搜索 Wiki">Search wiki</span><input type="search" data-wiki-search data-placeholder-en="Search characters, systems, items, or locations" data-placeholder-zh="搜索角色、系统、道具或地点" placeholder="Search characters, systems, items, or locations"><kbd>/</kbd></label></div>
      <p class="guide-results" aria-live="polite"><span data-wiki-result-count>{len(cards)}</span> <span data-copy-en="articles shown" data-copy-zh="篇文章">articles shown</span></p>
      <div class="wiki-card-grid">{''.join(cards)}</div>
      <div class="empty-state" data-wiki-empty hidden><h2 data-copy-en="No wiki article matched that search." data-copy-zh="没有找到符合条件的 Wiki 文章。">No wiki article matched that search.</h2><p data-copy-en="Try a character name, system, item, or broader category." data-copy-zh="请尝试角色名称、系统、道具或更宽泛的分类。">Try a character name, system, item, or broader category.</p></div>
    </div></section>
  </main>
  {site_footer(depth=0)}{scripts(depth=0)}
</body></html>'''


def build(output: Path, titles: Iterable[str]) -> None:
    title_list = list(titles)
    revisions = fetch_revisions(title_list)
    def load(title: str) -> PageInfo:
        return fetch_page(title, revisions.get(title.casefold(), (0, "")))

    # A small pool keeps a full private preview practical without hammering the
    # community wiki. Output order still follows the alphabetized title list.
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        pages = list(executor.map(load, title_list))
    known_slugs = {page.title.casefold(): page.slug for page in pages}
    for source, target in fetch_redirect_map().items():
        target_slug = known_slugs.get(target.casefold())
        if target_slug:
            known_slugs[source] = target_slug
    wiki_dir = output / "wiki"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    for page in pages:
        article_html, headings = clean_article(page, known_slugs)
        (wiki_dir / f"{page.slug}.html").write_text(
            article_page(page, article_html, headings), encoding="utf-8", newline="\n"
        )
        print(f"built {page.title} -> wiki/{page.slug}.html")
    (output / "wiki.html").write_text(index_page(pages), encoding="utf-8", newline="\n")
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": API,
        "pages": [
            {
                "title": page.title,
                "slug": page.slug,
                "revision_id": page.revision_id,
                "revision_timestamp": page.revision_timestamp,
                "category": page.category,
                "image_count": page.image_count,
            }
            for page in pages
        ],
    }
    (output / "wiki-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True, help="Preview output directory")
    parser.add_argument("--title", action="append", dest="titles", help="Live wiki title; repeatable")
    parser.add_argument("--all-pages", action="store_true", help="Build every non-redirect article in the main namespace")
    args = parser.parse_args()
    if args.all_pages and args.titles:
        parser.error("--all-pages cannot be combined with --title")
    titles = fetch_all_titles() if args.all_pages else (args.titles or DEFAULT_TITLES)
    build(args.output.resolve(), titles)


if __name__ == "__main__":
    main()
