from __future__ import annotations

import html
import json
import re
from difflib import SequenceMatcher
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit

from bs4 import BeautifulSoup
from markdown_it import MarkdownIt


SITE = Path(r"D:\extended\website")
SOURCE = Path(r"D:\GAME_MAKER\Chronoromancer\game\walkthroughs")
CHINESE = SOURCE / "zh-CN"
GUIDES = SITE / "guides"

WIKI_URL = "https://chronoromancer.miraheze.org/wiki/Main_Page"
PENDING_TRANSLATIONS: set[str] = set()


CATEGORIES = [
    {
        "id": "start",
        "en": "Start Here",
        "zh": "从这里开始",
        "description_en": "New-player routes, frequently asked questions, and the main story sequence.",
        "description_zh": "新手路线、常见问题与主线剧情顺序。",
        "files": {"quickstart_guide", "early_game_walkthrough", "faq", "story_beats"},
    },
    {
        "id": "systems",
        "en": "Core Systems",
        "zh": "核心系统",
        "description_en": "Rules, progression, relationships, resources, items, and world references.",
        "description_zh": "规则、成长、关系、资源、道具与世界资料。",
        "files": {
            "alignment_system", "combat_system", "investment_system", "items", "locations",
            "relationship_dating_and_intimacy", "stats_skills_and_proficiencies", "wealth_guide",
        },
    },
    {
        "id": "activities",
        "en": "Activities & Businesses",
        "zh": "活动与经营",
        "description_en": "Businesses, crafting, seasonal areas, minigames, and repeatable activities.",
        "description_zh": "经营、制作、季节区域、小游戏与重复活动。",
        "files": {
            "bar_games", "blacksmith_and_forge", "brothel", "brothel_stats_and_calculations",
            "caterpillar_rearing", "christmas_village", "fishing_guide", "haunted_mansion",
            "maid_system", "mining_system", "sirena_isle_resort",
        },
    },
    {
        "id": "factions",
        "en": "Factions & Exploration",
        "zh": "阵营与探索",
        "description_en": "Guild progression, dungeon preparation, and faction-specific systems.",
        "description_zh": "公会成长、地下城准备与阵营专属系统。",
        "files": {"bards_guild", "chaos_syndicate", "dungeon_guide", "fighters_guild", "thieves_guild", "wizard_faction"},
    },
    {
        "id": "characters",
        "en": "Character Routes",
        "zh": "角色路线",
        "description_en": "Complete relationship routes, unlock conditions, schedules, and progression advice.",
        "description_zh": "完整关系路线、解锁条件、日程与推进建议。",
        "files": set(),
    },
]

CATEGORY_BY_ID = {category["id"]: category for category in CATEGORIES}
EXPLICIT_FILES = {slug for category in CATEGORIES for slug in category["files"]}


@dataclass
class Guide:
    slug: str
    filename: str
    category: str
    title_en: str
    title_zh: str
    summary_en: str
    summary_zh: str
    translated: bool
    pending: bool
    source_en: Path
    source_zh: Path | None


def first_heading(text: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+?)\s*$", text, re.MULTILINE)
    return match.group(1).strip() if match else fallback.replace("_", " ").title()


