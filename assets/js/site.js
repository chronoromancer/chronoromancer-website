(function () {
  "use strict";

  const config = window.CHRONO_SITE_CONFIG || {};
  const russianCopy = window.CHRONO_RU_TRANSLATIONS || {};
  const russianCharacters = window.CHRONO_RU_CHARACTERS || {};
  const storageKey = "chronoromancer-language";
  const common = {
    en: {
      navHome: "Home",
      navStory: "Story",
      navCharacters: "Characters",
      navGuides: "Guides",
      navGallery: "Gallery",
      navWiki: "Player Wiki",
      navDownload: "Download",
      navBuy: "Buy",
      menuOpen: "Open navigation",
      menuClose: "Close navigation",
      languageLabel: "Language",
      footerDescription: "An adults-only time-travel sandbox RPG. Public website artwork is SFW.",
      footerExplore: "Explore",
      footerCommunity: "Community",
      footerLegal: "Legal",
      footerPrivacy: "Privacy",
      footerTerms: "Terms",
      officialItch: "Official itch.io page",
      copyright: "Chronoromancer Studio. All rights reserved.",
      close: "Close",
      previous: "Previous",
      next: "Next",
      comingSoon: "Preparing",
      available: "Available"
    },
    zh: {
      navHome: "首页",
      navStory: "剧情",
      navCharacters: "角色",
      navGuides: "攻略",
      navGallery: "画廊",
      navWiki: "玩家 Wiki",
      navDownload: "下载",
      navBuy: "购买",
      menuOpen: "打开导航菜单",
      menuClose: "关闭导航菜单",
      languageLabel: "语言",
      footerDescription: "一款仅限成人的时间旅行沙盒 RPG。公开网站仅使用适合公开展示的素材。",
      footerExplore: "浏览",
      footerCommunity: "社区",
      footerLegal: "法律信息",
      footerPrivacy: "隐私政策",
      footerTerms: "使用条款",
      officialItch: "itch.io 官方页面",
      copyright: "Chronoromancer Studio。保留所有权利。",
      close: "关闭",
      previous: "上一张",
      next: "下一张",
      comingSoon: "正在准备",
      available: "可用"
    },
    ru: {
      navHome: "Главная",
      navStory: "Сюжет",
      navCharacters: "Персонажи",
      navGuides: "Руководства",
      navGallery: "Галерея",
      navWiki: "Вики игроков",
      navDownload: "Скачать",
      navBuy: "Купить",
      menuOpen: "Открыть меню навигации",
      menuClose: "Закрыть меню навигации",
      languageLabel: "Язык",
      footerDescription: "Ролевая песочница о путешествиях во времени только для взрослых. На общедоступном сайте используются безопасные для просмотра изображения.",
      footerExplore: "Разделы",
      footerCommunity: "Сообщество",
      footerLegal: "Правовая информация",
      footerPrivacy: "Конфиденциальность",
      footerTerms: "Условия",
      officialItch: "Официальная страница на itch.io",
      copyright: "Chronoromancer Studio. Все права защищены.",
      close: "Закрыть",
      previous: "Предыдущее",
      next: "Следующее",
      comingSoon: "Готовится",
      available: "Доступно"
    }
  };

  let currentLanguage = getInitialLanguage();
  let galleryItems = [];
  let activeGalleryIndex = 0;

  function pageSupportsRussian() {
    return Boolean(document.querySelector('[data-language="ru"]'));
  }

  function getInitialLanguage() {
    const requested = new URLSearchParams(window.location.search).get("lang");
    if (requested === "zh" || requested === "zh-CN") return "zh";
    if ((requested === "ru" || requested === "ru-RU") && pageSupportsRussian()) return "ru";
    if (requested === "en") return "en";
    try {
      const stored = localStorage.getItem(storageKey);
      if (stored === "ru") return pageSupportsRussian() ? "ru" : "en";
      return stored === "zh" ? "zh" : "en";
    } catch (error) {
      return "en";
    }
  }

  function localizedValue(element, attribute) {
    const english = element.dataset[`${attribute}En`];
    if (currentLanguage === "zh") return element.dataset[`${attribute}Zh`] || english;
    if (currentLanguage === "ru") return element.dataset[`${attribute}Ru`] || russianCopy[english] || english;
    return english;
  }

  function setStoredLanguage(language) {
    try {
      if (!pageSupportsRussian() && language === "en" && localStorage.getItem(storageKey) === "ru") return;
      localStorage.setItem(storageKey, language);
    } catch (error) {
      // The site still works when storage is unavailable.
    }
  }

  function applyLanguage(language) {
    currentLanguage = language === "zh" || language === "ru" ? language : "en";
    const copy = common[currentLanguage];
    document.documentElement.lang = currentLanguage === "zh" ? "zh-CN" : currentLanguage === "ru" ? "ru" : "en";
    document.body.classList.toggle("lang-zh", currentLanguage === "zh");
    document.body.classList.toggle("lang-ru", currentLanguage === "ru");

    document.querySelectorAll("[data-i18n]").forEach((element) => {
      const value = copy[element.dataset.i18n];
      if (value) element.textContent = value;
    });

    document.querySelectorAll("[data-copy-en][data-copy-zh]").forEach((element) => {
      element.textContent = localizedValue(element, "copy");
    });

    document.querySelectorAll("[data-placeholder-en][data-placeholder-zh]").forEach((element) => {
      element.placeholder = localizedValue(element, "placeholder");
    });

    document.querySelectorAll("[data-aria-en][data-aria-zh]").forEach((element) => {
      element.setAttribute("aria-label", localizedValue(element, "aria"));
    });

    document.querySelectorAll("[data-lang-panel]").forEach((panel) => {
      panel.hidden = panel.dataset.langPanel !== currentLanguage;
    });

    document.querySelectorAll("[data-language]").forEach((button) => {
      const selected = button.dataset.language === currentLanguage;
      button.classList.toggle("is-active", selected);
      button.setAttribute("aria-pressed", String(selected));
    });

    document.querySelectorAll(".language-switch").forEach((switcher) => {
      switcher.setAttribute("aria-label", copy.languageLabel);
    });

    const title = currentLanguage === "zh"
      ? document.body.dataset.titleZh
      : currentLanguage === "ru"
        ? (document.body.dataset.titleRu || russianCopy[document.body.dataset.titleEn] || document.body.dataset.titleEn)
        : document.body.dataset.titleEn;
    if (title) document.title = title;
    const navToggle = document.querySelector("[data-nav-toggle]");
    if (navToggle) {
      navToggle.setAttribute("aria-label", common[currentLanguage][navToggle.classList.contains("is-open") ? "menuClose" : "menuOpen"]);
    }
    setStoredLanguage(currentLanguage);
    updateGalleryModal();
    applyCharacterFilters();
  }

  function initialiseNavigation() {
    const toggle = document.querySelector("[data-nav-toggle]");
    const nav = document.querySelector("[data-nav-menu]");
    if (!toggle || !nav) return;

    toggle.addEventListener("click", () => {
      const isOpen = nav.classList.toggle("is-open");
      toggle.classList.toggle("is-open", isOpen);
      toggle.setAttribute("aria-expanded", String(isOpen));
      toggle.setAttribute("aria-label", common[currentLanguage][isOpen ? "menuClose" : "menuOpen"]);
    });

    nav.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", () => {
        nav.classList.remove("is-open");
        toggle.classList.remove("is-open");
        toggle.setAttribute("aria-expanded", "false");
      });
    });
  }

  function initialiseConfiguredLinks() {
    document.querySelectorAll("[data-site-version]").forEach((element) => {
      element.textContent = config.release || "V0.9.8cc";
    });

    document.querySelectorAll("[data-config-link]").forEach((element) => {
      const path = element.dataset.configLink.split(".");
      let value = config;
      path.forEach((key) => { value = value && value[key]; });
      if (typeof value === "string" && value) element.href = value;
    });

    document.querySelectorAll("[data-download-id]").forEach((element) => {
      const item = config.downloads && config.downloads[element.dataset.downloadId];
      const status = element.querySelector("[data-download-status]");
      if (item && item.enabled && item.url) {
        element.href = item.url;
        element.classList.remove("is-disabled");
        element.removeAttribute("aria-disabled");
        if (status) status.textContent = common[currentLanguage].available;
      } else {
        element.removeAttribute("href");
        element.classList.add("is-disabled");
        element.setAttribute("aria-disabled", "true");
        if (status) status.textContent = common[currentLanguage].comingSoon;
      }
    });
  }

  function initialiseGallery() {
    galleryItems = Array.from(document.querySelectorAll("[data-gallery-item]"));
    if (!galleryItems.length) return;

    galleryItems.forEach((item, index) => {
      item.addEventListener("click", () => openGallery(index));
    });

    document.querySelectorAll("[data-gallery-filter]").forEach((button) => {
      button.addEventListener("click", () => {
        document.querySelectorAll("[data-gallery-filter]").forEach((candidate) => candidate.classList.remove("is-active"));
        button.classList.add("is-active");
        const filter = button.dataset.galleryFilter;
        galleryItems.forEach((item) => {
          item.hidden = filter !== "all" && item.dataset.category !== filter;
        });
      });
    });

    const modal = document.querySelector("[data-lightbox]");
    if (!modal) return;
    modal.querySelector("[data-lightbox-close]").addEventListener("click", closeGallery);
    modal.querySelector("[data-lightbox-prev]").addEventListener("click", () => moveGallery(-1));
    modal.querySelector("[data-lightbox-next]").addEventListener("click", () => moveGallery(1));
    modal.addEventListener("click", (event) => {
      if (event.target === modal) closeGallery();
    });
    document.addEventListener("keydown", (event) => {
      if (!modal.classList.contains("is-open")) return;
      if (event.key === "Escape") closeGallery();
      if (event.key === "ArrowLeft") moveGallery(-1);
      if (event.key === "ArrowRight") moveGallery(1);
    });
  }

  function openGallery(index) {
    activeGalleryIndex = index;
    const modal = document.querySelector("[data-lightbox]");
    if (!modal) return;
    updateGalleryModal();
    modal.classList.add("is-open");
    modal.setAttribute("aria-hidden", "false");
    document.body.classList.add("modal-open");
    modal.querySelector("[data-lightbox-close]").focus();
  }

  function closeGallery() {
    const modal = document.querySelector("[data-lightbox]");
    if (!modal) return;
    modal.classList.remove("is-open");
    modal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("modal-open");
  }

  function moveGallery(direction) {
    const visible = galleryItems.filter((item) => !item.hidden);
    const current = galleryItems[activeGalleryIndex];
    let visibleIndex = visible.indexOf(current);
    if (visibleIndex < 0) visibleIndex = 0;
    const next = visible[(visibleIndex + direction + visible.length) % visible.length];
    activeGalleryIndex = galleryItems.indexOf(next);
    updateGalleryModal();
  }

  function updateGalleryModal() {
    const modal = document.querySelector("[data-lightbox]");
    const item = galleryItems[activeGalleryIndex];
    if (!modal || !item) return;
    const source = item.querySelector("img");
    const caption = currentLanguage === "zh"
      ? item.dataset.captionZh
      : currentLanguage === "ru"
        ? (item.dataset.captionRu || russianCopy[item.dataset.captionEn] || item.dataset.captionEn)
        : item.dataset.captionEn;
    modal.querySelector("[data-lightbox-image]").src = source.src;
    modal.querySelector("[data-lightbox-image]").alt = caption || source.alt;
    modal.querySelector("[data-lightbox-caption]").textContent = caption || "";
  }

  function initialiseCharacterFilters() {
    document.querySelectorAll("[data-character-filter]").forEach((button) => {
      button.addEventListener("click", () => {
        document.querySelectorAll("[data-character-filter]").forEach((candidate) => candidate.classList.remove("is-active"));
        button.classList.add("is-active");
        applyCharacterFilters();
      });
    });
    const search = document.querySelector("[data-character-search]");
    if (search) search.addEventListener("input", applyCharacterFilters);
  }

  function initialiseCharacterDirectory() {
    const grid = document.querySelector("[data-character-grid]");
    const characters = Array.isArray(window.CHRONO_CHARACTERS) ? window.CHRONO_CHARACTERS : [];
    if (!grid || !characters.length) return;

    const eraLabels = {
      present: { en: "Present", zh: "现代", ru: "Современность" },
      medieval: { en: "Medieval", zh: "中世纪", ru: "Средневековье" },
      future: { en: "Future", zh: "未来", ru: "Будущее" }
    };
    const fragment = document.createDocumentFragment();

    characters.forEach((character) => {
      const card = document.createElement("article");
      card.className = "character-card";
      card.dataset.characterCard = "";
      card.dataset.era = character.era;
      card.dataset.searchEn = `${character.name} ${character.id} ${character.era} ${character.descriptionEn}`;
      card.dataset.searchZh = `${character.name} ${character.id} ${character.descriptionZh}`;
      card.dataset.searchRu = `${character.name} ${character.id} ${russianCharacters[character.id] || ""}`;

      const portrait = document.createElement("img");
      portrait.src = character.image;
      portrait.alt = character.name;
      portrait.loading = "lazy";
      portrait.decoding = "async";

      const copy = document.createElement("div");
      const tag = document.createElement("span");
      tag.className = "card-tag";
      tag.dataset.copyEn = eraLabels[character.era].en;
      tag.dataset.copyZh = eraLabels[character.era].zh;
      tag.dataset.copyRu = eraLabels[character.era].ru;
      tag.textContent = eraLabels[character.era][currentLanguage];

      const name = document.createElement("h2");
      name.textContent = character.name;

      const description = document.createElement("p");
      description.dataset.copyEn = character.descriptionEn;
      description.dataset.copyZh = character.descriptionZh;
      description.dataset.copyRu = russianCharacters[character.id] || character.descriptionEn;
      description.textContent = currentLanguage === "zh"
        ? character.descriptionZh
        : currentLanguage === "ru"
          ? description.dataset.copyRu
          : character.descriptionEn;

      copy.append(tag, name, description);
      card.append(portrait, copy);
      fragment.append(card);
    });

    grid.replaceChildren(fragment);
    document.querySelectorAll("[data-character-count]").forEach((element) => {
      const era = element.dataset.characterCount;
      const count = era === "all" ? characters.length : characters.filter((character) => character.era === era).length;
      element.textContent = String(count);
    });
  }

  function applyCharacterFilters() {
    const cards = Array.from(document.querySelectorAll("[data-character-card]"));
    if (!cards.length) return;
    const active = document.querySelector("[data-character-filter].is-active");
    const filter = active ? active.dataset.characterFilter : "all";
    const search = document.querySelector("[data-character-search]");
    const locale = currentLanguage === "zh" ? "zh-CN" : currentLanguage === "ru" ? "ru" : "en";
    const query = search ? search.value.trim().toLocaleLowerCase(locale) : "";
    let visibleCount = 0;
    cards.forEach((card) => {
      const eraMatch = filter === "all" || card.dataset.era === filter;
      const haystack = `${card.dataset.searchEn || ""} ${card.dataset.searchZh || ""} ${card.dataset.searchRu || ""} ${card.textContent}`.toLocaleLowerCase(locale);
      const searchMatch = !query || haystack.includes(query);
      card.hidden = !(eraMatch && searchMatch);
      if (!card.hidden) visibleCount += 1;
    });
    const empty = document.querySelector("[data-character-empty]");
    if (empty) empty.hidden = visibleCount !== 0;
  }

  document.addEventListener("DOMContentLoaded", () => {
    initialiseNavigation();
    initialiseConfiguredLinks();
    initialiseGallery();
    initialiseCharacterDirectory();
    initialiseCharacterFilters();

    document.querySelectorAll("[data-language]").forEach((button) => {
      button.addEventListener("click", () => {
        applyLanguage(button.dataset.language);
        initialiseConfiguredLinks();
      });
    });

    document.querySelectorAll("[data-current-year]").forEach((element) => {
      element.textContent = new Date().getFullYear();
    });

    applyLanguage(currentLanguage);
    initialiseConfiguredLinks();
  });
})();
