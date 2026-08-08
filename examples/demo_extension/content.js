// Content script: highlights links on demand, driven by popup messages.
(() => {
  if (window.__demodslHighlighter) return;
  window.__demodslHighlighter = true;
  document.documentElement.setAttribute("data-ext-loaded", "true");

  const STYLE_ID = "__demodsl_hl_style";

  function highlightOn() {
    if (!document.getElementById(STYLE_ID)) {
      const s = document.createElement("style");
      s.id = STYLE_ID;
      s.textContent =
        "a { background: #fde047 !important; color: #1c1917 !important;" +
        " border-radius: 3px; box-shadow: 0 0 0 3px #fde047 !important;" +
        " transition: background .3s ease; }";
      document.head.appendChild(s);
    }
    return document.querySelectorAll("a").length;
  }

  function highlightOff() {
    const s = document.getElementById(STYLE_ID);
    if (s) s.remove();
    return 0;
  }

  if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.onMessage) {
    chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
      if (msg && msg.type === "highlight-on") {
        sendResponse({ count: highlightOn() });
      } else if (msg && msg.type === "highlight-off") {
        sendResponse({ count: highlightOff() });
      }
    });
  }

  // Storage-driven control: reacts to popup toggles even when the popup is
  // opened as a full tab (single-tab demo flow).
  if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.onChanged) {
    const apply = (enabled) => {
      const count = enabled ? highlightOn() : highlightOff();
      if (enabled) chrome.storage.local.set({ lastCount: count });
    };
    chrome.storage.local.get({ enabled: false }).then((d) => apply(d.enabled));
    chrome.storage.onChanged.addListener((changes, area) => {
      if (area === "local" && changes.enabled) apply(changes.enabled.newValue);
    });
  }
})();
