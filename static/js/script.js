/* ===== JARVIS Neural Interface v3 ===== */

// DOM
const userInput       = document.getElementById('user-input');
const micBtn          = document.getElementById('mic-btn');
const sendBtn         = document.getElementById('send-btn');
const stopBtn         = document.getElementById('stop-btn');
const chatMessages    = document.getElementById('chat-messages');
const orbCore         = document.getElementById('orb-core');
const orbGlow         = document.getElementById('orb-glow');
const statusIndicator = document.getElementById('status-indicator');
const statusText      = document.getElementById('status-text');
const agentBadge      = document.getElementById('agent-badge');
const topTime         = document.getElementById('top-time');
const sidebar         = document.getElementById('sidebar');
const sidebarOpenBtn  = document.getElementById('sidebar-open-btn');
const sidebarCloseBtn = document.getElementById('sidebar-close-btn');
const clearHistoryBtn = document.getElementById('clear-history-btn');
const notifArea       = document.getElementById('notification-area');

// State
let currentState     = 'listening';
let isProcessing     = false;
let eventSource      = null;
let isListeningToMic = false;
let mediaRecorder    = null;
let audioChunks      = [];
let currentAgent     = 'friday';

const STORAGE_KEY = 'jarvis_chat_v3';

// ===== AGENT COLORS =====
const AGENT_COLORS = {
    friday:   '#00ffcc',
    athena:   '#b48eff',
    ultron:   '#ff4c4c',
    veronica: '#4ca6ff',
    vision:   '#ffb347',
    file:     '#a0a0a0',
    edith:    '#1adfb2',
    personal: '#4cff8a',
    chat:     '#00ffcc',
};

// Display codenames — raw key stays the routing id; this is just the label
const AGENT_NAMES = {
    friday:'FRIDAY', athena:'ATHENA', ultron:'ULTRON', veronica:'VERONICA',
    vision:'VISION', edith:'EDITH', echo:'ECHO',
    personal:'JOCASTA',          // personal assistant — notes, habits, goals
    system:'SENTRY',             // system diagnostics — OS, battery, health
    file:'ARCHIVE',              // file + document ops
    scheduler:'CHRONOS',         // scheduling / time
    self_improvement:'PHOENIX',  // self-improvement / reflection
    terminator:'TERMINATOR',     // desktop control
    n8n:'RELAY',                 // n8n automation / outbound
    routines:'MACRO'             // record / replay command macros
};
const displayName = k => AGENT_NAMES[(k || '').toLowerCase()] || (k || '').toUpperCase();

function setAgent(agent) {
    currentAgent = agent || 'friday';
    const color  = AGENT_COLORS[currentAgent] || '#00ffcc';
    const name   = displayName(currentAgent);
    agentBadge.textContent   = name;
    agentBadge.style.color   = color;
    agentBadge.style.borderColor = `${color}50`;
    agentBadge.style.boxShadow   = `0 0 10px ${color}30`;
    document.getElementById('sb-agent').textContent = name;
    document.getElementById('sb-agent').style.color = color;
}

// ===== CLOCK =====
function updateClock() {
    const now = new Date();
    topTime.textContent = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
}
setInterval(updateClock, 1000);
updateClock();

// ===== STATUS SIDEBAR =====
async function refreshStatus() {
    try {
        const r    = await fetch('/status');
        const data = await r.json();
        setAgent(data.last_agent);
        const ollamaEl = document.getElementById('sb-ollama');
        ollamaEl.textContent  = data.ollama_online ? 'ONLINE' : 'OFFLINE';
        ollamaEl.className    = 'sidebar-value ' + (data.ollama_online ? 'online' : 'offline');
        document.getElementById('sb-tasks').textContent     = data.tasks_pending     || 0;
        document.getElementById('sb-reminders').textContent = data.reminders_pending || 0;
        document.getElementById('sb-events').textContent    = data.events_today      || 0;
    } catch (e) { /* Ollama offline */ }
}
refreshStatus();
setInterval(refreshStatus, 30000);

sidebarOpenBtn.addEventListener('click', () => { sidebar.classList.add('open'); refreshStatus(); });
sidebarCloseBtn.addEventListener('click', () => sidebar.classList.remove('open'));

// Close sidebar on outside click (mobile)
document.addEventListener('click', (e) => {
    if (sidebar.classList.contains('open') &&
        !sidebar.contains(e.target) &&
        e.target !== sidebarOpenBtn) {
        sidebar.classList.remove('open');
    }
});

clearHistoryBtn.addEventListener('click', () => {
    if (confirm('Clear chat history?')) {
        localStorage.removeItem(STORAGE_KEY);
        chatMessages.innerHTML = '';
    }
});