def first_paragraph(text: str) -> str:
    blocks = re.split(r"\n\s*\n", text)
    for block in blocks[1:]:
        cleaned = block.strip()
        if not cleaned or cleaned.startswith(("#", "|", "```", "---", ">")):
            continue
        if re.match(r"^(?:[-*+] |\d+\. )", cleaned):
            continue
        cleaned = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", cleaned)
        cleaned = re.sub(r"[`*_~]", "", cleaned)
        cleaned = re.sub(r"<[^>]+>", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if cleaned:
            return cleaned[:237].rstrip() + ("…" if len(cleaned) > 237 else "")
    return ""


def category_for(slug: str) -> str:
    for category in CATEGORIES:
        if slug in category["files"]:
            return category["id"]
    return "characters"


def load_guides() -> list[Guide]:
    guides: list[Guide] = []
    for source in sorted(SOURCE.glob("*.md"), key=lambda path: path.name.casefold()):
        slug = source.stem.casefold()
        en_text = source.read_text(encoding="utf-8-sig")
        zh_source = CHINESE / source.name
        chinese_exists = zh_source.exists() and zh_source.stat().st_size > 0
        pending = slug in PENDING_TRANSLATIONS
        translated = chinese_exists and not pending
        zh_text = zh_source.read_text(encoding="utf-8-sig") if translated else ""
        guides.append(
            Guide(
                slug=slug,
                filename=source.name,
                category=category_for(slug),
                title_en=first_heading(en_text, slug),
                title_zh=first_heading(zh_text, slug) if translated else first_heading(en_text, slug),
                summary_en=first_paragraph(en_text),
                summary_zh=first_paragraph(zh_text) if translated else ("简体中文译文正在审核中。" if pending else "简体中文译文正在制作中。"),
                translated=translated,
                pending=pending,
                source_en=source,
                source_zh=zh_source if translated else None,
            )
        )
    order = {category["id"]: index for index, category in enumerate(CATEGORIES)}
    return sorted(guides, key=lambda guide: (order[guide.category], guide.title_en.casefold()))


def heading_slug(text: str, used: set[str]) -> str:
    value = re.sub(r"<[^>]+>", "", text).strip().lower()
    value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE)
    value = re.sub(r"\s", "-", value).strip("-") or "section"
    candidate = value
    counter = 1
    while candidate in used:
        candidate = f"{value}-{counter}"
        counter += 1
    used.add(candidate)
    return candidate


def rewrite_markdown_link(href: str, anchor_prefix: str = "") -> str:
    parts = urlsplit(href)
    if parts.scheme or parts.netloc:
        return href
    path = parts.path
    if path.lower().endswith(".md"):
        stem = Path(path).stem.casefold()
        path = f"{stem}.html"
    fragment = f"{anchor_prefix}{parts.fragment}" if anchor_prefix and parts.fragment and not path else parts.fragment
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, fragment))


def render_markdown(text: str, shared_ids: list[str] | None = None, anchor_prefix: str = "") -> tuple[str, list[dict], list[str]]:
    parser = MarkdownIt("commonmark", {"html": True}).enable("table").enable("strikethrough")
    soup = BeautifulSoup(parser.render(text), "html.parser")
    first_h1 = soup.find("h1")
    if first_h1:
        first_h1.decompose()

    # Translations may contain invisible English-ID anchors to preserve links.
    # Move each one onto the following heading, then prefix it in the Chinese panel
    # so both language panels can coexist without duplicate document IDs.
    stable_anchor_count = 0
    for stable_anchor in list(soup.select("a[id]")):
        if stable_anchor.get_text(strip=True):
            continue
        next_heading = stable_anchor.find_next(["h2", "h3"])
        if next_heading and not next_heading.has_attr("data-stable-id"):
            next_heading["data-stable-id"] = str(stable_anchor["id"])
            stable_anchor_count += 1
        stable_anchor.decompose()

    used: set[str] = set()
    generated_used: set[str] = set()
    toc: list[dict] = []
    ids: list[str] = []
    for index, heading in enumerate(soup.find_all(["h2", "h3"])):
        if heading.has_attr("data-stable-id"):
            anchor = f"{anchor_prefix}{heading['data-stable-id']}"
            del heading["data-stable-id"]
        elif shared_ids is not None and index < len(shared_ids) and stable_anchor_count == 0:
            anchor = f"{anchor_prefix}{shared_ids[index]}"
        else:
            anchor = f"{anchor_prefix}{heading_slug(heading.get_text(' ', strip=True), generated_used)}"
        if anchor in used:
            base = anchor
            suffix = 1
            while anchor in used:
                anchor = f"{base}-{suffix}"
                suffix += 1
        used.add(anchor)
        heading["id"] = anchor
        ids.append(anchor)
        toc.append({"id": anchor, "level": int(heading.name[1]), "text": heading.get_text(" ", strip=True)})

    for anchor in soup.find_all("a", href=True):
        href = str(anchor["href"])
        anchor["href"] = rewrite_markdown_link(href, anchor_prefix)
        if href.startswith(("http://", "https://")):
            anchor["target"] = "_blank"
            anchor["rel"] = "noopener noreferrer"

    # Preserve explicit in-document links when a heading was renamed. The alias
    # is placed before the most similar heading, so old source anchors still land
    # near the intended section.
    existing_ids = {str(tag["id"]) for tag in soup.find_all(id=True)}
    local_fragments = {
        unquote(urlsplit(str(anchor["href"])).fragment)
        for anchor in soup.find_all("a", href=True)
        if not urlsplit(str(anchor["href"])).path and urlsplit(str(anchor["href"])).fragment
    }
    headings = list(soup.find_all(["h2", "h3"]))
    for fragment in sorted(local_fragments - existing_ids):
        if not headings:
            continue
        normalized = fragment.removeprefix(anchor_prefix)
        target = max(
            headings,
            key=lambda heading: SequenceMatcher(
                None,
                normalized,
                str(heading.get("id", "")).removeprefix(anchor_prefix),
            ).ratio(),
        )
        alias = soup.new_tag("span", attrs={"id": fragment, "class": "anchor-alias", "aria-hidden": "true"})
        target.insert_before(alias)
        existing_ids.add(fragment)

    for table in list(soup.find_all("table")):
        wrapper = soup.new_tag("div", attrs={"class": "guide-table-wrap", "tabindex": "0"})
        table.wrap(wrapper)

    return str(soup), toc, ids


