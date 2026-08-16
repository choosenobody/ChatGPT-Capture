const SOURCE = "chatgpt-web";
const CAPTURE_DELAY_MS = 1200;
const seen = new Set();
let scanTimer = null;
let lastUrl = location.href;

function conversationId() {
  const match = location.pathname.match(/\/c\/([^/?#]+)/);
  return match?.[1] || null;
}

function conversationTitle() {
  return document.title.replace(/\s*[-–—]\s*ChatGPT\s*$/i, "").trim() || "Untitled ChatGPT conversation";
}

function normalizeText(text) {
  return (text || "").replace(/\u00a0/g, " ").replace(/[ \t]+\n/g, "\n").replace(/\n{3,}/g, "\n\n").trim();
}

function fnv1a(str) {
  let hash = 0x811c9dc5;
  for (let i = 0; i < str.length; i++) {
    hash ^= str.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  return (hash >>> 0).toString(16).padStart(8, "0");
}

function extractTurns() {
  const articles = [...document.querySelectorAll('article[data-testid^="conversation-turn-"]')];
  const nodes = articles.length
    ? articles
    : [...document.querySelectorAll('[data-message-author-role="user"], [data-message-author-role="assistant"]')];

  const turns = [];
  for (const node of nodes) {
    const roleNode = node.matches?.('[data-message-author-role]')
      ? node
      : node.querySelector?.('[data-message-author-role]');
    const role = roleNode?.getAttribute("data-message-author-role");
    if (role !== "user" && role !== "assistant") continue;

    const textRoot = roleNode || node;
    const text = normalizeText(textRoot.innerText || textRoot.textContent || "");
    if (!text) continue;

    const domId = node.getAttribute?.("data-testid") || "";
    const stableId = `${conversationId()}:${domId || fnv1a(role + "\n" + text)}`;
    turns.push({ stableId, role, text });
  }
  return turns;
}

function redactObviousSecrets(text) {
  const patterns = [
    [/sk-[A-Za-z0-9_-]{20,}/g, "[REDACTED_OPENAI_KEY]"],
    [/gh[pousr]_[A-Za-z0-9]{20,}/g, "[REDACTED_GITHUB_TOKEN]"],
    [/-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/g, "[REDACTED_PRIVATE_KEY]"],
    [/\b(?:seed phrase|mnemonic)\s*[:=]\s*[^\n]{20,}/gi, "[REDACTED_SEED_PHRASE]"],
  ];
  return patterns.reduce((out, [re, replacement]) => out.replace(re, replacement), text);
}

function pairCompletedTurns(turns) {
  const pairs = [];
  for (let i = 0; i < turns.length - 1; i++) {
    const user = turns[i];
    const assistant = turns[i + 1];
    if (user.role !== "user" || assistant.role !== "assistant") continue;
    pairs.push({ user, assistant });
  }
  return pairs;
}

function isAssistantStillStreaming() {
  return Boolean(
    document.querySelector('button[data-testid="stop-button"]') ||
    document.querySelector('button[aria-label*="Stop" i]') ||
    document.querySelector('button[aria-label*="停止" i]')
  );
}

async function scan() {
  if (isAssistantStillStreaming()) return;
  const currentConversationId = conversationId();
  if (!currentConversationId) return;
  const turns = extractTurns();
  for (const pair of pairCompletedTurns(turns)) {
    const pairId = `${pair.user.stableId}->${pair.assistant.stableId}`;
    if (seen.has(pairId)) continue;

    const payload = {
      schema_version: 1,
      source: SOURCE,
      conversation_id: currentConversationId,
      conversation_title: conversationTitle(),
      conversation_url: location.href,
      captured_at: new Date().toISOString(),
      turn_id: pairId,
      user_message: redactObviousSecrets(pair.user.text),
      assistant_message: redactObviousSecrets(pair.assistant.text),
    };

    chrome.runtime.sendMessage({ type: "CAPTURE_TURN", payload }, (response) => {
      if (chrome.runtime.lastError) return;
      if (response?.ok) seen.add(pairId);
    });
  }
}

function scheduleScan() {
  clearTimeout(scanTimer);
  scanTimer = setTimeout(scan, CAPTURE_DELAY_MS);
}

new MutationObserver(scheduleScan).observe(document.documentElement, {
  childList: true,
  subtree: true,
  characterData: true,
});

setInterval(() => {
  if (location.href !== lastUrl) {
    lastUrl = location.href;
    seen.clear();
  }
  scheduleScan();
}, 1500);

scheduleScan();