// ===== NOTIFICATIONS =====
function showNotification(text, kind) {
    const el = document.createElement('div');
    el.className    = 'notification' + (kind ? ' n-' + kind : '');
    el.textContent  = text;
    notifArea.appendChild(el);
    const hold = (kind === 'security') ? 9000 : 6000;
    setTimeout(() => el.classList.add('fade-out'), hold);
    setTimeout(() => el.remove(), hold + 600);
}

// ===== PROACTIVE PUSH — poll /notifications (digest, security, reminders) =====
let _lastNotifId = -1;   // -1 = prime on first poll (skip backlog)
async function pollNotifications() {
    try {
        const since = _lastNotifId < 0 ? 999999999 : _lastNotifId;
        const r = await fetch('/notifications?since=' + since);
        const data = await r.json();
        if (_lastNotifId < 0) {                 // first run: don't replay old items
            const all = await (await fetch('/notifications?since=0')).json();
            _lastNotifId = all.items.length ? all.items[all.items.length - 1].id : 0;
            return;
        }
        for (const n of (data.items || [])) {
            showNotification(n.text, n.kind);
            _lastNotifId = Math.max(_lastNotifId, n.id);
        }
    } catch (e) { /* offline */ }
}
pollNotifications();
setInterval(pollNotifications, 20000);

// ===== HUD RING — Canvas =====
const hudCanvas = document.getElementById('hud-ring');
const hudCtx    = hudCanvas ? hudCanvas.getContext('2d') : null;
const CX = hudCanvas ? hudCanvas.width  / 2 : 160;
const CY = hudCanvas ? hudCanvas.height / 2 : 160;

const HUD_COLORS = {
    listening: { r: 0,   g: 212, b: 255 },  // #00d4ff cyan
    thinking:  { r: 255, g: 150, b: 0   },  // #ff9600 amber
    speaking:  { r: 0,   g: 255, b: 136 },  // #00ff88 green
};

let hudColor    = { ...HUD_COLORS.listening };
let hudTarget   = { ...HUD_COLORS.listening };

// rings: radius, lineWidth, rotationSpeed, direction, tickCount, numArcs, arcGapRatio, alpha
const HUD_RINGS = [
    { radius: 152, lw: 0.6, speed: 0.003, dir:  1, ticks: 0,  arcs: 1,  gap: 0.0,  alpha: 0.18 }, // outer ghost
    { radius: 140, lw: 1.0, speed: 0.005, dir: -1, ticks: 72, arcs: 1,  gap: 0.0,  alpha: 0.30 }, // tick ring
    { radius: 126, lw: 2.0, speed: 0.010, dir:  1, ticks: 0,  arcs: 10, gap: 0.18, alpha: 0.90 }, // main segmented
    { radius: 110, lw: 1.2, speed: 0.020, dir: -1, ticks: 36, arcs: 6,  gap: 0.12, alpha: 0.70 }, // inner detail
    { radius:  95, lw: 1.8, speed: 0.035, dir:  1, ticks: 0,  arcs: 4,  gap: 0.22, alpha: 0.60 }, // fast inner
    { radius:  80, lw: 0.8, speed: 0.055, dir: -1, ticks: 24, arcs: 3,  gap: 0.15, alpha: 0.45 }, // close to orb
];

const ringRot = HUD_RINGS.map(() => Math.random() * Math.PI * 2);

function _lerp(a, b, t) {
    t = Math.min(1, Math.max(0, t));
    return { r: a.r + (b.r - a.r) * t | 0, g: a.g + (b.g - a.g) * t | 0, b: a.b + (b.b - a.b) * t | 0 };
}
function _rgba(c, a) { return `rgba(${c.r},${c.g},${c.b},${a})`; }

function _drawRing(ring, rot, col) {
    const { radius, lw, ticks, arcs, gap, alpha } = ring;
    const ctx = hudCtx;
    ctx.save();
    ctx.lineWidth    = lw;
    ctx.strokeStyle  = _rgba(col, alpha);
    ctx.shadowColor  = _rgba(col, alpha * 0.8);
    ctx.shadowBlur   = 8;

    if (arcs <= 1) {
        ctx.beginPath();
        ctx.arc(CX, CY, radius, 0, Math.PI * 2);
        ctx.stroke();
    } else {
        const seg = (Math.PI * 2) / arcs;
        const len = seg * (1 - gap);
        for (let i = 0; i < arcs; i++) {
            ctx.beginPath();
            ctx.arc(CX, CY, radius, rot + i * seg, rot + i * seg + len);
            ctx.stroke();
        }
    }

    if (ticks > 0) {
        ctx.shadowBlur  = 3;
        ctx.strokeStyle = _rgba(col, alpha * 0.5);
        ctx.lineWidth   = lw * 0.7;
        const step = (Math.PI * 2) / ticks;
        for (let i = 0; i < ticks; i++) {
            const a   = rot + i * step;
            const isMajor = i % (ticks / 12 | 0) === 0;
            const len = isMajor ? 6 : 3;
            ctx.beginPath();
            ctx.moveTo(CX + (radius - len) * Math.cos(a), CY + (radius - len) * Math.sin(a));
            ctx.lineTo(CX + (radius + 1)   * Math.cos(a), CY + (radius + 1)   * Math.sin(a));
            ctx.stroke();
        }
    }
    ctx.restore();
}

