const DEFAULTS = {
  endpoint: "",
  token: "",
  enabled: false,
};

chrome.runtime.onInstalled.addListener(async () => {
  const current = await chrome.storage.local.get(DEFAULTS);
  await chrome.storage.local.set(current);
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== "CAPTURE_TURN") return;

  (async () => {
    const config = await chrome.storage.local.get(DEFAULTS);
    if (!config.enabled) {
      sendResponse({ ok: false, skipped: "disabled" });
      return;
    }
    if (!config.endpoint || !config.token) {
      sendResponse({ ok: false, skipped: "not_configured" });
      return;
    }

    const endpointUrl = new URL(config.endpoint);
    const permissionPattern = `${endpointUrl.protocol}//${endpointUrl.hostname}/*`;
    const permitted = await chrome.permissions.contains({ origins: [permissionPattern] });
    if (!permitted) {
      sendResponse({ ok: false, skipped: "endpoint_permission_missing" });
      return;
    }

    const response = await fetch(config.endpoint.replace(/\/$/, "") + "/v1/capture", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${config.token}`,
      },
      body: JSON.stringify(message.payload),
    });

    const text = await response.text();
    sendResponse({ ok: response.ok, status: response.status, body: text.slice(0, 500) });
  })().catch((error) => sendResponse({ ok: false, error: String(error) }));

  return true;
});
