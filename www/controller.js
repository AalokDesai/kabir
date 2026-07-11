// ── Voice input ───────────────────────────────────────────────────────────────
function startListening() {
  eel.start_voice_input()();
}

// ── Arc reactor greeting ──────────────────────────────────────────────────────
function speakGreeting() {
  if (typeof eel !== 'undefined' && eel.speak_greeting) {
    eel.speak_greeting()();
  }
}

// ── Text input ────────────────────────────────────────────────────────────────
function sendTextCmd() {
  const input = document.getElementById('text-input');
  const text = input.value.trim();
  if (text) {
    input.value = '';
    hideCommandSuggestions();
    eel.handle_text_input(text)();
  }
}

function sendCmd(cmd) {
  // Used by quick command cards — switch to chat panel and send
  showPanel('chat');
  hideCommandSuggestions();
  if (typeof eel !== 'undefined' && eel.handle_text_input) {
    eel.handle_text_input(cmd)();
  }
}

// ── Enter key on text input ───────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const input = document.getElementById('text-input');
  if (input) {
    input.addEventListener('keydown', (e) => {
      if (handleSuggestionKeys(e)) return;
      if (e.key === 'Enter') sendTextCmd();
    });
    input.addEventListener('input', renderCommandSuggestions);
    input.addEventListener('focus', renderCommandSuggestions);
  }
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.chat-input-wrap')) hideCommandSuggestions();
  });
  const arcBtn = document.getElementById('arc-display-btn');
  if (arcBtn) {
    arcBtn.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); speakGreeting(); }
    });
  }
  const fileQuery = document.getElementById('file-query');
  if (fileQuery) {
    fileQuery.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') searchExplorerFiles();
    });
  }
  const fileRoot = document.getElementById('file-root');
  if (fileRoot) {
    fileRoot.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') searchExplorerFiles();
    });
  }
  const memoryQuery = document.getElementById('memory-query');
  if (memoryQuery) {
    memoryQuery.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') searchMemoryPanel();
    });
  }
  const notificationTitle = document.getElementById('notification-title');
  if (notificationTitle) {
    notificationTitle.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') addManualNotification();
    });
  }
  const notificationDetail = document.getElementById('notification-detail');
  if (notificationDetail) {
    notificationDetail.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') addManualNotification();
    });
  }
  ['contact-name', 'contact-phone', 'contact-email', 'contact-aliases'].forEach((id) => {
    const field = document.getElementById(id);
    if (field) {
      field.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') saveContactForm();
      });
    }
  });
  loadNotifications();
  loadContactsPanel();
  loadProfileForm();
  loadHistoryPanel();
  loadRecentChat();
  loadSettingsPanel();
  loadCommandSuggestions();
  startBackendHealthMonitor();
});

function setValue(id, value) {
  const el = document.getElementById(id);
  if (el) el.value = value || '';
}

function getValue(id) {
  const el = document.getElementById(id);
  return el ? el.value.trim() : '';
}

function escapeHtml(value) {
  return String(value || '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;',
  }[char]));
}