function _drawHudText(col) {
    const text   = 'F · R · I · D · A · Y';
    const chars  = text.split('');
    const radius = 126;
    const step   = 0.115;
    let angle    = ringRot[2] + Math.PI * 0.55 - (chars.length * step) / 2;
    const ctx    = hudCtx;
    ctx.save();
    ctx.font         = 'bold 7px Courier New';
    ctx.fillStyle    = _rgba(col, 0.75);
    ctx.shadowColor  = _rgba(col, 0.5);
    ctx.shadowBlur   = 5;
    ctx.textAlign    = 'center';
    ctx.textBaseline = 'middle';
    chars.forEach(ch => {
        const x = CX + radius * Math.cos(angle);
        const y = CY + radius * Math.sin(angle);
        ctx.save();
        ctx.translate(x, y);
        ctx.rotate(angle + Math.PI / 2);
        ctx.fillText(ch, 0, 0);
        ctx.restore();
        angle += step;
    });
    ctx.restore();
}

function _drawCenterDot(col) {
    // ── ARC REACTOR CORE (Ref-B Manina Labs style) ──
    const ctx = hudCtx;
    const t   = ringRot[2];               // shared rotation phase
    ctx.save();

    // 1. energy glow disk
    const glow = ctx.createRadialGradient(CX, CY, 2, CX, CY, 70);
    glow.addColorStop(0,   _rgba(col, 0.55));
    glow.addColorStop(0.35,_rgba(col, 0.14));
    glow.addColorStop(0.7, _rgba(col, 0.05));
    glow.addColorStop(1,   'transparent');
    ctx.fillStyle = glow;
    ctx.beginPath(); ctx.arc(CX, CY, 70, 0, Math.PI * 2); ctx.fill();

    // 2. segmented containment ring around the reactor
    ctx.strokeStyle = _rgba(col, 0.5);
    ctx.lineWidth   = 2;
    ctx.shadowColor = _rgba(col, 0.8);
    ctx.shadowBlur  = 12;
    for (let i = 0; i < 9; i++) {
        const a0 = -t * 1.3 + i * (Math.PI * 2 / 9);
        ctx.beginPath();
        ctx.arc(CX, CY, 60, a0, a0 + 0.42);
        ctx.stroke();
    }

    // 3. counter-rotating triangle reactor (two stacked for depth)
    const tri = (R, rot, alpha, lw) => {
        ctx.strokeStyle = _rgba(col, alpha);
        ctx.lineWidth   = lw;
        ctx.beginPath();
        for (let i = 0; i < 3; i++) {
            const a  = -Math.PI / 2 + i * (Math.PI * 2 / 3) + rot;
            const px = CX + Math.cos(a) * R, py = CY + Math.sin(a) * R;
            i ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
        }
        ctx.closePath(); ctx.stroke();
    };
    tri(46,  t * 0.8, 0.9, 2.2);          // main reactor triangle
    tri(34, -t * 1.1, 0.55, 1.4);         // inner counter triangle

    // 4. inner hex bolt ring + bright core
    ctx.strokeStyle = _rgba(col, 0.7);
    ctx.lineWidth = 1.4;
    ctx.beginPath(); ctx.arc(CX, CY, 20, 0, Math.PI * 2); ctx.stroke();

    const breathe = 0.6 + 0.4 * Math.sin(Date.now() / 420);
    const core = ctx.createRadialGradient(CX, CY, 0, CX, CY, 16);
    core.addColorStop(0, _rgba(col, 0.95 * breathe + 0.05));
    core.addColorStop(0.5, _rgba(col, 0.5 * breathe));
    core.addColorStop(1, 'transparent');
    ctx.fillStyle = core;
    ctx.beginPath(); ctx.arc(CX, CY, 16, 0, Math.PI * 2); ctx.fill();

    ctx.restore();
}

