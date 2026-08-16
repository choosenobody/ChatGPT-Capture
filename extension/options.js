const endpoint = document.querySelector("#endpoint");
const token = document.querySelector("#token");
const enabled = document.querySelector("#enabled");
const status = document.querySelector("#status");

const DEFAULTS = { endpoint: "", token: "", enabled: false };

function endpointPermissionPattern(value) {
  if (!value) return null;
  const url = new URL(value);
  const isLocal = url.hostname === "localhost" || url.hostname === "127.0.0.1";
  if (url.protocol !== "https:" && !(isLocal && url.protocol === "http:")) {
    throw new Error("Use HTTPS. Plain HTTP is allowed only for localhost/127.0.0.1.");
  }
  return `${url.protocol}//${url.hostname}/*`;
}

async function load() {
  const config = await chrome.storage.local.get(DEFAULTS);
  endpoint.value = config.endpoint;
  token.value = config.token;
  enabled.checked = config.enabled;
}

function showStatus(message, isError = false) {
  status.textContent = message;
  status.style.color = isError ? "#b42318" : "#067647";
  setTimeout(() => {
    status.textContent = "";
    status.style.color = "";
  }, 2500);
}

document.querySelector("#save").addEventListener("click", async () => {
  try {
    const nextEndpoint = endpoint.value.trim().replace(/\/$/, "");
    const nextToken = token.value.trim();
    const previous = await chrome.storage.local.get(DEFAULTS);

    if (enabled.checked && (!nextEndpoint || !nextToken)) {
      throw new Error("Endpoint and token are required when capture is enabled.");
    }

    const nextPattern = endpointPermissionPattern(nextEndpoint);
    const previousPattern = endpointPermissionPattern(previous.endpoint);

    if (nextPattern) {
      const granted = await chrome.permissions.request({ origins: [nextPattern] });
      if (!granted) throw new Error("Endpoint permission was not granted.");
    }

    await chrome.storage.local.set({
      endpoint: nextEndpoint,
      token: nextToken,
      enabled: enabled.checked,
    });

    if (previousPattern && previousPattern !== nextPattern) {
      await chrome.permissions.remove({ origins: [previousPattern] });
    }

    showStatus("Saved locally");
  } catch (error) {
    showStatus(error.message || String(error), true);
  }
});

load();
