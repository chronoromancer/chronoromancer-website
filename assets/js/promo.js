(() => {
  "use strict";

  const config = window.CHRONO_SITE_CONFIG || {};
  const downloads = config.downloads || {};
  const promoAnalytics = config.promoAnalytics || {};
  const siteRoot = new URL("../../", document.baseURI);
  const platformMap = {
    windows: { direct: "directWin", mega: "mega", torrent: "torrentPc", google: "googleDrive", itch: "itch" },
    pc: { direct: "directPc", mega: "mega", torrent: "torrentPc", google: "googleDrive", itch: "itch" },
    mac: { direct: "directMac", mega: "mega", torrent: "torrentMac", google: "googleDrive", itch: "itch" },
    android: { direct: "directAndroid", mega: "mega", torrent: "torrentAndroid", google: "googleDrive", itch: "itch" }
  };
  let selectedPlatform = "windows";

  function newSessionId() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") return window.crypto.randomUUID();
    return "10000000-1000-4000-8000-100000000000".replace(/[018]/g, (character) =>
      (Number(character) ^ (window.crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (Number(character) / 4)))).toString(16)
    );
  }

  function getSessionId() {
    const key = "chronoromancer_promo_session_v1";
    try {
      let value = window.sessionStorage.getItem(key);
      if (!value) {
        value = newSessionId();
        window.sessionStorage.setItem(key, value);
      }
      return value;
    } catch (_error) {
      return newSessionId();
    }
  }

  function isAutomatedBrowser() {
    const userAgent = navigator.userAgent || "";
    return navigator.webdriver || /bot|crawler|spider|headless|lighthouse|pagespeed|preview|prerender/i.test(userAgent);
  }

  function trackPromoEvent(eventName, dimensions = {}) {
    if (!promoAnalytics.enabled || !promoAnalytics.endpoint || isAutomatedBrowser()) return;

    const copyButton = document.querySelector("[data-copy-code]");
    const incoming = new URLSearchParams(window.location.search);
    const payload = {
      event_name: eventName,
      language: document.documentElement.lang || "",
      campaign_code: copyButton ? copyButton.dataset.copyCode || "" : "",
      campaign: incoming.get("campaign") || incoming.get("utm_campaign") || "",
      page_path: window.location.pathname,
      source: incoming.get("source") || incoming.get("utm_source") || "direct",
      session_id: getSessionId(),
      platform: dimensions.platform || "",
      channel: dimensions.channel || "",
      target: dimensions.target || ""
    };

    fetch(promoAnalytics.endpoint, {
      method: "POST",
      mode: "cors",
      credentials: "omit",
      keepalive: true,
      headers: { "Content-Type": "text/plain;charset=UTF-8" },
      body: JSON.stringify(payload)
    }).catch(() => {});
  }

  function trackVisiblePromoView() {
    if (document.prerendering || document.visibilityState !== "visible") return;
    trackPromoEvent("promo_view");
  }

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
    selectedPlatform = platformMap[platform] ? platform : "windows";
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
      trackPromoEvent("code_copy");
    });
  }

  const allowedParameters = ["source", "campaign", "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"];
  const incoming = new URLSearchParams(window.location.search);
  document.querySelectorAll("[data-preserve-campaign]").forEach((link) => {
    const target = new URL(link.href, document.baseURI);
    allowedParameters.forEach((parameter) => {
      if (incoming.has(parameter)) target.searchParams.set(parameter, incoming.get(parameter));
    });
    link.href = target.href;
  });

  selectPlatform("windows");

  document.querySelectorAll("[data-download-channel]").forEach((link) => {
    link.addEventListener("click", () => {
      if (!link.classList.contains("is-disabled")) {
        trackPromoEvent("download_click", {
          platform: selectedPlatform,
          channel: link.dataset.downloadChannel || ""
        });
      }
    });
  });

  document.querySelectorAll('[data-community-link="patreon"], [data-community-link="afdian"]').forEach((link) => {
    link.addEventListener("click", () => {
      trackPromoEvent("support_click", { target: link.dataset.communityLink || "" });
    });
  });

  if (document.visibilityState === "visible" && !document.prerendering) {
    trackVisiblePromoView();
  } else {
    document.addEventListener("visibilitychange", trackVisiblePromoView, { once: true });
  }
})();