function hudTick() {
    if (!hudCtx) return;
    hudColor = _lerp(hudColor, hudTarget, 0.035);
    HUD_RINGS.forEach((ring, i) => {
        ringRot[i] += ring.speed * ring.dir;
    });
    hudCtx.clearRect(0, 0, hudCanvas.width, hudCanvas.height);
    _drawCenterDot(hudColor);
    HUD_RINGS.forEach((ring, i) => _drawRing(ring, ringRot[i], hudColor));
    _drawHudText(hudColor);
    requestAnimationFrame(hudTick);
}

function setHudState(state) {
    hudTarget = { ...(HUD_COLORS[state] || HUD_COLORS.listening) };
}

// ===== STATE =====
function setState(newState) {
    if (currentState === newState) return;
    currentState = newState;
    orbCore.classList.remove('thinking', 'speaking');
    orbGlow.classList.remove('thinking', 'speaking');
    if (newState !== 'listening') {
        orbCore.classList.add(newState);
        orbGlow.classList.add(newState);
    }
    const stateMap = {
        listening: { text: 'LISTENING', cls: '' },
        thinking:  { text: 'THINKING',  cls: 'thinking' },
        speaking:  { text: 'SPEAKING',  cls: 'speaking' },
    };
    const s = stateMap[newState] || stateMap.listening;
    statusText.textContent    = s.text;
    statusIndicator.className = s.cls;
    stopBtn.classList.toggle('active', newState === 'speaking' || isProcessing);
    setHudState(newState);
}

// ===== CHAT — LocalStorage =====
function saveMessage(role, content) {
    const history = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
    history.push({ role, content, ts: Date.now(), agent: currentAgent });
    if (history.length > 60) history.splice(0, history.length - 60);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
}

function loadHistory() {
    const history = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
    history.forEach(msg => renderMessage(msg.content, msg.role, msg.agent, false));
}

function renderMessage(content, role, agent, streaming = false) {
    const wrap = document.createElement('div');
    wrap.className = `message ${role}`;

    // Agent tag for assistant messages
    if (role === 'assistant' && agent) {
        const tag = document.createElement('div');
        tag.className   = 'msg-agent-tag';
        tag.textContent = agent.toUpperCase();
        tag.style.color = AGENT_COLORS[agent] || '#00ffcc';
        wrap.appendChild(tag);
    }

    const bubble = document.createElement('div');
    bubble.className = 'message-content';

    if (streaming) {
        bubble.innerHTML = '<span class="typing-cursor"></span>';
    } else {
        bubble.textContent = content;
    }

    wrap.appendChild(bubble);
    chatMessages.appendChild(wrap);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return bubble;
}

function addMessage(content, role, streaming = false) {
    return renderMessage(content, role, currentAgent, streaming);
}

// ===== SEND =====
function sendMessage() {
    const message = userInput.value.trim();
    if (!message || isProcessing) return;
    userInput.value = '';

    saveMessage('user', message);
    renderMessage(message, 'user', null, false);

    isProcessing = true;
    setState('thinking');

    const assistantBubble = addMessage('', 'assistant', true);
    let responseText = '';
    let isFirstChunk = true;

    const url = '/chat_stream?message=' + encodeURIComponent(message);
    eventSource = new EventSource(url);

    eventSource.onmessage = function (e) {
        try {
            const data = JSON.parse(e.data);

            if (data.type === 'reminder') {
                showNotification(data.value);
                return;
            }

            if (data.type === 'agent') {
                setAgent(data.value);
                return;
            }

            if (data.type === 'status' && data.value === 'speaking') {
                setState('speaking');
                const c = assistantBubble.querySelector('.typing-cursor');
                if (c) c.remove();
                return;
            }

            if (data.type === 'chunk') {
                if (isFirstChunk) {
                    assistantBubble.innerHTML = '';
                    isFirstChunk = false;
                }
                const c = assistantBubble.querySelector('.typing-cursor');
                if (c) c.remove();
                responseText += data.value;
                assistantBubble.textContent = responseText;
                const cursor = document.createElement('span');
                cursor.className = 'typing-cursor';
                assistantBubble.appendChild(cursor);
                chatMessages.scrollTop = chatMessages.scrollHeight;
            }

            if (data.type === 'done') {
                const c = assistantBubble.querySelector('.typing-cursor');
                if (c) c.remove();
                saveMessage('assistant', responseText);
                setState('listening');
                isProcessing = false;
                eventSource.close();
                refreshStatus();
            }
        } catch (err) {
            console.error('Parse error:', err);
        }
    };

    eventSource.onerror = function () {
        const c = assistantBubble.querySelector('.typing-cursor');
        if (c) c.remove();
        setState('listening');
        isProcessing = false;
        eventSource.close();
    };
}