def esc(value: str) -> str:
    return html.escape(value, quote=True)


def header(prefix: str, active: str) -> str:
    def nav(link: str, key: str, label: str, page: str) -> str:
        active_class = ' class="is-active"' if active == page else ""
        return f'<a{active_class} href="{prefix}{link}" data-i18n="{key}">{label}</a>'

    return f'''<a class="skip-link" href="#content" data-copy-en="Skip to content" data-copy-zh="跳至正文">Skip to content</a>
  <div class="maturity-bar" data-copy-en="18+ adults-only game · Guides may describe mature game systems" data-copy-zh="18+ 仅限成人游戏 · 攻略可能涉及成人游戏系统">18+ adults-only game · Guides may describe mature game systems</div>
  <header class="site-header"><div class="container header-inner">
    <a class="brand" href="{prefix}main.html" aria-label="Chronoromancer home"><img src="{prefix}assets/images/v2/logo.png" alt="Chronoromancer"></a>
    <button class="nav-toggle" type="button" data-nav-toggle aria-expanded="false" aria-label="Open navigation"><span></span><span></span><span></span></button>
    <nav class="site-nav" data-nav-menu aria-label="Primary navigation">
      {nav('main.html', 'navHome', 'Home', 'home')}
      {nav('story.html', 'navStory', 'Story', 'story')}
      {nav('characters.html', 'navCharacters', 'Characters', 'characters')}
      {nav('walkthroughs.html', 'navGuides', 'Guides', 'guides')}
      {nav('screenshots.html', 'navGallery', 'Gallery', 'gallery')}
      <a data-config-link="community.wiki" target="_blank" rel="noopener noreferrer" data-i18n="navWiki">Player Wiki</a>
      <a href="{prefix}main.html#download" data-i18n="navDownload">Download</a>
      <div class="language-switch" role="group" aria-label="Language"><button type="button" data-language="en" aria-pressed="true">EN</button><button type="button" data-language="zh" aria-pressed="false">简体中文</button></div>
    </nav>
  </div></header>'''


