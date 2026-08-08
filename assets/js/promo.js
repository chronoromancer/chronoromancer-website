(() => {
  "use strict";

  const config = window.CHRONO_SITE_CONFIG || {};
  const downloads = config.downloads || {};
  const siteRoot = new URL("../../", document.baseURI);
  const platformMap = {
    windows: { direct: "directWin", mega: "mega", torrent: "torrentPc", google: "googleDrive", itch: "itch" },
    pc: { direct: "directPc", mega: "mega", torrent: "torrentPc", google: "googleDrive", itch: "itch" },
    mac: { direct: "directMac", mega: "mega", torrent: "torrentMac", google: "googleDrive", itch: "itch" },
    android: { direct: "directAndroid", mega: "mega", torrent: "torrentAndroid", google: "googleDrive", itch: "itch" }
  };

  function resolveUrl(url) {
    if (!url) return "";
    return new URL(url, siteRoot).href;
  }

  function setConfiguredLink(element, item) {
    if (!item || !item.enabled || !item.url) {
      element.removeAttribute("href");
      element.classList.add("is-disabled");
      element.setAttribute("aria-disabled", "true");
      return;
    }

    element.href = resolveUrl(item.url);
    element.classList.remove("is-disabled");
    element.removeAttribute("aria-disabled");
  }

  function selectPlatform(platform) {
    const mapping = platformMap[platform] || platformMap.windows;
    document.querySelectorAll("[data-platform]").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.platform === platform));
    });

    document.querySelectorAll("[data-download-channel]").forEach((link) => {
      const id = mapping[link.dataset.downloadChannel];
      setConfiguredLink(link, downloads[id]);
    });

    const selected = document.querySelector(`[data-platform="${platform}"]`);
    const note = document.querySelector("[data-platform-note]");
    if (selected && note) note.textContent = selected.dataset.platformDescription || "";
  }

  document.querySelectorAll("[data-platform]").forEach((button) => {
    button.addEventListener("click", () => selectPlatform(button.dataset.platform));
  });

  document.querySelectorAll("[data-community-link]").forEach((element) => {
    const url = config.community && config.community[element.dataset.communityLink];
    if (url) element.href = url;
  });

  document.querySelectorAll("[data-site-version]").forEach((element) => {
    element.textContent = config.promotionRelease || config.release || "";
  });

  const copyButton = document.querySelector("[data-copy-code]");
  if (copyButton) {
    copyButton.addEventListener("click", async () => {
      const code = copyButton.dataset.copyCode || "";
      const original = copyButton.textContent;
      try {
        await navigator.clipboard.writeText(code);
      } catch (_error) {
        const helper = document.createElement("textarea");
        helper.value = code;
        helper.setAttribute("readonly", "");
        helper.style.position = "fixed";
        helper.style.opacity = "0";
        document.body.appendChild(helper);
        helper.select();
        document.execCommand("copy");
        helper.remove();
      }
      copyButton.textContent = copyButton.dataset.copiedLabel || original;
      window.setTimeout(() => { copyButton.textContent = original; }, 1800);
    });
  }

  const allowedParameters = ["utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"];
  const incoming = new URLSearchParams(window.location.search);
  document.querySelectorAll("[data-preserve-campaign]").forEach((link) => {
    const target = new URL(link.href, document.baseURI);
    allowedParameters.forEach((parameter) => {
      if (incoming.has(parameter)) target.searchParams.set(parameter, incoming.get(parameter));
    });
    link.href = target.href;
  });

  selectPlatform("windows");
})();
