// DemoDSL Demo Banner — content script
// Injects a fixed banner at the top of every page + marks <html> for verification.
(function () {
  "use strict";

  // Guard: don't inject twice
  if (document.getElementById("__demodsl_demo_banner")) return;

  const banner = document.createElement("div");
  banner.id = "__demodsl_demo_banner";
  banner.innerHTML =
    '<span class="badge">LIVE</span> Demo Mode — Powered by DemoDSL Chrome Extensions Plugin';

  // Insert as first child of body
  if (document.body) {
    document.body.insertBefore(banner, document.body.firstChild);
  } else {
    document.addEventListener("DOMContentLoaded", () => {
      document.body.insertBefore(banner, document.body.firstChild);
    });
  }

  // Mark document for automated verification
  document.documentElement.setAttribute("data-demodsl-ext", "demo-banner");
})();
