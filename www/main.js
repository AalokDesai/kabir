// ── Clock & Date ──────────────────────────────────────────────────────────────
function updateClock() {
  const now = new Date();
  const h = String(now.getHours()).padStart(2,'0');
  const m = String(now.getMinutes()).padStart(2,'0');
  const s = String(now.getSeconds()).padStart(2,'0');
  const el = document.getElementById('clock');
  if (el) el.textContent = `${h}:${m}:${s}`;

  const days = ['SUN','MON','TUE','WED','THU','FRI','SAT'];
  const months = ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'];
  const d = document.getElementById('date-disp');
  if (d) d.textContent = `${days[now.getDay()]} ${now.getDate()} ${months[now.getMonth()]}`;
}
setInterval(updateClock, 1000);
updateClock();

// ── Panel switching ───────────────────────────────────────────────────────────
function showPanel(name) {
  document.getElementById('panel-chat').style.display = name === 'chat' ? 'flex' : 'none';
  document.getElementById('panel-cmds').style.display = name === 'cmds' ? 'flex' : 'none';
  document.getElementById('panel-files').style.display = name === 'files' ? 'flex' : 'none';
  document.getElementById('panel-history').style.display = name === 'history' ? 'flex' : 'none';
  document.getElementById('panel-contacts').style.display = name === 'contacts' ? 'flex' : 'none';
  document.getElementById('panel-notifications').style.display = name === 'notifications' ? 'flex' : 'none';
  document.getElementById('panel-settings').style.display = name === 'settings' ? 'flex' : 'none';
  document.getElementById('panel-logs').style.display = name === 'logs' ? 'flex' : 'none';
  document.getElementById('panel-profile').style.display = name === 'profile' ? 'flex' : 'none';
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  document.getElementById('nav-' + name).classList.add('active');
  if (name === 'history') loadHistoryPanel();
  if (name === 'contacts') loadContactsPanel();
  if (name === 'notifications') renderNotifications();
  if (name === 'settings') loadSettingsPanel();
  if (name === 'logs') loadLogsPanel();
}

// ── Add message ───────────────────────────────────────────────────────────────
function addMessage(sender, text) {
  const box = document.getElementById('chat-box');
  if (!box) return;
  const isUser = sender === 'You';
  const div = document.createElement('div');
  div.className = `chat-msg ${isUser ? 'user-msg' : 'kabir-msg'}`;
  div.innerHTML = `<span class="msg-tag">${escapeChatHtml(sender.toUpperCase())}</span><p>${escapeChatHtml(text)}</p>`;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;

  // Update last command
  if (isUser) {
    const el = document.getElementById('last-cmd');
    if (el) el.textContent = text.substring(0, 18).toUpperCase();
  }
}

// ── Eel-exposed: Python calls these ──────────────────────────────────────────
function escapeChatHtml(value) {
  return String(value || '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;',
  }[char]));
}

function setChatMessages(messages) {
  const box = document.getElementById('chat-box');
  if (!box || !Array.isArray(messages) || !messages.length) return;

  box.innerHTML = messages.map((item) => {
    const sender = item.speaker === 'You' ? 'You' : 'Kabir';
    const isUser = sender === 'You';
    return `
      <div class="chat-msg ${isUser ? 'user-msg' : 'kabir-msg'}">
        <span class="msg-tag">${escapeChatHtml(sender.toUpperCase())}</span>
        <p>${escapeChatHtml(item.message)}</p>
      </div>
    `;
  }).join('');
  box.scrollTop = box.scrollHeight;
}

function resetChatBox() {
  const box = document.getElementById('chat-box');
  if (!box) return;
  box.innerHTML = `
    <div class="chat-msg kabir-msg">
      <span class="msg-tag">KABIR</span>
      <p>Hello Sir. All systems are online. How may I assist you today?</p>
    </div>
  `;
}

eel.expose(addMessage);

function updateShutdownCountdown(action, seconds, active) {
  const banner = document.getElementById('shutdown-banner');
  const actionEl = document.getElementById('shutdown-action');
  const countEl = document.getElementById('shutdown-countdown');
  if (!banner) return;
  banner.style.display = active ? 'flex' : 'none';
  if (actionEl) actionEl.textContent = String(action || 'shutdown').toUpperCase();
  if (countEl) countEl.textContent = String(seconds || 0);
}
eel.expose(updateShutdownCountdown);

function setStatus(text) {
  const el = document.getElementById('mic-status-bar');
  if (el) el.textContent = text.toUpperCase();
}
eel.expose(setStatus);

const GAUGE_CIRCUMFERENCE = 213.63;

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function formatPercent(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return '--%';
  return `${Math.round(number)}%`;
}

function formatTemp(value) {
  const number = Number(value);
  if (!Number.isFinite(number) || number <= 0) return '--';
  return `${Math.round(number)}C`;
}

function setGauge(name, value) {
  const number = Math.max(0, Math.min(100, Number(value) || 0));
  const arc = document.getElementById(`gauge-${name}`);
  if (arc) {
    const offset = GAUGE_CIRCUMFERENCE - (GAUGE_CIRCUMFERENCE * number / 100);
    arc.style.strokeDashoffset = offset.toFixed(2);
  }

  const wrap = document.querySelector(`[data-stat="${name}"]`);
  if (wrap) {
    wrap.classList.toggle('warn', number >= 75 && number < 90);
    wrap.classList.toggle('critical', number >= 90);
  }
}

