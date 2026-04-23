// DemoDSL Demo Banner — background service worker
// Uses chrome.scripting API to inject content scripts on every navigation.
// This is the reliable approach when content_scripts from the manifest
// don't auto-inject (e.g. Playwright launch_persistent_context).

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === "complete" && tab.url && !tab.url.startsWith("chrome://")) {
    chrome.scripting.insertCSS({ target: { tabId }, files: ["style.css"] }).catch(() => {});
    chrome.scripting.executeScript({ target: { tabId }, files: ["content.js"] }).catch(() => {});
  }
});
