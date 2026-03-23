/* ══════════════════════════════════════════════════════
   AURELIUS — Advanced App Logic
   Features: Multi-session history, streaming, commands,
   system prompts, temperature, markdown, export, themes
══════════════════════════════════════════════════════ */

// ── State ─────────────────────────────────────────────
const state = {
  sessions: JSON.parse(localStorage.getItem('aurelius_sessions') || '[]'),
  currentSessionId: null,
  history: [],         // { role, content }[]
  systemPrompt: localStorage.getItem('aurelius_system') || '',
  temperature: parseFloat(localStorage.getItem('aurelius_temp') || '0.7'),
  streaming: localStorage.getItem('aurelius_stream') !== 'false',
  model: localStorage.getItem('aurelius_model') || 'claude-sonnet-4-5',
  memory: localStorage.getItem('aurelius_memory') !== 'false',
  thinking: false,
  totalTokens: 0,
};

// ── DOM ───────────────────────────────────────────────
const $ = id => document.getElementById(id);
const els = {
  sidebar:      $('sidebar'),
  sidebarToggle:$('sidebarToggle'),
  mobileMenu:   $('mobileMenu'),
  newChatBtn:   $('newChatBtn'),
  chatHistory:  $('chatHistory'),
  modelSelect:  $('modelSelect'),
  themeToggle:  $('themeToggle'),
  clearBtn:     $('clearBtn'),
  exportBtn:    $('exportBtn'),
  statusPill:   $('statusPill'),
  statusText:   $('statusText'),
  pulseDot:     document.querySelector('.pulse-dot'),
  tokenCounter: $('tokenCounter'),
  chatScroll:   $('chatScroll'),
  welcomeScreen:$('welcomeScreen'),
  messages:     $('messages'),
  input:        $('userInput'),
  sendBtn:      $('sendBtn'),
  charCount:    $('charCount'),
  streamToggle: $('streamToggle'),
  streamLabel:  $('streamLabel'),
  tempToggle:   $('tempToggle'),
  tempLabel:    $('tempLabel'),
  memoryBtn:    $('memoryBtn'),
  memoryLabel:  $('memoryLabel'),
  systemBtn:    $('systemPromptBtn'),
  systemInput:  $('systemInput'),
  modelBadge:   $('modelBadge'),
  timeGreet:    $('timeGreet'),
};

// ── Init ──────────────────────────────────────────────
function init() {
  applyTheme();
  syncUI();
  setTimeGreeting();
  renderHistory();
  bindEvents();
  startNewSession(false);
}

function syncUI() {
  els.modelSelect.value = state.model;
  els.modelBadge.textContent = state.model;
  els.streamLabel.textContent = `Stream ${state.streaming ? 'ON' : 'OFF'}`;
  els.tempLabel.textContent = `Temp ${state.temperature}`;
  els.memoryLabel.textContent = `Memory ${state.memory ? 'ON' : 'OFF'}`;
  els.systemInput.value = state.systemPrompt;
  $('tempSlider').value = state.temperature;
  $('tempDisplay').textContent = state.temperature;
  if (state.streaming) els.streamToggle.classList.add('active');
  else els.streamToggle.classList.remove('active');
  if (state.memory) els.memoryBtn.classList.add('active');
  else els.memoryBtn.classList.remove('active');
}

function setTimeGreeting() {
  const h = new Date().getHours();
  const greet = h < 12 ? 'Morning' : h < 17 ? 'Afternoon' : 'Evening';
  if (els.timeGreet) els.timeGreet.textContent = greet;
}

// ── Sessions / History ────────────────────────────────
function startNewSession(save = true) {
  if (save && state.history.length > 0) saveCurrentSession();
  state.currentSessionId = Date.now().toString();
  state.history = [];
  state.totalTokens = 0;
  els.messages.innerHTML = '';
  els.welcomeScreen.style.display = '';
  els.tokenCounter.textContent = '0 tokens';
  renderHistory();
}

function saveCurrentSession() {
  if (!state.history.length) return;
  const firstUser = state.history.find(m => m.role === 'user');
  const title = firstUser ? firstUser.content.slice(0, 45) + (firstUser.content.length > 45 ? '…' : '') : 'Untitled';
  const existing = state.sessions.findIndex(s => s.id === state.currentSessionId);
  const session = { id: state.currentSessionId, title, messages: state.history, ts: Date.now() };
  if (existing >= 0) state.sessions[existing] = session;
  else state.sessions.unshift(session);
  if (state.sessions.length > 30) state.sessions = state.sessions.slice(0, 30);
  localStorage.setItem('aurelius_sessions', JSON.stringify(state.sessions));
  renderHistory();
}

