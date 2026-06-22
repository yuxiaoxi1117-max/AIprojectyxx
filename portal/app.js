// State
const state = {
  apps: [],
  defaultApp: null,
  currentToolApp: null,
  // chat sessions: appId -> { messages: [], sessionId: string }
  sessions: {},
};

// ── Init ────────────────────────────────────────────────────────────────────

async function init() {
  try {
    const res = await fetch('/apps.json');
    state.apps = await res.json();
    state.defaultApp = state.apps.find(a => a.default) || state.apps[0];
    renderToolsGrid();
    renderWelcome('chat-messages', state.defaultApp?.name || 'AI 助手');
    if (state.defaultApp) {
      document.getElementById('chat-model-name').textContent =
        (state.defaultApp.icon || '') + ' ' + state.defaultApp.name;
    }
  } catch (e) {
    console.error('Failed to load apps.json', e);
  }
}

// ── Tab switching ────────────────────────────────────────────────────────────

function switchTab(tab) {
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
  document.getElementById(`tab-${tab}`).classList.add('active');
  document.querySelector(`[data-tab="${tab}"]`).classList.add('active');
}

// ── Tools Grid ──────────────────────────────────────────────────────────────

function renderToolsGrid() {
  const grid = document.getElementById('tools-grid');
  grid.innerHTML = '';
  // Show all non-default apps on the tools page
  const toolApps = state.apps.filter(a => !a.default);
  toolApps.forEach(app => {
    const card = document.createElement('div');
    card.className = 'app-card';
    card.innerHTML = `
      <div class="card-icon">${app.icon || '🤖'}</div>
      <div class="card-name">${app.name}</div>
      <div class="card-desc">${app.description || ''}</div>
      <div class="card-btn">开始对话 →</div>
    `;
    card.onclick = () => openToolChat(app);
    grid.appendChild(card);
  });
}

function openToolChat(app) {
  state.currentToolApp = app;
  document.getElementById('tools-grid-view').classList.add('hidden');
  document.getElementById('tools-chat-view').classList.remove('hidden');
  document.getElementById('tool-chat-title').textContent = `${app.icon || ''} ${app.name}`;
  document.getElementById('tool-chat-desc').textContent = app.description || '';

  const msgEl = document.getElementById('tool-messages');
  if (!state.sessions[app.id]?.messages?.length) {
    renderWelcome('tool-messages', app.name);
  } else {
    // Re-render existing messages
    msgEl.innerHTML = '';
    state.sessions[app.id].messages.forEach(m => appendBubble('tool-messages', m.role, m.content));
  }
  document.getElementById('tool-input').focus();
}

function backToTools() {
  document.getElementById('tools-chat-view').classList.add('hidden');
  document.getElementById('tools-grid-view').classList.remove('hidden');
  state.currentToolApp = null;
}

// ── Rendering helpers ────────────────────────────────────────────────────────

function renderWelcome(containerId, name) {
  const el = document.getElementById(containerId);
  el.innerHTML = `
    <div class="welcome">
      <div class="welcome-icon">✨</div>
      <h3>${name}</h3>
      <p>有什么可以帮助你的？</p>
    </div>`;
}

function clearWelcome(containerId) {
  const el = document.getElementById(containerId);
  const welcome = el.querySelector('.welcome');
  if (welcome) welcome.remove();
}

function appendBubble(containerId, role, content) {
  clearWelcome(containerId);
  const el = document.getElementById(containerId);
  const wrap = document.createElement('div');
  wrap.className = `message ${role === 'user' ? 'user' : 'ai'}`;
  wrap.innerHTML = `
    <div class="msg-role">${role === 'user' ? '你' : 'AI'}</div>
    <div class="bubble">${escapeHtml(content)}</div>`;
  el.appendChild(wrap);
  el.scrollTop = el.scrollHeight;
  return wrap.querySelector('.bubble');
}

