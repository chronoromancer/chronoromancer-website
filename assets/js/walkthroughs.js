(function () {
  "use strict";

  const cards = Array.from(document.querySelectorAll("[data-guide-card]"));
  const search = document.querySelector("[data-guide-search]");
  const resultCount = document.querySelector("[data-guide-result-count]");
  const empty = document.querySelector("[data-guide-empty]");

  function activeFilter() {
    const active = document.querySelector("[data-guide-filter].is-active");
    return active ? active.dataset.guideFilter : "all";
  }

  function applyGuideFilters() {
    if (!cards.length) return;
    const filter = activeFilter();
    const query = search ? search.value.trim().toLocaleLowerCase() : "";
    let visible = 0;

    cards.forEach((card) => {
      const categoryMatch = filter === "all" || card.dataset.category === filter;
      const searchMatch = !query || (card.dataset.search || "").includes(query);
      card.hidden = !(categoryMatch && searchMatch);
      if (!card.hidden) visible += 1;
    });

    document.querySelectorAll("[data-guide-section]").forEach((section) => {
      section.hidden = !section.querySelector("[data-guide-card]:not([hidden])");
    });

    if (resultCount) resultCount.textContent = String(visible);
    if (empty) empty.hidden = visible !== 0;
  }

  document.querySelectorAll("[data-guide-filter]").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll("[data-guide-filter]").forEach((candidate) => candidate.classList.remove("is-active"));
      button.classList.add("is-active");
      applyGuideFilters();
    });
  });

  if (search) {
    search.addEventListener("input", applyGuideFilters);
    document.addEventListener("keydown", (event) => {
      if (event.key === "/" && !/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName)) {
        event.preventDefault();
        search.focus();
      }
    });
  }

  const progress = document.querySelector("[data-reading-progress]");
  function updateReadingProgress() {
    if (!progress) return;
    const scrollable = document.documentElement.scrollHeight - window.innerHeight;
    const percentage = scrollable > 0 ? Math.min(100, Math.max(0, (window.scrollY / scrollable) * 100)) : 0;
    progress.style.width = `${percentage}%`;
  }

  const tocLinks = Array.from(document.querySelectorAll(".guide-toc a"));
  const observedHeadings = Array.from(document.querySelectorAll(".markdown-body h2[id], .markdown-body h3[id]"));
  if ("IntersectionObserver" in window && observedHeadings.length) {
    const observer = new IntersectionObserver((entries) => {
      const visible = entries.filter((entry) => entry.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
      if (!visible) return;
      tocLinks.forEach((link) => link.classList.toggle("is-current", link.getAttribute("href") === `#${visible.target.id}` && !link.closest("[hidden]")));
    }, { rootMargin: "-18% 0px -72% 0px", threshold: 0 });
    observedHeadings.forEach((heading) => observer.observe(heading));
  }

  if (progress) {
    window.addEventListener("scroll", updateReadingProgress, { passive: true });
    updateReadingProgress();
  }

  document.querySelectorAll("[data-language]").forEach((button) => {
    button.addEventListener("click", () => {
      if (!window.location.hash) return;
      const current = decodeURIComponent(window.location.hash.slice(1));
      const target = button.dataset.language === "zh"
        ? (current.startsWith("zh-") ? current : `zh-${current}`)
        : current.replace(/^zh-/, "");
      const destination = document.getElementById(target);
      if (destination) {
        history.replaceState(null, "", `#${encodeURIComponent(target)}`);
        destination.scrollIntoView({ block: "start" });
      }
    });
  });

  document.addEventListener("DOMContentLoaded", () => {
    if (!document.body.classList.contains("lang-zh") || !window.location.hash) return;
    const current = decodeURIComponent(window.location.hash.slice(1));
    if (current.startsWith("zh-")) return;
    const translatedTarget = document.getElementById(`zh-${current}`);
    if (translatedTarget) {
      history.replaceState(null, "", `#${encodeURIComponent(`zh-${current}`)}`);
      translatedTarget.scrollIntoView({ block: "start" });
    }
  });

  applyGuideFilters();
})();