// ===== STOP =====
function stopVoice() {
    if (!isProcessing) return;
    if (eventSource) eventSource.close();
    fetch('/stop', { method: 'POST' }).catch(() => {});
    isProcessing = false;
    setState('listening');
}

// ===== VOICE INPUT =====
function startVoiceInput() {
    if (isListeningToMic) return;
    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
            isListeningToMic = true;
            audioChunks = [];
            micBtn.classList.add('recording');
            userInput.placeholder = 'Recording... (click mic to stop)';
            userInput.disabled    = true;

            mediaRecorder = new MediaRecorder(stream);
            mediaRecorder.ondataavailable = e => { if (e.data.size > 0) audioChunks.push(e.data); };
            mediaRecorder.onstop = async () => {
                stream.getTracks().forEach(t => t.stop());
                userInput.placeholder = 'Transcribing...';
                const blob     = new Blob(audioChunks, { type: 'audio/webm' });
                const formData = new FormData();
                formData.append('audio', blob, 'recording.webm');
                try {
                    const res  = await fetch('/transcribe', { method: 'POST', body: formData });
                    const data = await res.json();
                    if (data.success && data.text) {
                        userInput.value       = data.text;
                        userInput.disabled    = false;
                        userInput.placeholder = 'Speak or type...';
                        isListeningToMic      = false;
                        micBtn.classList.remove('recording');
                        setTimeout(sendMessage, 80);
                    } else {
                        userInput.placeholder = data.error === 'No speech detected' ? 'No speech detected.' : 'Transcription failed.';
                        userInput.disabled    = false;
                        isListeningToMic      = false;
                        micBtn.classList.remove('recording');
                    }
                } catch (err) {
                    userInput.placeholder = 'Error. Try again.';
                    userInput.disabled    = false;
                    isListeningToMic      = false;
                    micBtn.classList.remove('recording');
                }
            };
            mediaRecorder.start();
        })
        .catch(() => alert('Microphone access denied.'));
}

function stopVoiceInput() {
    if (mediaRecorder && mediaRecorder.state === 'recording') mediaRecorder.stop();
}

// ===== EVENTS =====
sendBtn.addEventListener('click', sendMessage);
stopBtn.addEventListener('click', stopVoice);
micBtn.addEventListener('click', () => isListeningToMic ? stopVoiceInput() : startVoiceInput());
userInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});
document.addEventListener('keydown', e => {
    if (e.altKey && e.key.toLowerCase() === 's') { e.preventDefault(); stopVoice(); }
});
userInput.addEventListener('focus', () => { userInput.parentElement.style.boxShadow = '0 0 16px rgba(0,255,200,0.2)'; });
userInput.addEventListener('blur',  () => { userInput.parentElement.style.boxShadow = 'none'; });
window.addEventListener('beforeunload', () => { if (eventSource) eventSource.close(); });

// ===== WAKE WORD =====
const wakeBtn = document.getElementById('wake-btn');
let wakeEnabled    = false;
let wakeEventSrc   = null;

function toggleWakeWord() {
    wakeEnabled = !wakeEnabled;
    wakeBtn.classList.toggle('active', wakeEnabled);
    wakeBtn.title = wakeEnabled
        ? 'Wake word ON — say "Friday" or "Hey Jarvis" to activate'
        : 'Wake word OFF';

    fetch('/wake_toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: wakeEnabled })
    }).catch(() => {});

    if (wakeEnabled) {
        wakeEventSrc = new EventSource('/wake_stream');
        wakeEventSrc.onmessage = function (e) {
            try {
                const data = JSON.parse(e.data);
                if (data.type === 'wake' && data.value === 'triggered') {
                    onWakeWordDetected();
                }
            } catch (err) {}
        };
        wakeEventSrc.onerror = function () {
            // retry automatically via EventSource reconnect
        };
    } else {
        if (wakeEventSrc) {
            wakeEventSrc.close();
            wakeEventSrc = null;
        }
    }
}

function onWakeWordDetected() {
    if (isProcessing || isListeningToMic) return;
    // Visual flash
    wakeBtn.style.transform = 'scale(1.2)';
    setTimeout(() => { wakeBtn.style.transform = 'scale(1)'; }, 200);
    // Auto-start mic
    startVoiceInput();
}

if (wakeBtn) {
    wakeBtn.addEventListener('click', toggleWakeWord);
}

// ===== AUTONOMOUS VOICE LOOP (Phase 28) =====
const vloopBtn = document.getElementById('vloop-btn');
let vloopEnabled = false;