function loadSession(id) {
  const session = state.sessions.find(s => s.id === id);
  if (!session) return;
  saveCurrentSession();
  state.currentSessionId = session.id;
  state.history = [...session.messages];
  els.messages.innerHTML = '';
  els.welcomeScreen.style.display = 'none';
  state.history.forEach(m => renderMessage(m.role, m.content, false));
  renderHistory();
  scrollToBottom();
}

function deleteSession(id, e) {
  e.stopPropagation();
  state.sessions = state.sessions.filter(s => s.id !== id);
  localStorage.setItem('aurelius_sessions', JSON.stringify(state.sessions));
  if (state.currentSessionId === id) startNewSession(false);
  else renderHistory();
}

function renderHistory() {
  els.chatHistory.innerHTML = '';
  if (!state.sessions.length) {
    els.chatHistory.innerHTML = '<div style="padding:12px 10px;font-size:12px;color:var(--text3)">No conversations yet</div>';
    return;
  }
  state.sessions.forEach(s => {
    const d = document.createElement('div');
    d.className = `history-item ${s.id === state.currentSessionId ? 'active' : ''}`;
    d.onclick = () => loadSession(s.id);
    d.innerHTML = `
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
      </svg>
      <span class="history-title">${escapeHtml(s.title)}</span>
      <button class="history-delete" title="Delete" onclick="deleteSession('${s.id}',event)">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>`;
    els.chatHistory.appendChild(d);
  });
}

// ── Send Message ──────────────────────────────────────
async function sendMessage(overrideText) {
  const raw = (overrideText || els.input.value).trim();
  if (!raw || state.thinking) return;

  // Slash commands
  if (raw.startsWith('/')) {
    handleCommand(raw);
    els.input.value = '';
    resetInputHeight();
    return;
  }

  els.welcomeScreen.style.display = 'none';
  renderMessage('user', raw);
  state.history.push({ role: 'user', content: raw });
  estimateTokens(raw);

  els.input.value = '';
  resetInputHeight();
  els.charCount.textContent = '0 / ∞';

  setThinking(true);
  const typingEl = renderTyping();

  try {
    const messages = buildMessages();
    let fullResponse = '';

    if (state.streaming) {
      // Streaming
      const aiWrapper = createAiWrapper();
      typingEl.remove();

      const stream = await puter.ai.chat(messages, {
        model: state.model,
        stream: true,
      });

      for await (const chunk of stream) {
        const token = chunk?.text || chunk?.delta?.text || '';
        if (token) {
          fullResponse += token;
          updateStreamingMessage(aiWrapper, fullResponse);
          scrollToBottom();
        }
      }
      finalizeStreamingMessage(aiWrapper, fullResponse);

    } else {
      // Non-streaming
      const res = await puter.ai.chat(messages, { model: state.model });
      fullResponse = res?.message?.content?.[0]?.text || res?.text || typeof res === 'string' ? res : 'No response.';
      typingEl.remove();
      renderMessage('assistant', fullResponse);
    }

    state.history.push({ role: 'assistant', content: fullResponse });
    estimateTokens(fullResponse);
    saveCurrentSession();

  } catch (err) {
    typingEl.remove();
    const errMsg = `**Error:** ${err.message || 'Something went wrong. Ensure you are signed into Puter at [puter.com](https://puter.com).'}`;
    renderMessage('assistant', errMsg);
    console.error('[Aurelius]', err);
  } finally {
    setThinking(false);
  }
}

function buildMessages() {
  const msgs = state.memory ? [...state.history] : [state.history[state.history.length - 1]];
  if (state.systemPrompt) {
    return [{ role: 'system', content: state.systemPrompt }, ...msgs];
  }
  return msgs;
}

// ── Slash Commands ────────────────────────────────────
function handleCommand(raw) {
  const parts = raw.slice(1).trim().split(' ');
  const cmd = parts[0].toLowerCase();
  const args = parts.slice(1).join(' ');

  switch (cmd) {
    case 'clear': clearChat(); break;
    case 'new': startNewSession(true); break;
    case 'export': exportChat(); break;
    case 'help': openModal('commandsModal'); break;
    case 'system':
      if (args) {
        state.systemPrompt = args;
        localStorage.setItem('aurelius_system', args);
        showSystemBadge(args);
        toast('System prompt set');
      } else {
        openModal('systemModal');
      }
      break;
    case 'temp':
      const t = parseFloat(args);
      if (!isNaN(t) && t >= 0 && t <= 1) {
        state.temperature = t;
        localStorage.setItem('aurelius_temp', t);
        els.tempLabel.textContent = `Temp ${t}`;
        toast(`Temperature set to ${t}`);
      } else {
        toast('Usage: /temp 0.0–1.0');
      }
      break;
    case 'model':
      if (args) {
        state.model = args;
        localStorage.setItem('aurelius_model', args);
        els.modelBadge.textContent = args;
        toast(`Model: ${args}`);
      }
      break;
    default:
      toast(`Unknown command: /${cmd}. Type /help`);
  }
}

