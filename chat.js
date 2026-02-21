/**
 * static/js/chat.js
 * ──────────────────
 * Handles:
 *   - Basic-auth credential capture & storage (sessionStorage only)
 *   - Sending queries to /api/chat
 *   - Rendering markdown responses
 *   - Displaying source citations
 *   - Typing indicator, auto-scroll, textarea auto-resize
 *   - Suggested question injection
 *   - Rate-limit / error display
 */

"use strict";

/* ── State ──────────────────────────────────────────────────────────────────── */
let credentials = null;   // { username, password } set after auth modal

/* ── DOM refs ───────────────────────────────────────────────────────────────── */
const authModal   = document.getElementById("authModal");
const authForm    = document.getElementById("authForm");
const authError   = document.getElementById("authError");
const chatForm    = document.getElementById("chatForm");
const queryInput  = document.getElementById("queryInput");
const sendBtn     = document.getElementById("sendBtn");
const messages    = document.getElementById("messages");
const typingEl    = document.getElementById("typing");
const suggestions = document.querySelectorAll(".suggestions li");

/* ── marked.js config ───────────────────────────────────────────────────────── */
marked.setOptions({ breaks: true, gfm: true });

/* ═══════════════════════════════════════════════════════════════════════════════
   AUTH MODAL
   ═══════════════════════════════════════════════════════════════════════════ */

/** Show auth modal; hide chat UI interaction */
function showAuthModal() {
  authModal.classList.remove("hidden");
  sendBtn.disabled = true;
}

authForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value;
  if (!username || !password) return;

  // Test credentials against a lightweight endpoint
  try {
    const res = await fetch("/health");  // public endpoint to test connectivity
    // We validate actual creds by attempting a minimal API call
    const testRes = await fetch("/api/chat", {
      method: "POST",
      headers: buildHeaders({ username, password }),
      body: JSON.stringify({ query: "hello" }),
    });

    if (testRes.status === 401) {
      authError.hidden = false;
      return;
    }

    // Credentials accepted
    credentials = { username, password };
    authModal.classList.add("hidden");
    sendBtn.disabled = false;
    authError.hidden = true;

    // If test returned a real answer, display it
    const data = await testRes.json();
    if (data.answer) appendBotMessage(data.answer, data.sources || []);

  } catch (err) {
    authError.textContent = "⚠️ Network error. Is the server running?";
    authError.hidden = false;
  }
});

/* ═══════════════════════════════════════════════════════════════════════════════
   HELPERS
   ═══════════════════════════════════════════════════════════════════════════ */

/** Build Authorization header from credentials object */
function buildHeaders(creds) {
  const b64 = btoa(`${creds.username}:${creds.password}`);
  return {
    "Content-Type": "application/json",
    "Authorization": `Basic ${b64}`,
  };
}

/** Scroll messages panel to bottom */
function scrollToBottom() {
  messages.scrollTo({ top: messages.scrollHeight, behavior: "smooth" });
}

/** Auto-resize textarea as user types */
queryInput.addEventListener("input", () => {
  queryInput.style.height = "auto";
  queryInput.style.height = Math.min(queryInput.scrollHeight, 140) + "px";
});

/** Send on Enter (Shift+Enter = newline) */
queryInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    chatForm.dispatchEvent(new Event("submit"));
  }
});

/** Inject suggestion text into input on click */
suggestions.forEach((li) => {
  li.addEventListener("click", () => {
    queryInput.value = li.textContent.trim();
    queryInput.dispatchEvent(new Event("input"));  // trigger resize
    queryInput.focus();
  });
});

/* ═══════════════════════════════════════════════════════════════════════════════
   MESSAGE RENDERING
   ═══════════════════════════════════════════════════════════════════════════ */

function appendUserMessage(text) {
  const row = document.createElement("div");
  row.className = "message user-message";
  row.innerHTML = `
    <div class="avatar user-avatar" aria-hidden="true">👤</div>
    <div class="bubble">${escapeHtml(text)}</div>
  `;
  messages.appendChild(row);
  scrollToBottom();
}

function appendBotMessage(markdownText, sources = []) {
  const row = document.createElement("div");
  row.className = "message bot-message";

  const htmlBody = marked.parse(markdownText);
  let sourcesHtml = "";

  if (sources.length) {
    const tags = sources.map(
      (s) => `<span class="source-tag">📄 ${escapeHtml(s.source)} p.${s.page}</span>`
    ).join("");
    sourcesHtml = `
      <div class="sources-section">
        <details>
          <summary>📚 ${sources.length} source(s) used</summary>
          <div style="margin-top:6px">${tags}</div>
        </details>
      </div>
    `;
  }

  row.innerHTML = `
    <div class="avatar bot-avatar" aria-hidden="true">🩺</div>
    <div class="bubble">
      ${htmlBody}
      ${sourcesHtml}
    </div>
  `;
  messages.appendChild(row);
  scrollToBottom();
}

function appendErrorMessage(text) {
  const row = document.createElement("div");
  row.className = "message bot-message";
  row.innerHTML = `
    <div class="avatar bot-avatar" aria-hidden="true">⚠️</div>
    <div class="bubble error-bubble">${escapeHtml(text)}</div>
  `;
  messages.appendChild(row);
  scrollToBottom();
}

function escapeHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/* ═══════════════════════════════════════════════════════════════════════════════
   CHAT FORM SUBMIT
   ═══════════════════════════════════════════════════════════════════════════ */

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!credentials) { showAuthModal(); return; }

  const query = queryInput.value.trim();
  if (!query) return;

  // ── Clear input, disable send ────────────────────────────────────────────────
  queryInput.value = "";
  queryInput.style.height = "auto";
  sendBtn.disabled = true;

  // ── Render user message ──────────────────────────────────────────────────────
  appendUserMessage(query);

  // ── Show typing indicator ────────────────────────────────────────────────────
  typingEl.hidden = false;
  scrollToBottom();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: buildHeaders(credentials),
      body: JSON.stringify({ query }),
    });

    const data = await res.json();

    typingEl.hidden = true;

    if (!res.ok) {
      // Handle rate limit, auth failure, server errors
      if (res.status === 401) {
        credentials = null;
        showAuthModal();
        appendErrorMessage("Session expired. Please sign in again.");
      } else if (res.status === 429) {
        appendErrorMessage(
          "⏳ Too many requests. Please wait a moment and try again."
        );
      } else if (res.status === 503) {
        appendErrorMessage(
          "🔧 The knowledge base is not yet set up. "
          + "Please run the ingestion script and restart the server."
        );
      } else {
        appendErrorMessage(data.error || "An unexpected error occurred.");
      }
    } else {
      appendBotMessage(data.answer, data.sources || []);
    }

  } catch (err) {
    typingEl.hidden = true;
    appendErrorMessage(
      "🌐 Network error. Please check your connection and try again."
    );
    console.error("Chat fetch error:", err);
  } finally {
    sendBtn.disabled = false;
    queryInput.focus();
  }
});

/* ═══════════════════════════════════════════════════════════════════════════════
   INIT
   ═══════════════════════════════════════════════════════════════════════════ */
// Show auth modal on page load
showAuthModal();