def footer(prefix: str) -> str:
    return f'''<footer class="site-footer"><div class="container"><div class="footer-grid">
    <div class="footer-brand"><img src="{prefix}assets/images/v2/logo.png" alt="Chronoromancer"><p data-i18n="footerDescription">An adults-only time-travel sandbox RPG. Public website artwork is SFW.</p></div>
    <div class="footer-column"><h2 data-i18n="footerExplore">Explore</h2><a href="{prefix}story.html" data-i18n="navStory">Story</a><a href="{prefix}characters.html" data-i18n="navCharacters">Characters</a><a href="{prefix}walkthroughs.html" data-i18n="navGuides">Guides</a><a href="{prefix}screenshots.html" data-i18n="navGallery">Gallery</a><a href="{prefix}main.html#download" data-i18n="navDownload">Download</a></div>
    <div class="footer-column"><h2 data-i18n="footerCommunity">Community</h2><a data-config-link="community.discord" target="_blank" rel="noopener noreferrer">Discord</a><a data-config-link="community.telegram" target="_blank" rel="noopener noreferrer">Telegram</a><a data-config-link="community.patreon" target="_blank" rel="noopener noreferrer">Patreon</a><a data-config-link="community.wiki" target="_blank" rel="noopener noreferrer" data-i18n="navWiki">Player Wiki</a></div>
    <div class="footer-column"><h2 data-i18n="footerLegal">Legal</h2><a href="{prefix}privacy.html" data-i18n="footerPrivacy">Privacy</a><a href="{prefix}terms.html" data-i18n="footerTerms">Terms</a></div>
  </div><div class="footer-bottom"><span>© <span data-current-year></span> <span data-i18n="copyright">Chronoromancer Studio. All rights reserved.</span></span><span data-copy-en="Official guides · English / Simplified Chinese" data-copy-zh="官方攻略 · English / 简体中文">Official guides · English / Simplified Chinese</span></div></div></footer>'''


def toc_html(toc: list[dict]) -> str:
    return "".join(
        f'<a class="toc-level-{item["level"]}" href="#{esc(item["id"])}">{esc(item["text"])}</a>'
        for item in toc
    )


def build_guide_page(guide: Guide, previous: Guide | None, following: Guide | None) -> None:
    en_text = guide.source_en.read_text(encoding="utf-8-sig")
    en_html, en_toc, en_ids = render_markdown(en_text)
    if guide.translated and guide.source_zh:
        zh_text = guide.source_zh.read_text(encoding="utf-8-sig")
        zh_html, zh_toc, _ = render_markdown(zh_text, en_ids, "zh-")
    else:
        if guide.pending:
            zh_html = '''<div class="translation-pending"><strong>简体中文译文正在审核中</strong><p>本指南的中文译文已经完成初稿，正在进行最终内容审核。审核通过后会在这里正式开放。</p></div>'''
        else:
            zh_html = '''<div class="translation-pending"><strong>简体中文翻译正在制作中</strong><p>本指南的英文版本已经可以阅读。完成并通过检查后，简体中文译文会自动出现在这里。</p></div>'''
        zh_toc = []

    category = CATEGORY_BY_ID[guide.category]
    translation_label_en = "Simplified Chinese available" if guide.translated else ("Chinese translation under review" if guide.pending else "Chinese translation in progress")
    translation_label_zh = "简体中文译文已上线" if guide.translated else ("简体中文译文审核中" if guide.pending else "简体中文翻译进行中")

    def pager(item: Guide | None, direction_en: str, direction_zh: str) -> str:
        if not item:
            return "<span></span>"
        return f'''<a href="{item.slug}.html"><span data-copy-en="{direction_en}" data-copy-zh="{direction_zh}">{direction_en}</span><strong data-copy-en="{esc(item.title_en)}" data-copy-zh="{esc(item.title_zh)}">{esc(item.title_en)}</strong></a>'''

    page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{esc(guide.summary_en)}"><link rel="icon" type="image/png" href="../assets/images/v2/favicon.png">
  <link rel="stylesheet" href="../assets/css/style.css"><link rel="stylesheet" href="../assets/css/walkthroughs.css">
  <title>{esc(guide.title_en)} | Chronoromancer Guides</title></head>