// ── Render Messages ───────────────────────────────────
function renderMessage(role, content, animate = true) {
  const wrapper = document.createElement('div');
  wrapper.className = `msg-wrapper ${role}`;
  if (!animate) wrapper.style.animation = 'none';

  const isUser = role === 'user';
  const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  wrapper.innerHTML = `
    <div class="msg">
      <div class="msg-avatar ${isUser ? 'user-av' : 'ai-av'}">${isUser ? 'Y' : 'A'}</div>
      <div class="msg-content">
        <div class="msg-header">
          <span class="msg-name">${isUser ? 'You' : 'Aurelius'}</span>
          <span class="msg-time">${time}</span>
        </div>
        <div class="msg-body">${isUser ? escapeHtml(content).replace(/\n/g, '<br>') : renderMarkdown(content)}</div>
      </div>
      <div class="msg-actions">
        <button class="msg-action-btn" title="Copy" onclick="copyMsg(this,'${encodeURIComponent(content)}')">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
          </svg>
        </button>
      </div>
    </div>`;

  els.messages.appendChild(wrapper);
  scrollToBottom();
  return wrapper;
}

function renderTyping() {
  const wrapper = document.createElement('div');
  wrapper.className = 'msg-wrapper assistant';
  wrapper.innerHTML = `
    <div class="msg">
      <div class="msg-avatar ai-av">A</div>
      <div class="msg-content">
        <div class="msg-header">
          <span class="msg-name">Aurelius</span>
        </div>
        <div class="msg-body">
          <div class="typing-indicator">
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
          </div>
        </div>
      </div>
    </div>`;
  els.messages.appendChild(wrapper);
  scrollToBottom();
  return wrapper;
}

function createAiWrapper() {
  const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const wrapper = document.createElement('div');
  wrapper.className = 'msg-wrapper assistant';
  wrapper.innerHTML = `
    <div class="msg">
      <div class="msg-avatar ai-av">A</div>
      <div class="msg-content">
        <div class="msg-header">
          <span class="msg-name">Aurelius</span>
          <span class="msg-time">${time}</span>
        </div>
        <div class="msg-body streaming-body"></div>
      </div>
      <div class="msg-actions">
        <button class="msg-action-btn" title="Copy" onclick="copyMsg(this,'')">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
          </svg>
        </button>
      </div>
    </div>`;
  els.messages.appendChild(wrapper);
  return wrapper;
}

function updateStreamingMessage(wrapper, text) {
  const body = wrapper.querySelector('.streaming-body');
  if (body) body.innerHTML = renderMarkdown(text) + '<span class="cursor-blink">▋</span>';
}

function finalizeStreamingMessage(wrapper, text) {
  const body = wrapper.querySelector('.streaming-body');
  if (body) {
    body.innerHTML = renderMarkdown(text);
    body.classList.remove('streaming-body');
  }
  // Wire up copy button with final text
  const copyBtn = wrapper.querySelector('.msg-action-btn');
  if (copyBtn) copyBtn.setAttribute('onclick', `copyMsg(this,'${encodeURIComponent(text)}')`);
}

function showSystemBadge(text) {
  const d = document.createElement('div');
  d.className = 'system-badge';
  d.innerHTML = `
    <div class="system-badge-inner">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="3"/><path d="M19.07 4.93l-1.41 1.41M4.93 4.93l1.41 1.41M19.07 19.07l-1.41-1.41M4.93 19.07l1.41-1.41M21 12h-2M5 12H3M12 21v-2M12 5V3"/>
      </svg>
      System prompt active: ${escapeHtml(text.slice(0, 60))}${text.length > 60 ? '…' : ''}
    </div>`;
  els.messages.appendChild(d);
}