function toggleVoiceLoop() {
    vloopEnabled = !vloopEnabled;
    vloopBtn.classList.toggle('active', vloopEnabled);
    vloopBtn.title = vloopEnabled
        ? 'Voice Loop ON — fully autonomous (say "Friday" to activate)'
        : 'Voice Loop OFF';

    fetch('/voice_loop_toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: vloopEnabled })
    }).catch(() => {});

    // Voice loop manages wake detection internally — disable manual wake btn to avoid conflict
    if (vloopEnabled && wakeEnabled) {
        toggleWakeWord();  // turn off manual wake word mode
    }
}

if (vloopBtn) {
    vloopBtn.addEventListener('click', toggleVoiceLoop);
}

// ===== BOOT SEQUENCE =====
const BOOT_LINES = [
    { text: '> INITIALIZING JARVIS v3.0', ok: false },
    { text: '> NEURAL ENGINE', ok: true },
    { text: '> LOADING AGENTS  [FRIDAY / ATHENA / VERONICA / ULTRON / VISION]', ok: true },
    { text: '> WHISPER STT', ok: true },
    { text: '> VECTOR MEMORY', ok: true },
    { text: '> ALL SYSTEMS NOMINAL', ok: false, dim: false },
    { text: '> GOOD TO SEE YOU, BOSS.', ok: false, dim: true },
];

function runBoot() {
    const overlay  = document.getElementById('boot-overlay');
    const linesDiv = document.getElementById('boot-lines');
    const fill     = document.getElementById('boot-progress-fill');

    let i = 0;
    const step = () => {
        if (i >= BOOT_LINES.length) {
            fill.style.width = '100%';
            setTimeout(() => {
                overlay.classList.add('hidden');
                setTimeout(() => { overlay.style.display = 'none'; }, 900);
            }, 400);
            return;
        }
        const item = BOOT_LINES[i];
        const el   = document.createElement('div');
        el.className = 'boot-line' + (item.ok ? ' ok' : '') + (item.dim ? ' dim' : '');
        el.textContent = item.text;
        linesDiv.appendChild(el);
        requestAnimationFrame(() => el.classList.add('show'));
        fill.style.width = Math.round(((i + 1) / BOOT_LINES.length) * 100) + '%';
        i++;
        setTimeout(step, i === 1 ? 300 : 220);
    };
    step();
}

// ===== INIT =====
window.addEventListener('load', () => {
    setState('listening');
    requestAnimationFrame(hudTick);
    runBoot();

    // Load chat history after short delay (after boot)
    setTimeout(() => {
        loadHistory();
        userInput.focus();
        _syncLeftPanel();
        _startSignalWave();
        _startUptime();
        _updateDate();
        _refreshAgentChips(currentAgent);
    }, 2400);
});

// ═══════════════════════════════════════════════════════════
//  CINEMATIC HUD EXTENSIONS — left panel, signal wave, date
// ═══════════════════════════════════════════════════════════

// ── DATE DISPLAY ────────────────────────────────────────────
function _updateDate() {
    const el = document.getElementById('top-date');
    if (!el) return;
    const d = new Date();
    const days   = ['SUN','MON','TUE','WED','THU','FRI','SAT'];
    const months = ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'];
    el.textContent = `${days[d.getDay()]} ${String(d.getDate()).padStart(2,'0')} ${months[d.getMonth()]}`;
}
setInterval(_updateDate, 60000);

// ── LEFT PANEL SYNC ──────────────────────────────────────────
function _syncLeftPanel() {
    const lpAgent = document.getElementById('lp-agent');
    const lpMode  = document.getElementById('lp-mode');
    if (lpAgent) {
        lpAgent.textContent = currentAgent.toUpperCase();
        const color = AGENT_COLORS[currentAgent] || '#00d4ff';
        lpAgent.style.color = color;
        lpAgent.style.textShadow = `0 0 8px ${color}60`;
    }
    if (lpMode) {
        const modeMap = { listening:'LISTENING', thinking:'PROCESSING', speaking:'RESPONDING' };
        lpMode.textContent = modeMap[currentState] || 'STANDBY';
    }
}

// Patch setAgent to update left panel + chips
const _origSetAgent = setAgent;
setAgent = function(agent) {
    _origSetAgent(agent);
    const lpAgent = document.getElementById('lp-agent');
    if (lpAgent) {
        lpAgent.textContent = displayName(agent || 'friday');
        const color = AGENT_COLORS[agent] || '#00d4ff';
        lpAgent.style.color = color;
        lpAgent.style.textShadow = `0 0 8px ${color}60`;
    }
    _refreshAgentChips(agent || 'friday');
    if (typeof highlightFleet === 'function') highlightFleet((agent || 'friday').toLowerCase());
};

