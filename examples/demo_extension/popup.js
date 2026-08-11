// Popup logic: toggles highlighting via chrome.storage — every page's
// content script reacts to storage changes, so it works even when the
// popup is opened as a full tab (as demodsl does).
const toggleBtn = document.getElementById("toggle");
const resetBtn = document.getElementById("reset");
const countEl = document.getElementById("count");
const usesEl = document.getElementById("uses");

// Opened as a regular tab (demo) rather than a real popup -> center the card.
if (window.innerWidth > 420) document.body.classList.add("tab-view");

async function refresh() {
  const data = await chrome.storage.local.get({ uses: 0, enabled: false, lastCount: 0 });
  usesEl.textContent = String(data.uses);
  countEl.textContent = String(data.lastCount);
  toggleBtn.textContent = data.enabled
    ? "Désactiver le surlignage"
    : "Activer le surlignage";
  toggleBtn.classList.toggle("on", data.enabled);
}

toggleBtn.addEventListener("click", async () => {
  const data = await chrome.storage.local.get({ uses: 0, enabled: false });
  const enabled = !data.enabled;
  const patch = { enabled, uses: enabled ? data.uses + 1 : data.uses };
  if (!enabled) patch.lastCount = 0;
  await chrome.storage.local.set(patch);
  refresh();
});

resetBtn.addEventListener("click", async () => {
  await chrome.storage.local.set({ uses: 0, lastCount: 0, enabled: false });
  refresh();
});

chrome.storage.onChanged.addListener(refresh);
refresh();
