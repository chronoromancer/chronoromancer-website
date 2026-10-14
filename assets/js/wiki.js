(function () {
  "use strict";

  const cards = Array.from(document.querySelectorAll("[data-wiki-card]"));
  const search = document.querySelector("[data-wiki-search]");
  const count = document.querySelector("[data-wiki-result-count]");
  const empty = document.querySelector("[data-wiki-empty]");
  let activeCategory = "all";

  function applyFilters() {
    if (!cards.length) return;
    const query = search ? search.value.trim().toLocaleLowerCase() : "";
    let visible = 0;
    cards.forEach((card) => {
      const categoryMatches = activeCategory === "all" || card.dataset.category === activeCategory;
      const searchMatches = !query || (card.dataset.search || "").includes(query);
      const show = categoryMatches && searchMatches;
      card.hidden = !show;
      if (show) visible += 1;
    });
    if (count) count.textContent = String(visible);
    if (empty) empty.hidden = visible !== 0;
  }

  document.querySelectorAll("[data-wiki-filter]").forEach((button) => {
    button.addEventListener("click", () => {
      activeCategory = button.dataset.wikiFilter;
      document.querySelectorAll("[data-wiki-filter]").forEach((candidate) => {
        candidate.classList.toggle("is-active", candidate === button);
      });
      applyFilters();
    });
  });

  if (search) {
    search.addEventListener("input", applyFilters);
    document.addEventListener("keydown", (event) => {
      if (event.key === "/" && document.activeElement !== search) {
        event.preventDefault();
        search.focus();
      }
    });
  }

  const tocToggle = document.querySelector("[data-wiki-toc-toggle]");
  const toc = tocToggle && tocToggle.closest(".wiki-toc");
  if (tocToggle && toc) {
    tocToggle.addEventListener("click", () => {
      const open = toc.classList.toggle("is-open");
      tocToggle.setAttribute("aria-expanded", String(open));
    });
    toc.querySelectorAll(".wiki-toc-links a").forEach((link) => {
      link.addEventListener("click", () => {
        toc.classList.remove("is-open");
        tocToggle.setAttribute("aria-expanded", "false");
      });
    });
  }

  applyFilters();
})();