// Patch setState to update left panel mode
const _origSetState = setState;
setState = function(newState) {
    _origSetState(newState);
    const lpMode = document.getElementById('lp-mode');
    if (lpMode) {
        const modeMap = { listening:'LISTENING', thinking:'PROCESSING', speaking:'RESPONDING' };
        lpMode.textContent = modeMap[newState] || 'STANDBY';
    }
};

// ── AGENT FLEET CHIP HIGHLIGHTING ───────────────────────────
function _refreshAgentChips(agent) {
    document.querySelectorAll('#agent-fleet .agent-chip').forEach(chip => {
        chip.classList.toggle('active', chip.dataset.agent === agent);
    });
}

// ── MESSAGE COUNTER ──────────────────────────────────────────
function _updateMsgCount() {
    const el = document.getElementById('lp-msgs');
    if (!el) return;
    const history = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
    el.textContent = history.length;
}

const _origSaveMessage = saveMessage;
saveMessage = function(role, content) {
    _origSaveMessage(role, content);
    _updateMsgCount();
};

// ── UPTIME COUNTER ───────────────────────────────────────────
let _startTime = Date.now();
function _startUptime() {
    const el = document.getElementById('lp-uptime');
    if (!el) return;
    setInterval(() => {
        const s = Math.floor((Date.now() - _startTime) / 1000);
        const h = String(Math.floor(s / 3600)).padStart(2, '0');
        const m = String(Math.floor((s % 3600) / 60)).padStart(2, '0');
        el.textContent = `${h}:${m}`;
    }, 10000);
}