function formatFileSize(bytes) {
  const size = Number(bytes || 0);
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  if (size < 1024 * 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`;
  return `${(size / 1024 / 1024 / 1024).toFixed(1)} GB`;
}

function formatHistoryTime(value) {
  if (!value) return '';
  const date = new Date(String(value).replace(' ', 'T'));
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString([], {
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).toUpperCase();
}

function jsString(value) {
  return JSON.stringify(String(value || ''));
}

const NOTIFICATION_STORAGE_KEY = 'kabir.notifications.v1';
const FALLBACK_COMMAND_SUGGESTIONS = [
  'what is the time',
  'what is the date',
  'weather in Mumbai',
  'top news',
  'open youtube',
  'open google',
  'send email',
  'send message',
  'play music',
  'take screenshot',
  'search files',
  'show command history',
  'setup wireless phone',
  'volume up',
  'shutdown',
];
let notifications = [];
let contacts = [];
let commandSuggestions = FALLBACK_COMMAND_SUGGESTIONS.slice();
let activeSuggestionIndex = -1;

function normalizeSuggestionList(items) {
  const seen = new Set();
  return (items || [])
    .map((item) => String(item || '').trim())
    .filter(Boolean)
    .filter((item) => {
      const key = item.toLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .slice(0, 80);
}

async function loadCommandSuggestions() {
  commandSuggestions = normalizeSuggestionList(FALLBACK_COMMAND_SUGGESTIONS);
  if (typeof eel === 'undefined' || !eel.get_skill_suggestions) return;

  try {
    const response = await eel.get_skill_suggestions()();
    if (response && response.success) {
      commandSuggestions = normalizeSuggestionList([
        ...(response.suggestions || []),
        ...FALLBACK_COMMAND_SUGGESTIONS,
      ]);
    }
  } catch (error) {
    commandSuggestions = normalizeSuggestionList(FALLBACK_COMMAND_SUGGESTIONS);
  }
}

function scoreCommandSuggestion(command, query) {
  const text = command.toLowerCase();
  const clean = query.toLowerCase();
  const words = clean.split(/\s+/).filter(Boolean);
  if (!words.length) return 1;
  if (text === clean) return 100;
  if (text.startsWith(clean)) return 80;
  if (words.every((word) => text.includes(word))) return 50;
  return 0;
}

function getFilteredCommandSuggestions(query) {
  const clean = String(query || '').trim();
  const ranked = commandSuggestions
    .map((command) => ({ command, score: scoreCommandSuggestion(command, clean) }))
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score || a.command.length - b.command.length);
  return ranked.slice(0, clean ? 6 : 5).map((item) => item.command);
}

function hideCommandSuggestions() {
  const box = document.getElementById('command-suggestions');
  if (box) {
    box.style.display = 'none';
    box.innerHTML = '';
  }
  activeSuggestionIndex = -1;
}

function applyCommandSuggestion(command, sendNow = false) {
  const input = document.getElementById('text-input');
  if (!input) return;
  input.value = command;
  hideCommandSuggestions();
  input.focus();
  if (sendNow) sendTextCmd();
}

function renderCommandSuggestions() {
  const input = document.getElementById('text-input');
  const box = document.getElementById('command-suggestions');
  if (!input || !box || document.activeElement !== input) return;

  const suggestions = getFilteredCommandSuggestions(input.value);
  if (!suggestions.length) {
    hideCommandSuggestions();
    return;
  }

  activeSuggestionIndex = Math.min(activeSuggestionIndex, suggestions.length - 1);
  box.innerHTML = suggestions.map((command, index) => `
    <button type="button" class="command-suggestion ${index === activeSuggestionIndex ? 'active' : ''}"
            onmousedown="event.preventDefault(); applyCommandSuggestion(${jsString(command)}, true)">
      <i class="fas fa-bolt"></i>
      <span>${escapeHtml(command)}</span>
    </button>
  `).join('');
  box.style.display = 'flex';
}

function moveCommandSuggestion(delta) {
  const box = document.getElementById('command-suggestions');
  if (!box || box.style.display === 'none') return false;
  const count = box.querySelectorAll('.command-suggestion').length;
  if (!count) return false;
  activeSuggestionIndex = (activeSuggestionIndex + delta + count) % count;
  renderCommandSuggestions();
  return true;
}

function handleSuggestionKeys(event) {
  const box = document.getElementById('command-suggestions');
  const visible = box && box.style.display !== 'none';
  if (event.key === 'ArrowDown') {
    event.preventDefault();
    if (!visible) renderCommandSuggestions();
    moveCommandSuggestion(1);
    return true;
  }
  if (event.key === 'ArrowUp') {
    event.preventDefault();
    if (!visible) renderCommandSuggestions();
    moveCommandSuggestion(-1);
    return true;
  }
  if ((event.key === 'Tab' || event.key === 'Enter') && visible && activeSuggestionIndex >= 0) {
    const selected = box.querySelectorAll('.command-suggestion')[activeSuggestionIndex];
    if (selected) {
      event.preventDefault();
      applyCommandSuggestion(selected.textContent.trim(), event.key === 'Enter');
      return true;
    }
  }
  if (event.key === 'Escape') {
    hideCommandSuggestions();
    return true;
  }
  return false;
}

function notificationIcon(type) {
  if (type === 'calendar') return 'fa-calendar-check';
  if (type === 'email') return 'fa-envelope';
  if (type === 'system') return 'fa-desktop';
  if (type === 'error') return 'fa-triangle-exclamation';
  return 'fa-bell';
}

function notificationLabel(type) {
  if (type === 'calendar') return 'CALENDAR';
  if (type === 'email') return 'EMAIL';
  if (type === 'system') return 'SYSTEM';
  if (type === 'error') return 'ERROR';
  return 'REMINDER';
}

function loadNotifications() {
  try {
    const stored = JSON.parse(localStorage.getItem(NOTIFICATION_STORAGE_KEY) || '[]');
    notifications = Array.isArray(stored) ? stored : [];
  } catch (error) {
    notifications = [];
  }
  updateNotificationBadge();
}

function saveNotifications() {
  localStorage.setItem(NOTIFICATION_STORAGE_KEY, JSON.stringify(notifications));
  updateNotificationBadge();
}

function formatNotificationTime(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString([], {
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).toUpperCase();
}

function updateNotificationBadge() {
  const unread = notifications.filter((item) => !item.read).length;
  const badge = document.getElementById('notification-badge');
  if (badge) {
    badge.textContent = unread > 99 ? '99+' : String(unread);
    badge.style.display = unread ? 'inline-flex' : 'none';
  }

  const unreadCount = document.getElementById('notification-unread-count');
  const reminderCount = document.getElementById('notification-reminder-count');
  const calendarCount = document.getElementById('notification-calendar-count');
  const emailCount = document.getElementById('notification-email-count');
  if (unreadCount) unreadCount.textContent = String(unread);
  if (reminderCount) reminderCount.textContent = String(notifications.filter((item) => item.type === 'reminder').length);
  if (calendarCount) calendarCount.textContent = String(notifications.filter((item) => item.type === 'calendar').length);
  if (emailCount) emailCount.textContent = String(notifications.filter((item) => item.type === 'email').length);
}

function renderNotifications() {
  updateNotificationBadge();
  const box = document.getElementById('notification-list');
  if (!box) return;

  if (!notifications.length) {
    box.innerHTML = `
      <div class="notification-empty">
        <i class="fas fa-bell-slash"></i>
        <span>NO NOTIFICATIONS RECORDED</span>
      </div>
    `;
    return;
  }

  box.innerHTML = notifications.map((item) => `
    <div class="notification-item ${item.read ? 'read' : 'unread'}">
      <div class="notification-icon ${escapeHtml(item.type)}">
        <i class="fas ${notificationIcon(item.type)}"></i>
      </div>
      <div class="notification-main">
        <div class="notification-meta">
          <span>${notificationLabel(item.type)}</span>
          <span>${escapeHtml(formatNotificationTime(item.created_at))}</span>
        </div>
        <div class="notification-title">${escapeHtml(item.title)}</div>
        ${item.detail ? `<div class="notification-detail">${escapeHtml(item.detail)}</div>` : ''}
      </div>
      <div class="notification-item-actions">
        <button title="${item.read ? 'Mark unread' : 'Mark read'}" onclick="toggleNotificationRead('${item.id}')">
          <i class="fas ${item.read ? 'fa-circle' : 'fa-check'}"></i>
        </button>
        <button title="Delete notification" onclick="deleteNotification('${item.id}')">
          <i class="fas fa-xmark"></i>
        </button>
      </div>
    </div>
  `).join('');
}

function addNotification(payload) {
  const title = String(payload?.title || '').trim();
  if (!title) return null;

  const type = ['reminder', 'calendar', 'email', 'system', 'error'].includes(payload?.type) ? payload.type : 'reminder';
  const item = {
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    type,
    title,
    detail: String(payload?.detail || '').trim(),
    created_at: payload?.created_at || new Date().toISOString(),
    read: Boolean(payload?.read),
  };

  notifications = [item, ...notifications].slice(0, 100);
  saveNotifications();
  renderNotifications();
  return item;
}

function pushNotification(type, title, detail) {
  return addNotification({ type, title, detail });
}

if (typeof eel !== 'undefined') {
  eel.expose(pushNotification);
}

function addManualNotification() {
  const type = getValue('notification-type') || 'reminder';
  const title = getValue('notification-title');
  const detail = getValue('notification-detail');
  if (!title) return;

  addNotification({ type, title, detail });
  setValue('notification-title', '');
  setValue('notification-detail', '');
}

function toggleNotificationRead(id) {
  notifications = notifications.map((item) => (
    item.id === id ? { ...item, read: !item.read } : item
  ));
  saveNotifications();
  renderNotifications();
}

function markAllNotificationsRead() {
  notifications = notifications.map((item) => ({ ...item, read: true }));
  saveNotifications();
  renderNotifications();
}

function deleteNotification(id) {
  notifications = notifications.filter((item) => item.id !== id);
  saveNotifications();
  renderNotifications();
}

function clearNotifications() {
  notifications = [];
  saveNotifications();
  renderNotifications();
}

function renderHistoryCommands(commands) {
  const box = document.getElementById('history-commands');
  if (!box) return;

  if (!commands.length) {
    box.innerHTML = '<div class="history-empty">NO COMMANDS RECORDED</div>';
    return;
  }

  box.innerHTML = commands.map((item) => `
    <div class="history-item">
      <div class="history-item-main">
        <div class="history-text">${escapeHtml(item.command)}</div>
        <div class="history-meta">
          <span>${escapeHtml(item.source || 'UNKNOWN')}</span>
          <span>${escapeHtml(formatHistoryTime(item.created_at))}</span>
        </div>
      </div>
      <button title="Replay command" onclick="replayHistoryCommand(${Number(item.id)})">
        <i class="fas fa-play"></i>
      </button>
    </div>
  `).join('');
}

function renderHistoryMessages(messages) {
  const box = document.getElementById('history-messages');
  if (!box) return;

  if (!messages.length) {
    box.innerHTML = '<div class="history-empty">NO MESSAGES RECORDED</div>';
    return;
  }

  box.innerHTML = messages.map((item) => `
    <div class="history-message ${item.speaker === 'You' ? 'from-user' : 'from-kabir'}">
      <div class="history-meta">
        <span>${escapeHtml(item.speaker)}</span>
        <span>${escapeHtml(formatHistoryTime(item.created_at))}</span>
      </div>
      <div class="history-text">${escapeHtml(item.message)}</div>
    </div>
  `).join('');
}

function renderFrequentCommands(commands) {
  const box = document.getElementById('history-frequent');
  if (!box) return;

  if (!commands.length) {
    box.innerHTML = '<div class="history-empty">LEARNING COMMANDS</div>';
    return;
  }

  box.innerHTML = commands.map((item) => `
    <div class="history-frequent-item" onclick='replayHistoryText(${escapeHtml(jsString(item.command))})'>
      <div class="history-text">${escapeHtml(item.command)}</div>
      <div class="history-meta">
        <span>${Number(item.uses || 0)} USES</span>
        <span>${escapeHtml(formatHistoryTime(item.last_used))}</span>
      </div>
    </div>
  `).join('');
}

function renderMemoryResults(results) {
  const box = document.getElementById('memory-results');
  if (!box) return;

  if (!results.length) {
    box.innerHTML = '<div class="history-empty">NO MEMORY MATCHES</div>';
    return;
  }

  box.innerHTML = results.map((item) => {
    const isCommand = item.kind === 'command';
    return `
      <div class="memory-result">
        <div class="history-meta">
          <span>${escapeHtml(item.title || item.kind || 'MEMORY')}</span>
          <span>${escapeHtml(formatHistoryTime(item.created_at))}</span>
          <span>${escapeHtml(item.source || '')}</span>
        </div>
        <div class="history-text">${escapeHtml(item.body)}</div>
        ${item.url ? `<div class="history-meta">${escapeHtml(item.url)}</div>` : ''}
        ${isCommand ? `
          <button title="Replay command" onclick="replayHistoryCommand(${Number(item.id)})">
            <i class="fas fa-play"></i>
          </button>
        ` : ''}
      </div>
    `;
  }).join('');
}

async function loadHistoryPanel() {
  if (typeof eel === 'undefined' || !eel.get_history) return;
  const response = await eel.get_history(80)();
  if (!response.success) {
    const box = document.getElementById('history-commands');
    if (box) box.innerHTML = `<div class="history-empty">${escapeHtml(response.message || 'HISTORY LOAD FAILED')}</div>`;
    return;
  }
  renderHistoryCommands(response.commands || []);
  renderHistoryMessages(response.messages || []);
  renderFrequentCommands(response.frequent || []);
}

async function loadRecentChat() {
  if (typeof eel === 'undefined' || !eel.get_recent_chat) return;
  const response = await eel.get_recent_chat(40)();
  if (response && response.success && response.messages && response.messages.length) {
    setChatMessages(response.messages);
  }
}

async function clearChatHistory() {
  if (typeof eel === 'undefined' || !eel.clear_chat_history) return;
  const response = await eel.clear_chat_history()();
  if (response.success) {
    resetChatBox();
    addMessage('Kabir', response.message || 'Chat history cleared.');
    await loadHistoryPanel();
  } else {
    addMessage('Kabir', response.message || 'Clear chat failed.');
  }
}

async function clearAllHistory() {
  if (typeof eel === 'undefined' || !eel.clear_all_history) return;
  const response = await eel.clear_all_history()();
  if (response.success) {
    resetChatBox();
    addMessage('Kabir', response.message || 'History cleared.');
    renderMemoryResults([]);
    await loadHistoryPanel();
  } else {
    addMessage('Kabir', response.message || 'Clear history failed.');
  }
}

async function searchMemoryPanel() {
  const input = document.getElementById('memory-query');
  const query = input ? input.value.trim() : '';
  if (!query) {
    renderMemoryResults([]);
    return;
  }
  if (typeof eel === 'undefined' || !eel.search_memory) return;
  const response = await eel.search_memory(query, 30)();
  if (!response.success) {
    const box = document.getElementById('memory-results');
    if (box) box.innerHTML = `<div class="history-empty">${escapeHtml(response.message || 'MEMORY SEARCH FAILED')}</div>`;
    return;
  }
  renderMemoryResults(response.results || []);
}

async function replayHistoryCommand(id) {
  if (typeof eel === 'undefined' || !eel.replay_history_command) return;
  await eel.replay_history_command(id)();
  showPanel('chat');
}

async function replayHistoryText(command) {
  if (typeof eel === 'undefined' || !eel.replay_history_text) return;
  await eel.replay_history_text(command)();
  showPanel('chat');
}

function setSettingsStatus(text, good = true) {
  const status = document.getElementById('settings-status');
  if (!status) return;
  status.textContent = String(text || 'LOCAL STORE').toUpperCase();
  status.classList.toggle('good', Boolean(good));
}

function applyTheme(theme) {
  document.body.classList.toggle('theme-light', theme === 'light');
}

function renderSettingsSummary(settings) {
  const history = document.getElementById('settings-history-summary');
  const roots = document.getElementById('settings-roots-summary');
  if (history) {
    history.textContent = `${Number(settings.history_max_items || 5000)} items / ${Number(settings.history_retention_days || 180)} days`;
  }
  if (roots) {
    const count = Array.isArray(settings.safe_file_roots) ? settings.safe_file_roots.length : 0;
    roots.textContent = count ? `${count} extra folder${count === 1 ? '' : 's'}` : 'Default folders';
  }
}

function fillSettingsForm(settings) {
  setValue('settings-default-city', settings.default_city || 'Mumbai');
  setValue('settings-music-platform', settings.preferred_music_platform || 'youtube');
  setValue('settings-voice-engine', settings.voice_engine || 'neural');
  setValue('settings-voice-rate', settings.voice_rate || '+20%');
  setValue('settings-theme', settings.theme || 'dark');
  const wakeEnabled = document.getElementById('settings-wake-enabled');
  if (wakeEnabled) wakeEnabled.checked = Boolean(settings.wake_word_enabled);
  setValue('settings-wake-phrase', settings.wake_word_phrase || 'Hey Kabir');
  setValue('settings-wake-keyword', settings.wake_word_builtin_keyword || 'kabir');
  setValue('settings-wake-path', settings.wake_word_keyword_path || '');
  setValue('settings-wake-sensitivity', settings.wake_word_sensitivity || '0.65');
  setValue('settings-history-max', settings.history_max_items || 5000);
  setValue('settings-history-days', settings.history_retention_days || 180);
  setValue('settings-safe-roots', Array.isArray(settings.safe_file_roots) ? settings.safe_file_roots.join('\n') : '');
  applyTheme(settings.theme || 'dark');
  renderSettingsSummary(settings);
}

async function loadSettingsPanel() {
  if (typeof eel === 'undefined' || !eel.get_app_settings) return;
  const response = await eel.get_app_settings()();
  if (response.success) {
    fillSettingsForm(response.settings || {});
    setSettingsStatus('local store', true);
  } else {
    setSettingsStatus(response.message || 'settings load failed', false);
  }
}

async function saveSettingsForm() {
  if (typeof eel === 'undefined' || !eel.save_app_settings) return;
  const settings = {
    default_city: getValue('settings-default-city'),
    preferred_music_platform: getValue('settings-music-platform') || 'youtube',
    voice_engine: getValue('settings-voice-engine') || 'neural',
    voice_rate: getValue('settings-voice-rate') || '+20%',
    theme: getValue('settings-theme') || 'dark',
    wake_word_enabled: Boolean(document.getElementById('settings-wake-enabled')?.checked),
    wake_word_phrase: getValue('settings-wake-phrase') || 'Hey Kabir',
    wake_word_builtin_keyword: getValue('settings-wake-keyword') || 'kabir',
    wake_word_keyword_path: getValue('settings-wake-path'),
    wake_word_sensitivity: getValue('settings-wake-sensitivity') || '0.65',
    history_max_items: Number(getValue('settings-history-max') || 5000),
    history_retention_days: Number(getValue('settings-history-days') || 180),
    safe_file_roots: getValue('settings-safe-roots').split(/\r?\n/).map((item) => item.trim()).filter(Boolean),
  };
  const response = await eel.save_app_settings(settings)();
  if (response.success) {
    fillSettingsForm(response.settings || settings);
    setSettingsStatus(response.message || 'settings saved', true);
    addMessage('Kabir', response.message || 'Settings saved.');
    await loadHistoryPanel();
  } else {
    setSettingsStatus(response.message || 'settings save failed', false);
    addMessage('Kabir', response.message || 'Settings save failed.');
  }
}

function setFileSearchStatus(text, good = false) {
  const status = document.getElementById('file-search-status');
  if (!status) return;
  status.textContent = String(text || 'READY').toUpperCase();
  status.classList.toggle('good', Boolean(good));
}

function renderFileResults(results) {
  const box = document.getElementById('file-results');
  if (!box) return;

  if (!results.length) {
    box.innerHTML = `
      <div class="file-empty">
        <i class="fas fa-circle-info"></i>
        <span>NO MATCHING FILES FOUND</span>
      </div>
    `;
    return;
  }

  box.innerHTML = results.map((file, index) => `
    <div class="file-result">
      <div class="file-result-icon"><i class="fas fa-file"></i></div>
      <div class="file-result-main">
        <div class="file-result-name">${escapeHtml(file.name)}</div>
        <div class="file-result-path">${escapeHtml(file.path)}</div>
        <div class="file-result-meta">
          <span>MATCH ${escapeHtml(file.match || 'NAME')}</span>
          <span>${escapeHtml(file.type)}</span>
          <span>${formatFileSize(file.size)}</span>
          <span>${escapeHtml(file.modified)}</span>
        </div>
      </div>
      <div class="file-actions">
        <button title="Open file" onclick="openExplorerFile(${index})"><i class="fas fa-arrow-up-right-from-square"></i></button>
        <button title="Show in Explorer" onclick="revealExplorerFile(${index})"><i class="fas fa-folder-open"></i></button>
      </div>
    </div>
  `).join('');
}

let latestFileResults = [];

async function searchExplorerFiles() {
  if (typeof eel === 'undefined' || !eel.search_files) return;

  const query = getValue('file-query');
  const root = getValue('file-root');
  if (!query) {
    setFileSearchStatus('ENTER QUERY');
    renderFileResults([]);
    return;
  }

  setFileSearchStatus('SEARCHING');
  const response = await eel.search_files(query, root || null, 80)();
  latestFileResults = response.results || [];
  renderFileResults(latestFileResults);
  setFileSearchStatus(response.message || 'DONE', Boolean(response.success));
}

function showFileSearchResults(query, response) {
  const queryInput = document.getElementById('file-query');
  if (queryInput) queryInput.value = query || '';

  latestFileResults = (response && response.results) || [];
  renderFileResults(latestFileResults);
  setFileSearchStatus((response && response.message) || 'DONE', Boolean(response && response.success));
  showPanel('files');
}

if (typeof eel !== 'undefined') {
  eel.expose(showFileSearchResults);
}

async function openExplorerFile(index) {
  const file = latestFileResults[index];
  if (!file || typeof eel === 'undefined' || !eel.open_file_path) return;
  const response = await eel.open_file_path(file.path)();
  setFileSearchStatus(response.message || 'OPENED', Boolean(response.success));
}

async function revealExplorerFile(index) {
  const file = latestFileResults[index];
  if (!file || typeof eel === 'undefined' || !eel.reveal_file_path) return;
  const response = await eel.reveal_file_path(file.path)();
  setFileSearchStatus(response.message || 'REVEALED', Boolean(response.success));
}

function renderProfileStatus(status) {
  const statusEl = document.getElementById('profile-status');
  if (statusEl) {
    statusEl.textContent = status.configured ? 'CONFIGURED' : 'NOT CONFIGURED';
    statusEl.classList.toggle('good', Boolean(status.configured));
  }

  const summaryEmail = document.getElementById('summary-email');
  const summaryProvider = document.getElementById('summary-provider');
  const summarySmtp = document.getElementById('summary-smtp');
  if (summaryEmail) summaryEmail.textContent = status.email || '-';
  if (summaryProvider) summaryProvider.textContent = (status.provider || 'auto').toUpperCase();
  if (summarySmtp) {
    summarySmtp.textContent = status.smtp_host ? `${status.smtp_host}:${status.smtp_port}` : '-';
  }
}

function updateProviderHint() {
  const provider = getValue('profile-provider');
  const hint = document.getElementById('provider-hint');
  if (!hint) return;

  if (provider === 'gmail') {
    hint.textContent = 'Use your Gmail address with a Google app password. Normal Gmail account passwords usually will not work.';
  } else if (provider === 'zimbra') {
    hint.textContent = 'For Zimbra, enter the SMTP host from your organization, often mail.yourdomain.com, with port 587 and STARTTLS.';
  } else if (provider === 'custom') {
    hint.textContent = 'Use Custom SMTP when your provider gives a specific host, port, and TLS setting.';
  } else {
    hint.textContent = 'Auto detect handles Gmail and common providers. Unknown domains use mail.yourdomain.com unless you enter SMTP host.';
  }
}

async function loadProfileForm() {
  if (typeof eel === 'undefined' || !eel.get_mail_profile) return;

  const profile = await eel.get_mail_profile()();
  setValue('profile-name', profile.name);
  setValue('profile-age', profile.age);
  setValue('profile-email', profile.email);
  setValue('profile-smtp-user', profile.smtp_user);
  setValue('profile-password', '');
  setValue('profile-provider', profile.provider || 'auto');
  setValue('profile-smtp-host', profile.smtp_host);
  setValue('profile-smtp-port', profile.smtp_port || 587);
  const tls = document.getElementById('profile-use-tls');
  if (tls) tls.checked = profile.use_tls !== false;

  updateProviderHint();
  if (eel.get_mail_profile_status) {
    renderProfileStatus(await eel.get_mail_profile_status()());
  }
}

async function saveProfileForm() {
  if (typeof eel === 'undefined' || !eel.save_profile) return;

  const profile = {
    name: getValue('profile-name'),
    age: getValue('profile-age'),
    email: getValue('profile-email'),
    smtp_user: getValue('profile-smtp-user'),
    password: getValue('profile-password'),
    provider: getValue('profile-provider') || 'auto',
    smtp_host: getValue('profile-smtp-host'),
    smtp_port: Number(getValue('profile-smtp-port') || 587),
    use_tls: Boolean(document.getElementById('profile-use-tls')?.checked),
  };

  const response = await eel.save_profile(profile)();
  if (response.success) {
    addMessage('Kabir', response.message);
    if (eel.get_mail_profile_status) {
      renderProfileStatus(await eel.get_mail_profile_status()());
    }
  } else {
    addMessage('Kabir', response.message || 'Profile save failed.');
  }
}

function setContactsStatus(text, good = true) {
  const status = document.getElementById('contacts-status');
  if (!status) return;
  status.textContent = String(text || '').toUpperCase();
  status.classList.toggle('good', Boolean(good));
}

function renderContacts() {
  const box = document.getElementById('contacts-list');
  if (!box) return;

  if (!contacts.length) {
    box.innerHTML = '<div class="history-empty">NO CONTACTS SAVED</div>';
    return;
  }

  box.innerHTML = contacts.map((contact, index) => `
    <div class="contact-item">
      <div class="contact-avatar"><i class="fas fa-user"></i></div>
      <div class="contact-main">
        <div class="contact-name">${escapeHtml(contact.name)}</div>
        <div class="contact-detail">
          ${contact.phone ? `<span><i class="fas fa-phone"></i> ${escapeHtml(contact.phone)}</span>` : ''}
          ${contact.email ? `<span><i class="fas fa-envelope"></i> ${escapeHtml(contact.email)}</span>` : ''}
        </div>
        <div class="contact-aliases">${escapeHtml((contact.aliases || []).join(', '))}</div>
      </div>
      <div class="contact-actions">
        <button title="Edit contact" onclick="editContact(${index})"><i class="fas fa-pen"></i></button>
        <button title="Delete contact" onclick="deleteContact(${index})"><i class="fas fa-trash"></i></button>
      </div>
    </div>
  `).join('');
}

async function loadContactsPanel() {
  if (typeof eel === 'undefined' || !eel.get_contacts) return;
  const response = await eel.get_contacts()();
  if (response.success) {
    contacts = response.contacts || [];
    renderContacts();
    setContactsStatus('encrypted local store', true);
  } else {
    contacts = [];
    renderContacts();
    setContactsStatus(response.message || 'contacts load failed', false);
  }
}

function resetContactForm() {
  setValue('contact-id', '');
  setValue('contact-name', '');
  setValue('contact-phone', '');
  setValue('contact-email', '');
  setValue('contact-aliases', '');
  setContactsStatus('new contact', true);
}

function editContact(index) {
  const contact = contacts[index];
  if (!contact) return;
  setValue('contact-id', contact.id);
  setValue('contact-name', contact.name);
  setValue('contact-phone', contact.phone);
  setValue('contact-email', contact.email);
  setValue('contact-aliases', (contact.aliases || []).join(', '));
  setContactsStatus('editing contact', true);
}

async function saveContactForm() {
  if (typeof eel === 'undefined' || !eel.save_contact) return;
  const contact = {
    id: getValue('contact-id'),
    name: getValue('contact-name'),
    phone: getValue('contact-phone'),
    email: getValue('contact-email'),
    aliases: getValue('contact-aliases').split(',').map((item) => item.trim()).filter(Boolean),
  };
  const response = await eel.save_contact(contact)();
  if (response.success) {
    resetContactForm();
    await loadContactsPanel();
    addMessage('Kabir', response.message);
  } else {
    setContactsStatus(response.message || 'contact save failed', false);
    addMessage('Kabir', response.message || 'Contact save failed.');
  }
}

async function deleteContact(index) {
  if (typeof eel === 'undefined' || !eel.delete_contact) return;
  const contact = contacts[index];
  if (!contact) return;
  const response = await eel.delete_contact(contact.id)();
  if (response.success) {
    await loadContactsPanel();
    addMessage('Kabir', response.message);
  } else {
    setContactsStatus(response.message || 'contact delete failed', false);
  }
}

let backendWasOffline = false;
let backendHealthTimer = null;

function setBackendBanner(online, message = '') {
  const banner = document.getElementById('backend-banner');
  const text = document.getElementById('backend-banner-text');
  const status = document.getElementById('sys-status');
  if (banner) banner.style.display = online ? 'none' : 'flex';
  if (text) text.textContent = String(message || 'BACKEND DISCONNECTED').toUpperCase();
  if (status) {
    status.textContent = online ? 'ONLINE' : 'OFFLINE';
    status.classList.toggle('online', Boolean(online));
  }
}

async function reloadBackendState() {
  await Promise.allSettled([
    loadHistoryPanel(),
    loadRecentChat(),
    loadContactsPanel(),
    loadProfileForm(),
    loadSettingsPanel(),
    loadLogsPanel(),
  ]);
  renderNotifications();
}

async function checkBackendHealth() {
  if (typeof eel === 'undefined' || !eel.health_check) {
    backendWasOffline = true;
    setBackendBanner(false, 'backend unavailable');
    return;
  }

  try {
    const response = await eel.health_check()();
    if (!response || !response.success) {
      throw new Error('health check failed');
    }
    setBackendBanner(true);
    if (response.powerAction && response.powerAction.active && typeof updateShutdownCountdown === 'function') {
      updateShutdownCountdown(response.powerAction.action, response.powerAction.seconds, true);
    }
    if (backendWasOffline) {
      backendWasOffline = false;
      await reloadBackendState();
      addNotification({ type: 'system', title: 'Backend reconnected', detail: 'Kabir state was refreshed.' });
    }
  } catch (error) {
    backendWasOffline = true;
    setBackendBanner(false, 'backend disconnected - retrying');
  }
}

function startBackendHealthMonitor() {
  if (backendHealthTimer) return;
  checkBackendHealth();
  backendHealthTimer = setInterval(checkBackendHealth, 5000);
}

async function cancelScheduledShutdown() {
  if (typeof eel === 'undefined' || !eel.cancel_shutdown) return;
  const response = await eel.cancel_shutdown()();
  addMessage('Kabir', response.message || 'Power action cancelled.');
  if (typeof updateShutdownCountdown === 'function') {
    updateShutdownCountdown('', 0, false);
  }
}

async function loadLogsPanel() {
  const output = document.getElementById('logs-output');
  if (!output) return;
  if (typeof eel === 'undefined' || !eel.get_logs) {
    output.textContent = 'LOG VIEWER UNAVAILABLE';
    return;
  }
  const response = await eel.get_logs(200)();
  if (!response.success) {
    output.textContent = response.message || 'LOG LOAD FAILED';
    return;
  }
  const lines = response.lines || [];
  output.textContent = lines.length ? lines.join('\n') : 'NO LOGS RECORDED YET';
  output.scrollTop = output.scrollHeight;
}