// ── Markdown Parser ───────────────────────────────────
function renderMarkdown(text) {
  let html = escapeHtml(text);

  // Fenced code blocks with language
  html = html.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
    const l = lang || 'code';
    const id = 'cb-' + Math.random().toString(36).slice(2, 8);
    return `<div class="code-block-wrap">
      <div class="code-header">
        <span class="code-lang">${escapeHtml(l)}</span>
        <button class="code-copy" id="${id}" onclick="copyCode(this,'${encodeURIComponent(code.trim())}')">Copy</button>
      </div>
      <pre><code>${code.trim()}</code></pre>
    </div>`;
  });

  // Inline code
  html = html.replace(/`([^`\n]+)`/g, '<code>$1</code>');

  // Headers
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');

  // Bold + Italic
  html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

  // Blockquote
  html = html.replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>');

  // HR
  html = html.replace(/^---$/gm, '<hr>');

  // Unordered list
  html = html.replace(/^[*\-] (.+)$/gm, '<li>$1</li>');
  html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');

  // Ordered list
  html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');

  // Links
  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

  // Tables (simple)
  html = html.replace(/\|(.+)\|\n\|[-| ]+\|\n((?:\|.+\|\n?)+)/g, (_, header, rows) => {
    const ths = header.split('|').filter(Boolean).map(c => `<th>${c.trim()}</th>`).join('');
    const trs = rows.trim().split('\n').map(r => {
      const tds = r.split('|').filter(Boolean).map(c => `<td>${c.trim()}</td>`).join('');
      return `<tr>${tds}</tr>`;
    }).join('');
    return `<table><thead><tr>${ths}</tr></thead><tbody>${trs}</tbody></table>`;
  });

  // Paragraphs (double newline → paragraph break, single → br)
  html = html.replace(/\n{2,}/g, '</p><p>');
  html = html.replace(/\n/g, '<br>');
  html = '<p>' + html + '</p>';

  // Clean up empty paragraphs around block elements
  html = html.replace(/<p>(<(?:div|pre|ul|ol|h[1-6]|blockquote|hr|table)[^>]*>)/g, '$1');
  html = html.replace(/<\/(?:div|pre|ul|ol|h[1-6]|blockquote|table)><\/p>/g, '</$1>');
  html = html.replace(/<p><\/p>/g, '');

  return html;
}

// ── Utility Functions ─────────────────────────────────
function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function scrollToBottom() {
  requestAnimationFrame(() => {
    els.chatScroll.scrollTop = els.chatScroll.scrollHeight;
  });
}

function resetInputHeight() {
  els.input.style.height = 'auto';
}

function estimateTokens(text) {
  state.totalTokens += Math.ceil(text.length / 4);
  els.tokenCounter.textContent = `~${state.totalTokens.toLocaleString()} tokens`;
}

function setThinking(val) {
  state.thinking = val;
  els.sendBtn.disabled = val;
  if (val) {
    els.statusText.textContent = 'Thinking…';
    els.pulseDot.classList.add('thinking');
  } else {
    els.statusText.textContent = 'Ready';
    els.pulseDot.classList.remove('thinking');
  }
}

function clearChat() {
  state.history = [];
  state.totalTokens = 0;
  els.messages.innerHTML = '';
  els.welcomeScreen.style.display = '';
  els.tokenCounter.textContent = '0 tokens';
  toast('Conversation cleared');
}

function exportChat() {
  if (!state.history.length) { toast('Nothing to export'); return; }
  const lines = [`# Aurelius Export\n**Date:** ${new Date().toLocaleString()}\n**Model:** ${state.model}\n`];
  if (state.systemPrompt) lines.push(`**System Prompt:** ${state.systemPrompt}\n`);
  lines.push('---\n');
  state.history.forEach(m => {
    const role = m.role === 'user' ? '**You**' : '**Aurelius**';
    lines.push(`${role}\n\n${m.content}\n\n---\n`);
  });
  const blob = new Blob([lines.join('\n')], { type: 'text/markdown' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = `aurelius-${Date.now()}.md`;
  a.click();
  URL.revokeObjectURL(url);
  toast('Chat exported');
}

function copyMsg(btn, encoded) {
  const text = decodeURIComponent(encoded);
  navigator.clipboard.writeText(text).then(() => {
    btn.classList.add('copied');
    setTimeout(() => btn.classList.remove('copied'), 1500);
  });
}

function copyCode(btn, encoded) {
  navigator.clipboard.writeText(decodeURIComponent(encoded)).then(() => {
    btn.textContent = 'Copied!';
    btn.classList.add('done');
    setTimeout(() => { btn.textContent = 'Copy'; btn.classList.remove('done'); }, 2000);
  });
}

function toast(msg) {
  const el = $('toast');
  el.textContent = msg;
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), 2500);
}