<body class="guide-page" data-title-en="{esc(guide.title_en)} | Chronoromancer Guides" data-title-zh="{esc(guide.title_zh)} | Chronoromancer 官方攻略">
  <div class="reading-progress" data-reading-progress></div>
  {header('../', 'guides')}
  <main id="content">
    <section class="guide-masthead"><div class="container">
      <nav class="breadcrumb" aria-label="Breadcrumb"><a href="../walkthroughs.html" data-copy-en="Official Guides" data-copy-zh="官方攻略">Official Guides</a><span>/</span><span data-copy-en="{esc(category['en'])}" data-copy-zh="{esc(category['zh'])}">{esc(category['en'])}</span></nav>
      <p class="eyebrow" data-copy-en="Version-matched official guide" data-copy-zh="与当前版本匹配的官方攻略">Version-matched official guide</p>
      <h1 data-copy-en="{esc(guide.title_en)}" data-copy-zh="{esc(guide.title_zh)}">{esc(guide.title_en)}</h1>
      <div class="guide-meta"><span data-copy-en="{esc(category['en'])}" data-copy-zh="{esc(category['zh'])}">{esc(category['en'])}</span><span data-copy-en="{translation_label_en}" data-copy-zh="{translation_label_zh}">{translation_label_en}</span><span data-site-version>V0.9.7.7c</span></div>
    </div></section>
    <div class="container guide-layout">
      <aside class="guide-sidebar">
        <a class="back-to-library" href="../walkthroughs.html" data-copy-en="← All guides" data-copy-zh="← 全部攻略">← All guides</a>
        <div data-lang-panel="en"><h2>On this page</h2><nav class="guide-toc">{toc_html(en_toc)}</nav></div>
        <div data-lang-panel="zh" hidden><h2>本页目录</h2><nav class="guide-toc">{toc_html(zh_toc) if zh_toc else '<span class="toc-empty">翻译完成后将显示目录。</span>'}</nav></div>
      </aside>
      <article class="guide-content">
        <div class="spoiler-notice"><strong data-copy-en="Guide notice" data-copy-zh="攻略提示">Guide notice</strong><span data-copy-en="This page contains gameplay and story spoilers and may describe mature systems." data-copy-zh="本页包含玩法与剧情剧透，并可能涉及成人游戏系统。">This page contains gameplay and story spoilers and may describe mature systems.</span></div>
        <div class="markdown-body" data-lang-panel="en">{en_html}</div>
        <div class="markdown-body" data-lang-panel="zh" hidden>{zh_html}</div>
        <div class="guide-community-note"><div><strong data-copy-en="Community discoveries" data-copy-zh="社区发现">Community discoveries</strong><p data-copy-en="These official guides track the current game. The player-maintained wiki may contain additional strategies and discoveries." data-copy-zh="这些官方攻略与当前游戏版本保持一致；玩家维护的 Wiki 可能还收录其他策略与社区发现。">These official guides track the current game. The player-maintained wiki may contain additional strategies and discoveries.</p></div><a href="{WIKI_URL}" target="_blank" rel="noopener noreferrer" data-copy-en="Visit Player Wiki →" data-copy-zh="访问玩家 Wiki →">Visit Player Wiki →</a></div>
        <nav class="guide-pager" aria-label="Adjacent guides">{pager(previous, 'Previous guide', '上一篇攻略')}{pager(following, 'Next guide', '下一篇攻略')}</nav>
      </article>
    </div>
  </main>
  {footer('../')}
  <script src="../assets/js/site-config.js"></script><script src="../assets/js/site.js"></script><script src="../assets/js/walkthroughs.js"></script>