function createStreamingBubble(containerId) {
  clearWelcome(containerId);
  const el = document.getElementById(containerId);
  const wrap = document.createElement('div');
  wrap.className = 'message ai';
  wrap.innerHTML = `<div class="msg-role">AI</div><div class="bubble"><span class="cursor"></span></div>`;
  el.appendChild(wrap);
  el.scrollTop = el.scrollHeight;
  return wrap.querySelector('.bubble');
}

function escapeHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ── Session management ───────────────────────────────────────────────────────

function getSession(appId) {
  if (!state.sessions[appId]) {
    state.sessions[appId] = { messages: [], sessionId: crypto.randomUUID() };
  }
  return state.sessions[appId];
}

function pushMessage(appId, role, content) {
  getSession(appId).messages.push({ role, content });
}

// ── API call ─────────────────────────────────────────────────────────────────

async function streamCompletion(appId, messages, bubbleEl, containerId) {
  const session = getSession(appId);

  const res = await fetch('/api/v1/chat/completions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: appId,
      messages,
      stream: true,
      chat_id: session.sessionId,
    }),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`API error ${res.status}: ${err}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let fullText = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value, { stream: true });
    const lines = chunk.split('\n');

    for (const line of lines) {
      if (!line.startsWith('data:')) continue;
      const data = line.slice(5).trim();
      if (data === '[DONE]') break;
      try {
        const parsed = JSON.parse(data);
        const delta = parsed.choices?.[0]?.delta?.content || '';
        if (delta) {
          fullText += delta;
          // Update bubble content (remove cursor first)
          bubbleEl.innerHTML = escapeHtml(fullText) + '<span class="cursor"></span>';
          document.getElementById(containerId).scrollTop =
            document.getElementById(containerId).scrollHeight;
        }
      } catch (_) {}
    }
  }

  // Finalize bubble (remove cursor)
  bubbleEl.innerHTML = escapeHtml(fullText);
  return fullText;
}

// ── Chat Tab ─────────────────────────────────────────────────────────────────

async function sendChat() {
  const app = state.defaultApp;
  if (!app) return;

  const input = document.getElementById('chat-input');
  const text = input.value.trim();
  if (!text) return;

  input.value = '';
  autoResize(input);
  setLoading('chat-send', true);

  pushMessage(app.id, 'user', text);
  appendBubble('chat-messages', 'user', text);
  const bubble = createStreamingBubble('chat-messages');

  const session = getSession(app.id);
  const messages = session.messages.map(m => ({ role: m.role, content: m.content }));

  try {
    const reply = await streamCompletion(app.id, messages, bubble, 'chat-messages');
    pushMessage(app.id, 'assistant', reply);
  } catch (e) {
    bubble.textContent = `错误：${e.message}`;
  } finally {
    setLoading('chat-send', false);
  }
}

function handleChatKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendChat();
  }
}

// ── Tool Chat ─────────────────────────────────────────────────────────────────

async function sendTool() {
  const app = state.currentToolApp;
  if (!app) return;

  const input = document.getElementById('tool-input');
  const text = input.value.trim();
  if (!text) return;

  input.value = '';
  autoResize(input);
  setLoading('tool-send', true);

  pushMessage(app.id, 'user', text);
  appendBubble('tool-messages', 'user', text);
  const bubble = createStreamingBubble('tool-messages');

  const session = getSession(app.id);
  const messages = session.messages.map(m => ({ role: m.role, content: m.content }));

  try {
    const reply = await streamCompletion(app.id, messages, bubble, 'tool-messages');
    pushMessage(app.id, 'assistant', reply);
  } catch (e) {
    bubble.textContent = `错误：${e.message}`;
  } finally {
    setLoading('tool-send', false);
  }
}

function handleToolKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendTool();
  }
}

// ── Utilities ────────────────────────────────────────────────────────────────

function setLoading(btnId, loading) {
  document.getElementById(btnId).disabled = loading;
}

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 160) + 'px';
}

// ── Start ────────────────────────────────────────────────────────────────────
init();