function updateStats(stats) {
  if (!stats || !stats.available) {
    setText('telemetry-updated', '--:--:--');
    setText('network-detail', stats && stats.message ? stats.message : 'TELEMETRY OFFLINE');
    return;
  }

  const cpu = stats.cpu || {};
  const gpu = stats.gpu || {};
  const ram = stats.ram || {};
  const disk = stats.disk || {};
  const network = stats.network || {};

  setText('telemetry-updated', stats.updatedAt || '--:--:--');
  setText('cpu-value', formatPercent(cpu.value));
  setText('gpu-value', gpu.available ? formatPercent(gpu.load) : 'N/A');
  setText('ram-value', formatPercent(ram.value));
  setText('disk-value', formatPercent(disk.value));
  setText('network-value', network.downLabel || '--');
  setText('network-detail', `UP ${network.upLabel || '--'} / DOWN ${network.downLabel || '--'}`);
  setText('cpu-temp', formatTemp(cpu.temperature));
  setText('gpu-temp', formatTemp(gpu.temperature));

  setGauge('cpu', cpu.value);
  setGauge('gpu', gpu.available ? gpu.load : 0);
  setGauge('ram', ram.value);
  setGauge('disk', disk.value);

  const netValue = Math.max(0, Math.min(100, Number(network.value) || 0));
  const netArc = document.getElementById('gauge-network');
  if (netArc) {
    const offset = GAUGE_CIRCUMFERENCE - (GAUGE_CIRCUMFERENCE * netValue / 100);
    netArc.style.strokeDashoffset = offset.toFixed(2);
  }
  const netWrap = document.querySelector('.network-gauge');
  if (netWrap) {
    netWrap.classList.toggle('warn', netValue >= 75 && netValue < 90);
    netWrap.classList.toggle('critical', netValue >= 90);
  }
}
eel.expose(updateStats);

function setListening(active) {
  const btn  = document.getElementById('mic-btn');
  const icon = document.getElementById('mic-icon');
  const viz  = document.getElementById('visualizer');
  const arc  = document.getElementById('arc-label');
  const vs   = document.getElementById('voice-status');

  if (active) {
    btn && btn.classList.add('listening');
    icon && icon.setAttribute('class','fas fa-microphone-slash');
    viz && viz.classList.add('active');
    arc && (arc.textContent = 'LISTENING');
    vs  && (vs.textContent  = 'ACTIVE');
  } else {
    btn && btn.classList.remove('listening');
    icon && icon.setAttribute('class','fas fa-microphone');
    viz && viz.classList.remove('active');
    arc && (arc.textContent = 'STANDBY');
    vs  && (vs.textContent  = 'IDLE');
  }
}
eel.expose(setListening);

function stopAssistant() {
  addMessage('Kabir', 'Goodbye Sir. Shutting down.');
}
eel.expose(stopAssistant);

// ── Eel-exposed: screen transitions ──────────────────────────────────────────
function hideLoader() {
  const el = document.getElementById('loader');
  if (el) { el.style.opacity='0'; el.style.transition='opacity 0.6s'; setTimeout(()=>el.style.display='none', 600); }
}
eel.expose(hideLoader);

function hideFaceAuth() {
  const el = document.getElementById('face-auth-con');
  if (el) { el.style.opacity='0'; el.style.transition='opacity 0.5s'; setTimeout(()=>el.style.display='none', 500); }
}
eel.expose(hideFaceAuth);

function hideFaceAuthSuccess() {
  const el = document.getElementById('face-auth-success');
  if (el) { el.style.opacity='0'; el.style.transition='opacity 0.5s'; setTimeout(()=>el.style.display='none', 500); }
}
eel.expose(hideFaceAuthSuccess);

function showFaceAuth() {
  const el = document.getElementById('face-auth-con');
  if (el) { el.style.opacity='1'; el.style.display='flex'; }
}
eel.expose(showFaceAuth);

function showFaceAuthSuccess() {
  document.getElementById('face-auth-success').style.display = 'flex';
}
eel.expose(showFaceAuthSuccess);

function hideStart() {
  // hideStart in the repo means show the main UI
  document.getElementById('start').style.display = 'flex';
}
eel.expose(hideStart);

// ── Live camera feed from Python ──────────────────────────────────────────────
function updateFaceCam(b64) {
  const img = document.getElementById('cam-feed');
  const placeholder = document.getElementById('scan-placeholder');
  if (img) {
    img.src = 'data:image/jpeg;base64,' + b64;
    img.style.display = 'block';
    if (placeholder) placeholder.style.display = 'none';
  }
}
eel.expose(updateFaceCam);

// ── Face auth text update ─────────────────────────────────────────────────────
function setFaceAuthText(text) {
  const el = document.getElementById('face-auth-text');
  if (el) el.textContent = text;
}
eel.expose(setFaceAuthText);

// ── Auth failed screen ────────────────────────────────────────────────────────
function showAuthFailed() {
  const fa = document.getElementById('face-auth-con');
  if (fa) fa.style.display = 'none';
  const el = document.getElementById('auth-failed');
  if (el) el.style.display = 'flex';
}
eel.expose(showAuthFailed);