function useSuggestion(btn) {
  els.input.value = btn.textContent.trim();
  els.input.focus();
  autoResize();
}

function autoResize() {
  els.input.style.height = 'auto';
  els.input.style.height = Math.min(els.input.scrollHeight, 220) + 'px';
  els.charCount.textContent = els.input.value.length + ' / ∞';
}

// ── Modals ────────────────────────────────────────────
function openModal(id) {
  $(id).classList.add('open');
}
function closeModal(id) {
  $(id).classList.remove('open');
}
function saveSystemPrompt() {
  state.systemPrompt = els.systemInput.value.trim();
  localStorage.setItem('aurelius_system', state.systemPrompt);
  if (state.systemPrompt && state.history.length) showSystemBadge(state.systemPrompt);
  closeModal('systemModal');
  toast('System prompt applied');
}
function saveTemp() {
  state.temperature = parseFloat($('tempSlider').value);
  localStorage.setItem('aurelius_temp', state.temperature);
  els.tempLabel.textContent = `Temp ${state.temperature}`;
  closeModal('tempModal');
  toast(`Temperature: ${state.temperature}`);
}

// ── Theme ─────────────────────────────────────────────
function applyTheme() {
  const saved = localStorage.getItem('aurelius_theme') || 'dark';
  document.documentElement.setAttribute('data-theme', saved);
}
function toggleTheme() {
  const cur = document.documentElement.getAttribute('data-theme');
  const next = cur === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('aurelius_theme', next);
}

// ── Sidebar ───────────────────────────────────────────
let sidebarOpen = true;
function toggleSidebar() {
  sidebarOpen = !sidebarOpen;
  els.sidebar.classList.toggle('collapsed', !sidebarOpen);
}
function toggleMobileSidebar() {
  els.sidebar.classList.toggle('mobile-open');
}

// ── Bind Events ───────────────────────────────────────
function bindEvents() {
  // Textarea
  els.input.addEventListener('input', autoResize);
  els.input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  // Buttons
  els.sendBtn.addEventListener('click', () => sendMessage());
  els.newChatBtn.addEventListener('click', () => startNewSession(true));
  els.clearBtn.addEventListener('click', clearChat);
  els.exportBtn.addEventListener('click', exportChat);
  els.themeToggle.addEventListener('click', toggleTheme);
  els.sidebarToggle.addEventListener('click', toggleSidebar);
  els.mobileMenu.addEventListener('click', toggleMobileSidebar);
  els.systemBtn.addEventListener('click', () => openModal('systemModal'));
  els.tempToggle.addEventListener('click', () => openModal('tempModal'));

  els.streamToggle.addEventListener('click', () => {
    state.streaming = !state.streaming;
    localStorage.setItem('aurelius_stream', state.streaming);
    els.streamLabel.textContent = `Stream ${state.streaming ? 'ON' : 'OFF'}`;
    els.streamToggle.classList.toggle('active', state.streaming);
    toast(`Streaming ${state.streaming ? 'enabled' : 'disabled'}`);
  });

  els.memoryBtn.addEventListener('click', () => {
    state.memory = !state.memory;
    localStorage.setItem('aurelius_memory', state.memory);
    els.memoryLabel.textContent = `Memory ${state.memory ? 'ON' : 'OFF'}`;
    els.memoryBtn.classList.toggle('active', state.memory);
    toast(`Memory ${state.memory ? 'on — full history sent' : 'off — single turn only'}`);
  });

  els.modelSelect.addEventListener('change', () => {
    state.model = els.modelSelect.value;
    localStorage.setItem('aurelius_model', state.model);
    els.modelBadge.textContent = state.model;
    toast(`Model: ${state.model}`);
  });

  // Close modals on backdrop click
  document.querySelectorAll('.modal-backdrop').forEach(bd => {
    bd.addEventListener('click', e => {
      if (e.target === bd) bd.classList.remove('open');
    });
  });

  // Keyboard shortcuts
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') document.querySelectorAll('.modal-backdrop.open').forEach(m => m.classList.remove('open'));
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') { e.preventDefault(); startNewSession(true); }
    if ((e.ctrlKey || e.metaKey) && e.key === 'e') { e.preventDefault(); exportChat(); }
  });
}

// ── Cursor blink CSS ──────────────────────────────────
const style = document.createElement('style');
style.textContent = `.cursor-blink { animation: cur 0.8s step-end infinite; } @keyframes cur { 50% { opacity: 0; } }`;
document.head.appendChild(style);

// ── Boot ──────────────────────────────────────────────
init();