</body></html>'''
    (GUIDES / f"{guide.slug}.html").write_text(page, encoding="utf-8")


def build_index(guides: list[Guide]) -> None:
    translated_count = sum(guide.translated for guide in guides)
    category_sections: list[str] = []
    for category in CATEGORIES:
        category_guides = [guide for guide in guides if guide.category == category["id"]]
        cards = []
        for guide in category_guides:
            status_en = "Chinese available" if guide.translated else ("Chinese under review" if guide.pending else "Chinese in progress")
            status_zh = "简中已完成" if guide.translated else ("简中审核中" if guide.pending else "简中翻译中")
            search = " ".join((guide.slug, guide.title_en, guide.title_zh, guide.summary_en, guide.summary_zh))
            cards.append(f'''<article class="guide-card" data-guide-card data-category="{guide.category}" data-translated="{str(guide.translated).lower()}" data-search="{esc(search.casefold())}">
              <div class="guide-card-top"><span class="guide-category" data-copy-en="{esc(category['en'])}" data-copy-zh="{esc(category['zh'])}">{esc(category['en'])}</span><span class="translation-status {'is-ready' if guide.translated else ''}" data-copy-en="{status_en}" data-copy-zh="{status_zh}">{status_en}</span></div>
              <h3 data-copy-en="{esc(guide.title_en)}" data-copy-zh="{esc(guide.title_zh)}">{esc(guide.title_en)}</h3>
              <p data-copy-en="{esc(guide.summary_en)}" data-copy-zh="{esc(guide.summary_zh)}">{esc(guide.summary_en)}</p>
              <a href="guides/{guide.slug}.html" data-copy-en="Read guide →" data-copy-zh="阅读攻略 →">Read guide →</a>
            </article>''')
        category_sections.append(f'''<section class="guide-category-section" data-guide-section="{category['id']}">
          <div class="category-heading"><div><p class="eyebrow" data-copy-en="Guide collection" data-copy-zh="攻略分类">Guide collection</p><h2 data-copy-en="{esc(category['en'])}" data-copy-zh="{esc(category['zh'])}">{esc(category['en'])}</h2></div><p data-copy-en="{esc(category['description_en'])}" data-copy-zh="{esc(category['description_zh'])}">{esc(category['description_en'])}</p></div>
          <div class="guide-card-grid">{''.join(cards)}</div>
        </section>''')

    buttons = [f'<button class="filter-button is-active" type="button" data-guide-filter="all"><span data-copy-en="All guides" data-copy-zh="全部攻略">All guides</span><span class="filter-count">{len(guides)}</span></button>']
    for category in CATEGORIES:
        count = sum(guide.category == category["id"] for guide in guides)
        buttons.append(f'''<button class="filter-button" type="button" data-guide-filter="{category['id']}"><span data-copy-en="{esc(category['en'])}" data-copy-zh="{esc(category['zh'])}">{esc(category['en'])}</span><span class="filter-count">{count}</span></button>''')

    page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Official Chronoromancer walkthroughs in English and Simplified Chinese."><meta property="og:title" content="Chronoromancer Official Guides"><meta property="og:description" content="Version-matched walkthroughs, systems references, and character routes in English and Simplified Chinese.">
  <link rel="icon" type="image/png" href="assets/images/v2/favicon.png"><link rel="stylesheet" href="assets/css/style.css"><link rel="stylesheet" href="assets/css/walkthroughs.css"><title>Official Guides | Chronoromancer</title></head>
<body class="walkthrough-library" data-title-en="Official Guides | Chronoromancer" data-title-zh="官方攻略 | Chronoromancer">
  {header('', 'guides')}
  <main id="content">
    <section class="walkthrough-hero"><div class="container walkthrough-hero-inner"><div>
      <p class="eyebrow" data-copy-en="Official, version-matched knowledge" data-copy-zh="与当前版本匹配的官方资料">Official, version-matched knowledge</p>
      <h1 data-copy-en="Master every timeline." data-copy-zh="掌握每一条时间线。">Master every timeline.</h1>
      <p data-copy-en="Browse complete walkthroughs, character routes, system references, and progression advice drawn from the current game files." data-copy-zh="浏览依据当前游戏文件编写的完整攻略、角色路线、系统资料与推进建议。">Browse complete walkthroughs, character routes, system references, and progression advice drawn from the current game files.</p>
      <div class="guide-library-stats"><span><strong>{len(guides)}</strong><span data-copy-en="English guides" data-copy-zh="篇英文攻略">English guides</span></span><span><strong>{translated_count}</strong><span data-copy-en="Chinese translations available now" data-copy-zh="篇简中译文目前可用">Chinese translations available now</span></span><span><strong>5</strong><span data-copy-en="organized collections" data-copy-zh="个攻略分类">organized collections</span></span></div>
    </div><aside class="official-guide-callout"><span class="card-tag" data-copy-en="Official library" data-copy-zh="官方资料库">Official library</span><h2 data-copy-en="Built from the working game documentation." data-copy-zh="直接来源于游戏的工作文档。">Built from the working game documentation.</h2><p data-copy-en="English is the source of truth. Each completed Simplified Chinese translation appears under the same guide and can be switched instantly." data-copy-zh="英文文档是内容源。每篇完成的简体中文译文都会显示在同一攻略页面中，并可即时切换。">English is the source of truth. Each completed Simplified Chinese translation appears under the same guide and can be switched instantly.</p></aside></div></section>
    <section class="section guide-browser"><div class="container">
      <div class="guide-tools"><div class="guide-filter-row">{''.join(buttons)}</div><label class="guide-search"><span class="sr-only" data-copy-en="Search guides" data-copy-zh="搜索攻略">Search guides</span><input type="search" data-guide-search data-placeholder-en="Search titles, topics, or characters" data-placeholder-zh="搜索标题、主题或角色" placeholder="Search titles, topics, or characters"><kbd>/</kbd></label></div>
      <p class="guide-results" aria-live="polite"><span data-guide-result-count>{len(guides)}</span> <span data-copy-en="guides shown" data-copy-zh="篇攻略">guides shown</span></p>
      {''.join(category_sections)}
      <div class="empty-state" data-guide-empty hidden><h2 data-copy-en="No guide matched that search." data-copy-zh="没有找到符合条件的攻略。">No guide matched that search.</h2><p data-copy-en="Try a character name, system, location, or a broader category." data-copy-zh="请尝试角色名称、系统、地点或更宽泛的分类。">Try a character name, system, location, or a broader category.</p></div>
    </div></section>
    <section class="section section--tinted"><div class="container wiki-bridge"><div><p class="eyebrow" data-copy-en="Official knowledge + player discoveries" data-copy-zh="官方资料 + 玩家发现">Official knowledge + player discoveries</p><h2 data-copy-en="Keep the community wiki close." data-copy-zh="玩家 Wiki 依然值得收藏。">Keep the community wiki close.</h2><p data-copy-en="This library provides controlled, version-matched English and Chinese guides. Miraheze remains the community space for player tips, discoveries, and contributions." data-copy-zh="本资料库提供受控且与版本匹配的中英文攻略；Miraheze 仍是玩家分享技巧、发现与贡献内容的社区空间。">This library provides controlled, version-matched English and Chinese guides. Miraheze remains the community space for player tips, discoveries, and contributions.</p></div><a class="button button--secondary" href="{WIKI_URL}" target="_blank" rel="noopener noreferrer" data-copy-en="Visit the Player Wiki" data-copy-zh="访问玩家 Wiki">Visit the Player Wiki</a></div></section>
  </main>
  {footer('')}
  <script src="assets/js/site-config.js"></script><script src="assets/js/site.js"></script><script src="assets/js/walkthroughs.js"></script>
</body></html>'''
    (SITE / "walkthroughs.html").write_text(page, encoding="utf-8")


