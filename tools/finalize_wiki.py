#!/usr/bin/env python3
"""Finalize a fetched Chronoromancer wiki build for the public website.

The fetch/build stage deliberately remains separate so that a failed network
request can never replace the published wiki.  This stage translates the live
English revision to Simplified Chinese with the locally installed Argos model,
keeps game names intact, downloads referenced images into the website, and
writes the finished bilingual pages to a chosen output directory.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import mimetypes
import re
import shutil
import urllib.parse
import urllib.request
from pathlib import Path

import ctranslate2
import sentencepiece as spm
from bs4 import BeautifulSoup, Comment, NavigableString, Tag


ARGOS_PACKAGE = Path.home() / ".local/share/argos-translate/packages/translate-en_zh-1_9"
USER_AGENT = "ChronoromancerWebsiteWikiBuild/1.0 (official website build tool)"
SKIP_TRANSLATION_PARENTS = {"code", "pre", "script", "style"}
ZH_CATEGORIES = {
    "Overview": "概览",
    "Characters": "角色",
    "Game Systems": "游戏系统",
    "Reference": "参考资料",
    "Walkthroughs": "流程攻略",
    "World & Reference": "世界与参考资料",
}
ZH_FIXED = {
    "All": "全部",
    "image": "张图片",
    "images": "张图片",
    "Live revision": "实时修订版",
    "Read article →": "阅读文章 →",
    "Single-section article": "单节文章",
}

# The compact translation model can loop on a small number of symbolic labels,
# arrow-separated score formulas, and sentence fragments split by inline HTML.
# Keep these reviewed translations explicit so rebuilds remain deterministic.
DEGENERATE_TRANSLATIONS = {
    "Funny +3 → Funny +3": "幽默 +3 → 幽默 +3",
    "Caring +5 → Funny +5 → Flirty +5 → Caring +6 → Caring +6 → Funny +6 → Flirty +7": "关怀 +5 → 幽默 +5 → 调情 +5 → 关怀 +6 → 关怀 +6 → 幽默 +6 → 调情 +7",
    ", Funny": "，幽默",
    "There is no money, Energy, Calm, gift or extra quest requirement configured. The direct affection is not multiplied. This is a Charm-stat lesson and does": "未设置金钱、能量、冷静、礼物或额外任务要求。直接好感不会获得倍率加成。这是一堂魅力属性课程，并且",
    "Funny +4 → Funny +4 → Funny +4": "幽默 +4 → 幽默 +4 → 幽默 +4",
    ". These use the main-story sequence rather than the personal scene chain. Each triggers once, all hours, at the registered location after its predecessor.": "。这些内容采用主线剧情顺序，而非个人场景链。每项内容只会触发一次，可在任意时间于前一项完成后前往已登记地点触发。",
    "one session Talk, one praise, one ordinary gift and one training": "每次训练中可进行一次交谈、一次称赞、一次普通送礼和一次训练",
    "Maids Quarters room level to the recruited-maid count, capped at six": "女仆宿舍的房间等级等于已招募女仆人数，上限为六级",
    "Funny +4 → Flirty +5 → Flirty +4": "幽默 +4 → 调情 +5 → 调情 +4",
    ", initially 1, advances after lessons up to 8. Categories do not maintain separate unlock levels.": "，初始为 1，完成课程后逐步提升至 8。各类别不分别保留独立的解锁等级。",
    "❓ Stats & Skills": "❓ 属性与技能",
    "to jump around — more warp destinations unlock as you progress through the story.": "在各地点间快速移动——随着剧情推进，会解锁更多传送目的地。",
    "Five of a Kind → Royal Flush → Straight Flush → Four of a Kind → Full House → Flush → Straight → Three of a Kind → Two Pair → Pair → High Card.": "五条 → 皇家同花顺 → 同花顺 → 四条 → 葫芦 → 同花 → 顺子 → 三条 → 两对 → 一对 → 高牌。",
    "— A magical-warded enclosure for housing exotic creatures. Built jointly with Aziza — she handles the enchantments while Gastoff handles the construction. (Gives both Gastoff and Aziza +15 relationship.)": "——用于饲养珍奇生物的魔法防护围栏。由 Aziza 与 Gastoff 合作建造——她负责附魔，他负责施工。（Gastoff 与 Aziza 的关系值各 +15。）",
    "Hardy": "坚韧",
    "Emperor Moth 30%; Puss Moth 20%; Luna Moth 15%; Polyphemus Moth 15%; Death's-head Hawkmoth 15%; Atlas Moth 5%": "帝王蛾 30%；猫蛾 20%；月神蛾 15%；波吕斐摩斯蛾 15%；鬼脸天蛾 15%；阿特拉斯蛾 5%",
    "Cabbage White 45%; Large White 35%; Green-veined White 15%; Orange-tip 3%; Cinnabar Moth 2%": "菜粉蝶 45%；大菜粉蝶 35%；青脉菜粉蝶 15%；橙翅襟粉蝶 3%；朱砂蛾 2%",
    "Gates → Den → Parlor → Lair → Parlor → Big Top → Booth → Gates → Funhouse → Gates → Garden → Gates": "大门 → 巢穴 → 会客厅 → 兽穴 → 会客厅 → 马戏大帐篷 → 摊位 → 大门 → 趣味屋 → 大门 → 花园 → 大门",
    "modified Ability ÷ 2 × physical factor": "修正后能力值 ÷ 2 × 物理系数",
    ", plus 7 with Hypnotic Gaze and plus 7 with Sleep Spores, then the same repeated-Sleep penalty. Some encounters are explicitly immune; a cap is not a promise that every enemy can be put to sleep.": "，Hypnotic Gaze 提供 +7，Sleep Spores 再提供 +7，之后采用相同的重复睡眠惩罚。部分遭遇明确免疫；存在上限并不代表每个敌人都能被催眠。",
    "raw stat ÷ 100 × F": "原始属性值 ÷ 100 × F",
    "Focus buff, Cologne buff, Luck buff, Magic Spectacles, Awesome Crown, Ornate Locket": "专注增益、古龙水增益、幸运增益、魔法眼镜、炫酷王冠、华丽坠饰",
    "— Every NPC has one signature skill that": "——每个 NPC 都拥有一种标志性技能，",
    "to the right of your stats panel. The panel lists all 15 quests with progress bars, rewards, and claim buttons. Rewards must be claimed manually once a quest is done — they aren't auto-granted.": "位于属性面板右侧。该面板列出全部 15 项任务，包含进度条、奖励和领取按钮。任务完成后必须手动领取奖励——不会自动发放。",
    "Sonia already gains +15 total from Story Beats 1 and 4, plus +10 from Beat 11 (gated).": "Sonia 已从剧情节点 1 和 4 共获得 +15，并从节点 11（有条件限制）再获得 +10。",
    "Flowers are worth +20 relationship points with most romance NPCs at Close Friend+. Buying them from shops costs money. Finding them for free is pure value. And the early-game gold stashes alone can fund your first few Gastoff upgrades and investment purchases.": "大多数可恋爱 NPC 在达到亲密好友以上时，送花可增加 +20 关系点。从商店购买需要花钱，免费找到的花则完全是额外收益。仅靠游戏初期藏匿的金币，就足以支付你最初几次 Gastoff 升级和投资购买。",
    "— Planters and the window box. Perfect — you're visiting the Cafe Exterior anyway for Jessie's encounter.": "——花盆和窗箱。正好——你本来就要去咖啡馆外景触发 Jessie 的遭遇。",
}


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def translatable(value: str) -> bool:
    value = normalize_text(value)
    return bool(value and re.search(r"[A-Za-z]", value))


def protected_terms(manifest: dict) -> list[str]:
    terms = {
        "Chronoromancer",
        "AIMy",
        "VOID",
        "TIME",
        "Miraheze",
        "Wiki",
        "Ren'Py",
        "RenPy",
        "Discord",
        "Patreon",
        "Afdian",
    }
    for entry in manifest.get("pages", []):
        full_title = entry.get("title", "")
        if not full_title.startswith("Character:"):
            continue
        title = full_title.split(":", 1)[-1].strip()
        if title and len(title) > 1:
            terms.add(title)
    return sorted(terms, key=lambda item: (-len(item), item.casefold()))


def protect(value: str, terms: list[str]) -> tuple[str, dict[str, str]]:
    replacements: dict[str, str] = {}
    counter = 0

    def reserve(match: re.Match[str]) -> str:
        nonlocal counter
        token = f"[NAME{counter}]"
        counter += 1
        replacements[token] = match.group(0)
        return token

    # Preserve URLs, addresses, code-like identifiers, versions, and variables.
    patterns = (
        r"https?://[^\s]+",
        r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b",
        r"\{[^{}]+\}|\[[A-Za-z_][A-Za-z0-9_.:-]*\]",
        r"\bv?\d+(?:\.\d+){1,4}[A-Za-z0-9_-]*\b",
        r"\b[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+\b",
    )
    # One combined pass prevents generated placeholder brackets from being
    # mistaken for source brackets by the next expression.
    result = re.sub("|".join(f"(?:{pattern})" for pattern in patterns), reserve, value)
    for term in terms:
        if term not in result:
            continue
        result = re.sub(rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])", reserve, result)
    return result, replacements


def restore(value: str, replacements: dict[str, str]) -> str:
    result = value.replace("▁", "")
    for token, original in replacements.items():
        number = re.search(r"\d+", token)
        if number:
            # SentencePiece may insert whitespace inside a marker; accept the
            # harmless variants without matching unrelated source brackets.
            result = re.sub(
                rf"\[?\s*NAME\s*{number.group(0)}\s*\]?",
                lambda _match, replacement=original: replacement,
                result,
                flags=re.IGNORECASE,
            )
        result = result.replace(token, original)
    return result.strip()


class ChineseTranslator:
    def __init__(self, cache_path: Path, terms: list[str], *, reset_cache: bool = False) -> None:
        if not (ARGOS_PACKAGE / "model").is_dir():
            raise RuntimeError(f"English→Chinese Argos model not found: {ARGOS_PACKAGE}")
        self.cache_path = cache_path
        self.cache: dict[str, str] = {}
        if cache_path.is_file() and not reset_cache:
            self.cache = json.loads(cache_path.read_text(encoding="utf-8"))
        self.terms = terms
        repaired = 0
        for source, target in list(self.cache.items()):
            _protected, replacements = protect(source, self.terms)
            restored = restore(target, replacements)
            if restored != target:
                self.cache[source] = restored
                repaired += 1
        if repaired:
            print(f"repaired protected markers in {repaired} cached translations", flush=True)
        self.processor = spm.SentencePieceProcessor(model_file=str(ARGOS_PACKAGE / "sentencepiece.model"))
        self.translator = ctranslate2.Translator(
            str(ARGOS_PACKAGE / "model"),
            device="cpu",
            inter_threads=1,
            intra_threads=8,
            compute_type="int8",
        )

    def translate_many(self, values: list[str]) -> None:
        pending = [value for value in dict.fromkeys(values) if value not in self.cache]
        if not pending:
            self.cache.update(DEGENERATE_TRANSLATIONS)
            self.save()
            return
        prepared: list[str] = []
        metadata: list[dict[str, str]] = []
        for value in pending:
            protected, replacements = protect(value, self.terms)
            prepared.append(protected)
            metadata.append(replacements)
        batch_size = 512
        for start in range(0, len(prepared), batch_size):
            chunk = prepared[start : start + batch_size]
            encoded = [self.processor.encode(item, out_type=str) for item in chunk]
            results = self.translator.translate_batch(
                encoded,
                replace_unknowns=True,
                beam_size=4,
                num_hypotheses=1,
                length_penalty=0.2,
                max_batch_size=256,
                batch_type="tokens",
            )
            for offset, result in enumerate(results):
                index = start + offset
                translated = self.processor.decode(result.hypotheses[0])
                self.cache[pending[index]] = restore(translated, metadata[index])
            done = min(start + batch_size, len(prepared))
            print(f"translated {done}/{len(prepared)} new text fragments", flush=True)
            self.save()
        self.cache.update(DEGENERATE_TRANSLATIONS)
        self.save()

    def save(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(self.cache, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    def __call__(self, value: str) -> str:
        normalized = normalize_text(value)
        return self.cache.get(normalized, normalized)


def collect_texts(preview: Path) -> list[str]:
    values: list[str] = []
    for path in sorted((preview / "wiki").glob("*.html")):
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        content = soup.select_one(".wiki-source-content")
        if content is None:
            continue
        for node in content.find_all(string=True):
            if isinstance(node, Comment):
                continue
            if node.parent.name in SKIP_TRANSLATION_PARENTS:
                continue
            value = normalize_text(str(node))
            if translatable(value):
                values.append(value)
    # Shared shell/index strings that are not translated by site.js.
    values.extend(
        [
            "Overview",
            "Characters",
            "Game Systems",
            "Reference",
            "Walkthroughs",
            "World & Reference",
            "Live revision",
            "Read article",
            "Single-section article",
        ]
    )
    return list(dict.fromkeys(values))


def translated_clone(content: Tag, translate: ChineseTranslator) -> Tag:
    clone_soup = BeautifulSoup(str(content), "html.parser")
    clone = clone_soup.select_one(".wiki-source-content")
    assert clone is not None
    clone["data-lang-panel"] = "zh"
    clone["lang"] = "zh-CN"
    clone["class"] = ["wiki-source-content", "wiki-source-content-zh"]
    clone["hidden"] = ""
    for element in clone.select("[id]"):
        element["id"] = f"zh-{element['id']}"
    for link in clone.select("a[href]"):
        href = link.get("href", "")
        parsed = urllib.parse.urlsplit(href)
        if not parsed.scheme and not parsed.netloc and parsed.fragment:
            link["href"] = urllib.parse.urlunsplit(
                (parsed.scheme, parsed.netloc, parsed.path, parsed.query, f"zh-{parsed.fragment}")
            )
    for node in list(clone.find_all(string=True)):
        if isinstance(node, Comment):
            node.extract()
            continue
        if node.parent.name in SKIP_TRANSLATION_PARENTS:
            continue
        original = str(node)
        normalized = normalize_text(original)
        if not translatable(normalized):
            continue
        leading = original[: len(original) - len(original.lstrip())]
        trailing = original[len(original.rstrip()) :]
        node.replace_with(NavigableString(leading + translate(normalized) + trailing))
    return clone


def extension_for(source: str, content_type: str) -> str:
    path_suffix = Path(urllib.parse.urlparse(source).path).suffix.casefold()
    if path_suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}:
        return ".jpg" if path_suffix == ".jpeg" else path_suffix
    guessed = mimetypes.guess_extension(content_type.split(";", 1)[0].strip())
    return ".jpg" if guessed == ".jpe" else (guessed or ".bin")


def download_image(source: str, directory: Path) -> tuple[str, str]:
    request = urllib.request.Request(source, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read()
        content_type = response.headers.get("Content-Type", "application/octet-stream")
    digest = hashlib.sha256(payload).hexdigest()[:20]
    target = directory / f"{digest}{extension_for(source, content_type)}"
    if not target.exists():
        target.write_bytes(payload)
    return source, target.name


def localize_images(pages: list[tuple[Path, BeautifulSoup]], output: Path) -> dict[str, str]:
    sources = sorted(
        {
            image.get("src", "")
            for _, soup in pages
            for image in soup.select(".wiki-source-content img[src]")
            if image.get("src", "").startswith(("http://", "https://"))
        }
    )
    image_dir = output / "assets/images/wiki"
    image_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output / "assets/data/wiki-image-manifest.json"
    existing: dict[str, str] = {}
    if manifest_path.is_file():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
    mapping = {
        source: existing[source]
        for source in sources
        if source in existing and (image_dir / existing[source]).is_file()
    }
    missing = [source for source in sources if source not in mapping]
    if mapping:
        print(f"reused {len(mapping)}/{len(sources)} localized wiki images", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(download_image, source, image_dir): source for source in missing}
        for index, future in enumerate(concurrent.futures.as_completed(futures), 1):
            source, filename = future.result()
            mapping[source] = filename
            if index % 25 == 0 or index == len(missing):
                print(f"downloaded {index}/{len(missing)} missing wiki images", flush=True)
    used_files = set(mapping.values())
    for path in image_dir.iterdir():
        if path.is_file() and path.name not in used_files:
            path.unlink()
    return mapping


def add_copy(element: Tag, english: str, chinese: str) -> None:
    element["data-copy-en"] = english
    element["data-copy-zh"] = chinese


def repair_local_fragments(wiki_directory: Path) -> int:
    parsed: dict[str, BeautifulSoup] = {
        path.name: BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        for path in sorted(wiki_directory.glob("*.html"))
    }
    ids = {
        name: {str(element["id"]) for element in soup.select("[id]")}
        for name, soup in parsed.items()
    }
    repaired = 0
    changed_pages: set[str] = set()
    for source_name, soup in parsed.items():
        for link in soup.select("a[href]"):
            href = link.get("href", "")
            parsed_href = urllib.parse.urlsplit(href)
            if parsed_href.scheme or parsed_href.netloc or not parsed_href.fragment:
                continue
            target_name = Path(parsed_href.path).name or source_name
            if target_name not in ids or parsed_href.fragment in ids[target_name]:
                continue
            link["href"] = urllib.parse.urlunsplit(
                (parsed_href.scheme, parsed_href.netloc, parsed_href.path, parsed_href.query, "")
            )
            repaired += 1
            changed_pages.add(source_name)
    for name in changed_pages:
        (wiki_directory / name).write_text(str(parsed[name]), encoding="utf-8", newline="\n")
    return repaired


def finalize(preview: Path, output: Path, cache_path: Path, *, reset_cache: bool = False) -> None:
    manifest = json.loads((preview / "wiki-manifest.json").read_text(encoding="utf-8"))
    translator = ChineseTranslator(cache_path, protected_terms(manifest), reset_cache=reset_cache)
    texts = collect_texts(preview)
    print(f"translation corpus: {len(texts)} unique text fragments", flush=True)
    translator.translate_many(texts)

    parsed_pages: list[tuple[Path, BeautifulSoup]] = []
    for path in sorted((preview / "wiki").glob("*.html")):
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        for comment in soup.find_all(string=lambda value: isinstance(value, Comment)):
            comment.extract()
        parsed_pages.append((path, soup))
    image_map = localize_images(parsed_pages, output)

    wiki_output = output / "wiki"
    if wiki_output.exists():
        shutil.rmtree(wiki_output)
    wiki_output.mkdir(parents=True, exist_ok=True)

    manifest_by_slug = {entry["slug"]: entry for entry in manifest.get("pages", [])}
    for source_path, soup in parsed_pages:
        english = soup.select_one(".wiki-source-content[data-lang-panel='en']")
        if english is None:
            raise RuntimeError(f"missing English article content in {source_path.name}")
        chinese = translated_clone(english, translator)
        placeholder = soup.select_one(".wiki-language-note")
        if placeholder:
            placeholder.replace_with(chinese)
        else:
            english.insert_after(chinese)

        for image in soup.select(".wiki-source-content img[src]"):
            source = image.get("src", "")
            if source in image_map:
                image["src"] = f"../assets/images/wiki/{image_map[source]}"

        slug = source_path.stem
        entry = manifest_by_slug.get(slug, {})
        category = entry.get("category", "Reference")
        breadcrumb = soup.select_one(".breadcrumb span:last-child")
        if breadcrumb:
            add_copy(breadcrumb, category, ZH_CATEGORIES.get(category, category))

        # Each language needs its own fragment targets. A shared TOC would send
        # Chinese readers to hidden English headings.
        english_toc = soup.select_one(".wiki-toc-links")
        if english_toc:
            english_toc["data-lang-panel"] = "en"
            toc_soup = BeautifulSoup(str(english_toc), "html.parser")
            chinese_toc = toc_soup.select_one(".wiki-toc-links")
            assert chinese_toc is not None
            chinese_toc["data-lang-panel"] = "zh"
            chinese_toc["lang"] = "zh-CN"
            chinese_toc["hidden"] = ""
            for toc_link in chinese_toc.select("a"):
                href = toc_link.get("href", "")
                if href.startswith("#"):
                    toc_link["href"] = f"#zh-{href[1:]}"
                label = normalize_text(toc_link.get_text(" ", strip=True))
                if translatable(label):
                    toc_link.string = translator(label)
            empty = chinese_toc.select_one(".wiki-toc-empty")
            if empty:
                empty.string = "单节文章"
            english_toc.insert_after(chinese_toc)

        license_box = soup.new_tag("div", attrs={"class": "wiki-license-note"})
        license_box.append(BeautifulSoup(
            '<span data-copy-en="Text adapted from the community-maintained Chronoromancer Wiki under CC BY-SA 4.0." '
            'data-copy-zh="文字内容改编自社区维护的 Chronoromancer Wiki，并依照 CC BY-SA 4.0 使用。">'
            'Text adapted from the community-maintained Chronoromancer Wiki under CC BY-SA 4.0.</span>',
            "html.parser",
        ))
        article = soup.select_one(".wiki-article")
        if article:
            article.append(license_box)

        (wiki_output / source_path.name).write_text(str(soup), encoding="utf-8", newline="\n")
        print(f"finalized wiki/{source_path.name}", flush=True)

    repaired_fragments = repair_local_fragments(wiki_output)
    print(f"removed {repaired_fragments} stale cross-article fragments", flush=True)

    index = BeautifulSoup((preview / "wiki.html").read_text(encoding="utf-8"), "html.parser")
    for card in index.select("[data-wiki-card]"):
        category = card.get("data-category", "Reference")
        card["data-search"] = (
            f"{card.get('data-search', '')} {ZH_CATEGORIES.get(category, category)}"
        ).strip()
        category_label = card.select_one(".wiki-card-category")
        if category_label:
            add_copy(category_label, category, ZH_CATEGORIES.get(category, category))
        image_label = card.select_one(".wiki-card-images")
        if image_label:
            english = normalize_text(image_label.get_text(" ", strip=True))
            count_match = re.match(r"(\d+)", english)
            count = count_match.group(1) if count_match else "0"
            add_copy(image_label, english, f"{count} 张图片")
        revision = card.select_one("p")
        if revision:
            english = normalize_text(revision.get_text(" ", strip=True))
            chinese = english.replace("Live revision", "实时修订版")
            add_copy(revision, english, chinese)
        link = card.select_one("a")
        if link:
            add_copy(link, "Read article →", "阅读文章 →")
    for button in index.select("[data-wiki-filter]"):
        category = button.get("data-wiki-filter", "")
        spans = button.find_all("span", recursive=False)
        count = normalize_text(spans[-1].get_text(" ", strip=True)) if spans else ""
        english = "All" if category == "all" else category
        chinese = "全部" if category == "all" else ZH_CATEGORIES.get(category, english)
        button.clear()
        label = index.new_tag("span")
        add_copy(label, english, chinese)
        label.string = english
        count_label = index.new_tag("span")
        count_label.string = count
        button.append(label)
        button.append(" ")
        button.append(count_label)
        if category != "all":
            button["data-search-zh"] = ZH_CATEGORIES.get(category, category)
    (output / "wiki.html").write_text(str(index), encoding="utf-8", newline="\n")
    (output / "wiki-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (output / "assets/data").mkdir(parents=True, exist_ok=True)
    (output / "assets/data/wiki-image-manifest.json").write_text(
        json.dumps(image_map, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"finished {len(parsed_pages)} bilingual wiki pages", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", type=Path, required=True, help="Fetched wiki preview directory")
    parser.add_argument("--output", type=Path, required=True, help="Website output directory")
    parser.add_argument("--cache", type=Path, required=True, help="Persistent translation cache JSON")
    parser.add_argument(
        "--reset-cache",
        action="store_true",
        help="Discard cached translations and rebuild them with the current model settings",
    )
    args = parser.parse_args()
    finalize(
        args.preview.resolve(),
        args.output.resolve(),
        args.cache.resolve(),
        reset_cache=args.reset_cache,
    )


if __name__ == "__main__":
    main()