// ── SIGNAL WAVE CANVAS ───────────────────────────────────────
function _startSignalWave() {
    const canvas = document.getElementById('signal-wave');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;
    let offset = 0;

    function drawWave() {
        ctx.clearRect(0, 0, W, H);

        // pick color from current state
        const stateCol = {
            listening: { r:0,   g:200, b:255 },
            thinking:  { r:255, g:160, b:0   },
            speaking:  { r:0,   g:255, b:136 },
        };
        const sc = stateCol[currentState] || stateCol.listening;
        const colStr = `rgba(${sc.r},${sc.g},${sc.b}`;

        // background faint trace
        ctx.beginPath();
        ctx.strokeStyle = `${colStr},0.12)`;
        ctx.lineWidth = 1;
        for (let x = 0; x < W; x++) {
            const y = H / 2;
            if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.stroke();

        // main wave
        const amp = currentState === 'thinking' ? 16 : currentState === 'speaking' ? 18 : (isListeningToMic ? 20 : 6);
        ctx.beginPath();
        ctx.strokeStyle = `${colStr},0.85)`;
        ctx.lineWidth = 1.5;
        ctx.shadowColor = `${colStr},0.5)`;
        ctx.shadowBlur  = 5;

        for (let x = 0; x < W; x++) {
            const t  = (x + offset) * 0.09;
            const y  = H / 2
                + Math.sin(t)       * amp * 0.55
                + Math.sin(t * 2.1) * amp * 0.28
                + Math.sin(t * 0.5) * amp * 0.17;
            if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.stroke();
        ctx.shadowBlur = 0;

        offset += isListeningToMic ? 5 : currentState === 'speaking' ? 3.5 : 1.2;
        requestAnimationFrame(drawWave);
    }
    drawWave();
}

// ── SIDEBAR CLICK — just refresh status (sidebar is always visible) ──
// Override the add/remove 'open' behavior — sidebar is now a permanent flex item.
// sidebarOpenBtn already calls refreshStatus() via the original listener above.

/* ═══════════ PHASE 45 — Command Center: live panels · 15-agent fleet · modes ═══════════ */

// Full 15-agent palette (extends the 9 above)
const FLEET_COLORS = {
    friday:'#00d4ff', athena:'#c084fc', ultron:'#ff3344', veronica:'#4ca6ff',
    vision:'#ffb347', edith:'#1adfb2', echo:'#ff8ad6', personal:'#4cff8a',
    system:'#9ad0ff', file:'#a0a0a0', scheduler:'#ffd24c',
    self_improvement:'#7CFFB2', terminator:'#ff6b3d', n8n:'#d36cff', routines:'#6cffe0'
};


// ── build the 15-agent fleet ──
(function buildFleet(){
    const el = document.getElementById('agent-fleet');
    if (!el) return;
    el.innerHTML = '';
    Object.keys(FLEET_COLORS).forEach(a => {
        const c = FLEET_COLORS[a];
        const chip = document.createElement('div');
        chip.className = 'agent-chip';
        chip.dataset.agent = a;
        chip.title = a;   // raw key on hover
        chip.innerHTML = `<span class="ac-dot" style="color:${c}"></span>${displayName(a)}`;
        el.appendChild(chip);
    });
})();

function highlightFleet(agent){
    document.querySelectorAll('.agent-chip').forEach(e =>
        e.classList.toggle('live', e.dataset.agent === agent));
}

// ── live /health → left SYSTEMS panel + integrity bars ──
async function refreshHealth(){
    try {
        const h = await (await fetch('/health')).json();
        const dot = (id, ok, warn) => {
            const e = document.getElementById(id); if(!e) return;
            e.className = 'mdot ' + (ok ? 'ok' : (warn ? 'warn' : 'err'));
        };
        const val = (id, t) => { const e=document.getElementById(id); if(e) e.textContent=t||''; };

        dot('m-ollama', h.ollama.up, false);   val('mv-ollama', h.ollama.model_loaded ? 'LOADED':'NO MODEL');
        dot('m-whisper', h.whisper.loaded, true); val('mv-whisper', (h.whisper.model||'').toUpperCase());
        dot('m-tts', h.tts.kokoro_worker_alive, true); val('mv-tts', (h.tts.backend||'').toUpperCase());
        dot('m-sched', h.scheduler.running, true); val('mv-sched', h.scheduler.running?'RUN':'IDLE');
        dot('m-browser', h.browser.enabled, true); val('mv-browser', h.browser.enabled?'ON':'OFF');
        dot('m-autotune', true, false);

        // integrity bars → real metrics
        const bar = (f, p, pct, label) => {
            const fe=document.getElementById(f), pe=document.getElementById(p);
            if(fe) fe.style.width = pct+'%';
            if(pe) pe.textContent = label;
        };
        bar('if-model','ip-model', h.ollama.model_loaded?100:0, h.ollama.model_loaded?'OK':'OFF');
        if (h.disk && h.disk.pct_used!=null)
            bar('if-disk','ip-disk', 100-h.disk.pct_used, (h.disk.free_gb||'?')+'GB');
        bar('if-comms','ip-comms', h.ollama.up?100:0, h.ollama.up?'100%':'DOWN');
    } catch(e) { /* offline */ }
}
refreshHealth();
setInterval(refreshHealth, 7000);

// (fleet highlight hooked into the existing setAgent wrapper above)

// ── OPERATIONS / CYBER data ──
async function refreshModes(){
    try {
        const st = await (await fetch('/status')).json();
        const set=(id,v)=>{const e=document.getElementById(id); if(e) e.textContent=v;};
        set('op-tasks', st.tasks_pending||0);
        set('op-rem',   st.reminders_pending||0);
        set('op-evt',   st.events_today||0);
    } catch(e){}
    try {
        const h = await (await fetch('/health')).json();
        const e=document.getElementById('op-sched'); if(e) e.textContent = h.scheduler.running?'RUN':'IDLE';
    } catch(e){}
    try {
        const cy = await (await fetch('/cyber_status')).json();
        const set=(id,v)=>{const e=document.getElementById(id); if(e) e.textContent=v;};
        set('cy-cve', cy.cve_tracked||0);
        set('cy-scan', cy.last_scan || 'none');
    } catch(e){}
    try {
        const m = await (await fetch('/metrics')).json();
        const set=(id,v)=>{const e=document.getElementById(id); if(e) e.textContent=v;};
        set('op-calls', m.total_calls||0);
        set('op-busiest', m.busiest ? displayName(m.busiest) : '—');
        set('op-errs', m.total_errors||0);
        const r = (m.recent||[])[0];
        set('op-recent', r ? `${displayName(r.agent)} ${r.action||''} ${r.ms}ms` : 'idle');
    } catch(e){}
}

// ── MODE SWITCHING ──
const modeView = document.getElementById('mode-view');
const mainWorkspace = document.getElementById('main-workspace');
function setMode(mode){
    document.querySelectorAll('.mode-tab').forEach(t =>
        t.classList.toggle('on', t.dataset.mode === mode));
    if (mode === 'command') {
        modeView.hidden = true;
        if (mainWorkspace) mainWorkspace.style.display = '';   // restore orb+chat+panels
    } else {
        if (mainWorkspace) mainWorkspace.style.display = 'none'; // kill orb bleed-through
        modeView.hidden = false;
        document.querySelectorAll('.mview').forEach(s =>
            s.hidden = (s.dataset.mview !== mode));
        refreshModes();
    }
}
document.querySelectorAll('.mode-tab').forEach(t =>
    t.addEventListener('click', () => setMode(t.dataset.mode)));