def write_manifest(guides: list[Guide]) -> None:
    payload = {
        "total": len(guides),
        "translated": sum(guide.translated for guide in guides),
        "guides": [
            {
                "slug": guide.slug,
                "filename": guide.filename,
                "category": guide.category,
                "titleEn": guide.title_en,
                "titleZh": guide.title_zh,
                "translated": guide.translated,
                "translationState": "ready" if guide.translated else ("review" if guide.pending else "missing"),
                "url": f"guides/{guide.slug}.html",
            }
            for guide in guides
        ],
    }
    data_dir = SITE / "assets" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "walkthroughs.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_sitemap(guides: list[Guide]) -> None:
    urls = ["main.html", "story.html", "characters.html", "walkthroughs.html", "screenshots.html", "privacy.html", "terms.html"]
    urls.extend(f"guides/{guide.slug}.html" for guide in guides)
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    lines.extend(f"  <url><loc>https://chronoromancergame.com/{url}</loc></url>" for url in urls)
    lines.append("</urlset>")
    (SITE / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    GUIDES.mkdir(parents=True, exist_ok=True)
    guides = load_guides()
    build_index(guides)
    for index, guide in enumerate(guides):
        previous = guides[index - 1] if index else None
        following = guides[index + 1] if index + 1 < len(guides) else None
        build_guide_page(guide, previous, following)
    write_manifest(guides)
    write_sitemap(guides)
    print(f"Generated {len(guides)} guide pages; {sum(guide.translated for guide in guides)} include Simplified Chinese.")


if __name__ == "__main__":
    main()
