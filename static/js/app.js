/* ============================================================
   Safar-e-Taleem — Shared Frontend Logic
   Full voice pipeline: mic input (STT) + spoken output (TTS)
   ============================================================ */

let isRecording = false;
let speechRecognition = null;
let _cachedVoice = null;
let _cachedUrduVoice = null;

// Detect the best STT language for Roman-Urdu + English mixed speech.
// 'en-PK' would be ideal (Pakistan-English accent + Urdu loanwords) but
// many browsers don't support it.  We probe the SpeechRecognition
// implementation's supported locales when possible, then fall back to
// the universally-supported 'en-US' which handles mixed code-switching
// reasonably well since the target phrases are mostly English words
// with Urdu grammar connectors (petrol, school, cost, price, etc.).
function _detectSTTLang() {
    try {
        const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRec) return 'en-US';
        // Some browsers expose a getSupportedLanguages helper
        if (typeof SpeechRec.getSupportedLanguages === 'function') {
            const supported = SpeechRec.getSupportedLanguages();
            if (supported && supported.includes('en-PK')) return 'en-PK';
        }
    } catch (_) { /* swallow */ }
    // Chrome accepts 'en-PK' without error even if it internally maps to
    // en-IN or en-US — try it and let the browser handle the mapping.
    return 'en-PK';
}

// Pick the best English voice (warm female preferred, always available)
function _pickEnglishVoice(voices) {
    return voices.find(v => /female|samantha|karen|victoria|zira/i.test(v.name) && v.lang.startsWith('en')) ||
           voices.find(v => v.lang === 'en-US') ||
           voices.find(v => v.lang.startsWith('en')) ||
           null;
}

// Pick an Urdu voice if the browser/OS has one installed (Chrome on Android
// and some desktop setups do; many don't). Roman-Urdu text read by an actual
// Urdu voice engine sounds far more natural than an English voice guessing
// at the pronunciation.
function _pickUrduVoice(voices) {
    return voices.find(v => v.lang === 'ur-PK') ||
           voices.find(v => v.lang && v.lang.startsWith('ur')) ||
           voices.find(v => /urdu/i.test(v.name)) ||
           null;
}

// Preload voices
if (window.speechSynthesis) {
    speechSynthesis.onvoiceschanged = () => {
        _cachedVoice = _pickEnglishVoice(speechSynthesis.getVoices());
        _cachedUrduVoice = _pickUrduVoice(speechSynthesis.getVoices());
    };
    if (speechSynthesis.getVoices().length > 0) {
        speechSynthesis.onvoiceschanged();
    }
}

/* ---------- FUEL PRICE LIVE POLLING (TrackMate API) ---------- */

const FUEL_REFRESH_INTERVAL = 300000; // 5 minutes
let _fuelTimer = null;

/**
 * Show skeleton placeholders in all fuel tiles while loading.
 */
function _showFuelSkeleton() {
    document.querySelectorAll('.fuel-tile-price').forEach(el => {
        if (!el.dataset.loaded) {
            el.innerHTML = '<span class="skeleton skeleton-line" style="display:inline-block;width:70%;">&nbsp;</span>';
        }
    });
    const refreshBtn = document.querySelector('.fuel-refresh-btn');
    if (refreshBtn) refreshBtn.classList.add('spinning');
}

/**
 * Format price for display — Rs XXX.XX / L  or  Rs XXX / kg
 */
function _fmtFuel(price, unit) {
    if (price == null) return '—';
    const p = typeof price === 'number' ? price : parseFloat(price);
    if (isNaN(p)) return '—';
    return 'Rs ' + p.toFixed(2);
}

/**
 * Core fetch — hits the backend /api/petrol-price which proxies TrackMate.
 * Updates petrol, diesel, kerosene, LPG tiles, effective date, source badge.
 */
async function updatePrice() {
    const refreshBtn = document.querySelector('.fuel-refresh-btn');
    if (refreshBtn) refreshBtn.classList.add('spinning');

    // Hackathon demo slider guard: while a simulated petrol price is active on
    // the principal dashboard, don't let this poll overwrite the simulated
    // petrol display (diesel/kerosene/LPG tiles still refresh normally).
    const simSlider = document.getElementById('petrol-spike-slider');
    const simActive = !!(simSlider && simSlider.dataset.simulating === '1');

    try {
        const res = await fetch('/api/petrol-price');
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();

        // ---- Petrol (primary display) ----
        const priceEl = document.getElementById('live-price');
        if (priceEl && !simActive) {
            priceEl.textContent = 'Rs ' + data.price + ' / L';
            priceEl.dataset.loaded = '1';
        }

        // ---- Direction / change indicator ----
        const changeEl = document.querySelector('.petrol-change');
        if (changeEl && !simActive && data.direction !== 'unchanged') {
            const color = data.direction === 'increase' ? '#fca5a5' : '#86efac';
            const dotColor = data.direction === 'increase' ? '#ef4444' : '#004D40';
            const sign = data.direction === 'increase' ? '+' : '';
            changeEl.innerHTML =
                '<span class="live-dot" style="background-color: ' + dotColor + ';"></span> ' +
                '<span style="color: ' + color + ';">Price ' + data.direction + 'd by Rs ' +
                Math.abs(data.difference) + ' (' + sign + data.percentage_change + '%)</span>';
        }

        // ---- Alert status (principal page) ----
        const statusEl = document.getElementById('status-text');
        if (statusEl && !simActive && data.alert) {
            statusEl.innerHTML =
                '<span class="live-dot" style="background-color: #ef4444;"></span> ' +
                'High Alert: Critical Price Increase (+' + data.percentage_change + '%)';
        }

        // ---- Multi-fuel tiles ----
        if (!simActive) _updateFuelTile('fuel-petrol', data.price, 'litre');
        _updateFuelTile('fuel-diesel', data.diesel, 'litre');
        _updateFuelTile('fuel-kerosene', data.kerosene, 'litre');
        _updateFuelTile('fuel-lpg', data.lpg, 'kg');

        // ---- Effective date ----
        const effEl = document.getElementById('fuel-effective-date');
        if (effEl && data.effective_date) {
            effEl.textContent = 'Effective: ' + data.effective_date;
        }

        // ---- Source badge ----
        const srcEl = document.getElementById('fuel-source');
        if (srcEl && data.source) {
            srcEl.textContent = data.source;
        }

        // ---- Clear error state ----
        const errEl = document.getElementById('fuel-error-msg');
        if (errEl) errEl.style.display = 'none';

    } catch (e) {
        console.error('Fuel price fetch error:', e);
        // Show error state — don't clear existing valid data
        const errEl = document.getElementById('fuel-error-msg');
        if (errEl) {
            errEl.style.display = 'flex';
            errEl.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Unable to load latest fuel prices. Showing last known values.';
        }
    } finally {
        if (refreshBtn) refreshBtn.classList.remove('spinning');
    }
}

function _updateFuelTile(id, price, unit) {
    const el = document.getElementById(id);
    if (!el) return;
    el.dataset.loaded = '1';
    if (price == null) {
        el.textContent = '—';
        return;
    }
    el.textContent = _fmtFuel(price, unit);
}

/**
 * Manual refresh button handler.
 */
function refreshFuelPrices() {
    updatePrice();
}

/**
 * Start periodic fuel price polling (every 5 minutes).
 */
function _startFuelPolling() {
    // Immediate first fetch
    _showFuelSkeleton();
    updatePrice();
    // Then every 5 minutes
    _fuelTimer = setInterval(updatePrice, FUEL_REFRESH_INTERVAL);
}

/* ---------- AI CHATBOT (Ask Ammi/Abba) ---------- */

function toggleRobotAssistant() {
    const popup = document.getElementById('chat-popup');
    const bubble = document.getElementById('bot-bubble');
    if (!popup) return;

    if (popup.style.display === 'flex') {
        popup.style.display = 'none';
        if (bubble) bubble.style.display = 'block';
    } else {
        popup.style.display = 'flex';
        if (bubble) bubble.style.display = 'none';
    }
}

function appendMessage(text, sender) {
    const messages = document.getElementById('chat-messages');
    if (!messages) return;

    const msgDiv = document.createElement('div');
    msgDiv.className = 'message ' + sender + '-message';
    msgDiv.innerText = text;
    messages.appendChild(msgDiv);
    messages.scrollTop = messages.scrollHeight;
}

async function sendMessage() {
    const input = document.getElementById('chat-input');
    if (!input) return;

    const query = input.value.trim();
    if (!query) return;

    // Voice diagnostic command
    if (query.toLowerCase() === 'voice' || query.toLowerCase() === 'voice test') {
        appendMessage(query, 'user');
        input.value = '';
        showVoiceDiagnostic();
        return;
    }

    appendMessage(query, 'user');
    input.value = '';

    try {
        const res = await fetch('/api/ask-ammi-abba', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: query })
        });
        const data = await res.json();
        appendMessage(data.text_response, 'bot');
        speakResponse(data.text_response, data.source);
    } catch (e) {
        appendMessage("Sorry, I couldn't connect right now. Please try again.", 'bot');
    }
}

function handleKeyPress(e) {
    if (e.key === 'Enter') sendMessage();
}

/* ---------- VOICE: STT (Speech Recognition) + TTS (Speech Synthesis) ---------- */

function speakResponse(text, source) {
    if (!window.speechSynthesis) return;

    // Clean text for speech
    let clean = text
        .replace(/[\u{1F600}-\u{1F64F}\u{1F300}-\u{1F5FF}\u{1F680}-\u{1F6FF}\u{1F1E0}-\u{1F1FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\u{1F900}-\u{1F9FF}\u{200D}\u{FE0F}]/gu, '')
        .replace(/\n+/g, '. ')
        .replace(/\u2022/g, '')
        .replace(/Rs ([\d,]+)/g, '$1 rupees')
        .replace(/(\d+)%/g, '$1 percent')
        .trim();

    // Ensure voices loaded
    if (!_cachedVoice) _cachedVoice = _pickEnglishVoice(speechSynthesis.getVoices());
    if (!_cachedUrduVoice) _cachedUrduVoice = _pickUrduVoice(speechSynthesis.getVoices());

    speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(clean);

    // Qwen responses are Roman-Urdu — an actual Urdu voice (if the browser
    // has one) pronounces this far more naturally than an English voice
    // guessing at it. Rule-based fallback text is plain English, so keep
    // the English voice for that.
    if (source === 'qwen' && _cachedUrduVoice) {
        utterance.voice = _cachedUrduVoice;
        utterance.lang = _cachedUrduVoice.lang;
        utterance.rate = 0.85;
    } else {
        utterance.lang = 'en-US';
        utterance.rate = source === 'qwen' ? 0.80 : 0.90; // slower helps English voices with Roman-Urdu words
        if (_cachedVoice) utterance.voice = _cachedVoice;
    }
    utterance.pitch = 1.0;

    speechSynthesis.speak(utterance);
}

// Voice diagnostic — type "voice" in chat to see what's available
function showVoiceDiagnostic() {
    const voices = speechSynthesis.getVoices();
    if (voices.length === 0) {
        appendMessage('Voices loading... Type "voice" again in 1 second.', 'bot');
        return;
    }
    const selected = _cachedVoice ? _cachedVoice.name + ' (' + _cachedVoice.lang + ')' : 'None';
    const urdu = _cachedUrduVoice ? _cachedUrduVoice.name + ' (' + _cachedUrduVoice.lang + ')' : 'None found on this device';
    appendMessage(
        'Voice Info:\n' +
        'Total voices available: ' + voices.length + '\n' +
        'English voice in use: ' + selected + '\n' +
        'Urdu voice found: ' + urdu + '\n\n' +
        'All voices: ' + voices.slice(0, 10).map(v => v.name + ' (' + v.lang + ')').join(', ') + (voices.length > 10 ? '...' : ''),
        'bot'
    );
}

function _findMicElements() {
    // Generic: find mic button and icon from the current chat footer
    const footer = document.querySelector('.chat-footer');
    const micBtn = footer ? footer.querySelector('.chat-mic-btn') : null;
    const micIcon = footer ? footer.querySelector('.chat-mic-btn i, [id$="-mic-icon"]') :
                             document.querySelector('[id$="-mic-icon"]');
    return { micBtn, micIcon };
}

// Toggle the shared recording visuals on the mic button + chat input.
// Class-based (no inline backgroundColor) so the same code drives the
// mic button on every page (parent-mic-btn, index-mic-btn, …).
function _setMicRecordingUI(recording) {
    const { micBtn, micIcon } = _findMicElements();
    const input = document.getElementById('chat-input');

    if (micBtn) {
        micBtn.classList.toggle('recording', recording);
        micBtn.setAttribute('aria-pressed', recording ? 'true' : 'false');
        micBtn.title = recording ? 'Stop recording' : 'Voice Assistant';
    }
    if (micIcon) {
        micIcon.className = recording ? 'fa-solid fa-circle-stop' : 'fa-solid fa-microphone';
    }
    if (input) {
        if (recording) {
            if (!input.dataset.placeholder) input.dataset.placeholder = input.placeholder;
            input.placeholder = 'Listening… speak now';
        } else if (input.dataset.placeholder) {
            input.placeholder = input.dataset.placeholder;
            delete input.dataset.placeholder;
        }
        input.classList.toggle('listening', recording);
    }
}

/**
 * Wire onstart / onresult / onerror / onend handlers onto a
 * SpeechRecognition instance.  Extracted so the language-fallback
 * retry in onerror can reuse the exact same wiring.
 */
function _wireRecognitionHandlers(rec) {
    rec.onstart = () => {
        isRecording = true;
        _setMicRecordingUI(true);
    };

    rec.onresult = (event) => {
        const input = document.getElementById('chat-input');
        if (!input) return;

        // Collect this update's interim + final chunks
        let interim = '';
        let finalText = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
            const result = event.results[i];
            if (result.isFinal) finalText += result[0].transcript;
            else interim += result[0].transcript;
        }

        if (finalText) {
            // Final transcript → place it in the chat input, then reuse the
            // normal submission flow (exactly one /api/ask-ammi-abba call).
            input.value = finalText.trim();
            console.log('[STT] Final transcript:', input.value);
            sendMessage();
        } else if (interim) {
            // Interim preview only — never submits
            input.value = interim;
        }
    };

    rec.onerror = (event) => {
        // A newer recognition session took over — ignore stale events
        if (speechRecognition !== rec) return;

        const err = event.error;
        if (err === 'aborted') {
            // User pressed the mic to stop — intentional, not a failure
            return;
        }
        // 'language-not-supported' means the browser rejected 'en-PK'.
        // Retry once with 'en-US' as a safe fallback.
        if (err === 'language-not-supported' && rec.lang !== 'en-US') {
            console.warn('[STT] Language', rec.lang, 'not supported — retrying with en-US');
            appendMessage('Switching to English recognition…', 'bot');
            isRecording = false;
            _setMicRecordingUI(false);
            const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRec) return;
            // Small delay to let the current session fully close
            setTimeout(() => {
                const fallback = new SpeechRec();
                speechRecognition = fallback;
                fallback.lang = 'en-US';
                fallback.interimResults = true;
                fallback.maxAlternatives = 1;
                fallback.continuous = false;
                _wireRecognitionHandlers(fallback);
                try { fallback.start(); } catch (_) { /* give up */ }
            }, 300);
            return;
        }
        if (err === 'not-allowed' || err === 'service-not-allowed') {
            appendMessage('Microphone permission was blocked. Please type your message instead.', 'bot');
        } else if (err === 'no-speech') {
            appendMessage('Could not hear you. Press the mic again and speak louder.', 'bot');
        } else if (err === 'audio-capture') {
            appendMessage('No microphone found. Please check your device or type your message.', 'bot');
        } else if (err === 'network') {
            appendMessage('Voice recognition network error. Please check your connection or type your message.', 'bot');
        } else {
            appendMessage('Voice error. Please type your message instead.', 'bot');
        }
    };

    rec.onend = () => {
        // A newer recognition session took over — ignore stale events
        if (speechRecognition !== rec) return;
        isRecording = false;
        _setMicRecordingUI(false);
    };
}

function recordVoiceCommand() {
    // Browser support — graceful fallback to manual typing, never crash
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRec) {
        appendMessage("Voice input isn't supported in this browser. Please type your message.", 'bot');
        return;
    }

    // Toggle off: the user clicked the mic again to stop an in-progress
    // recording. Any interim text already in the input stays there so it can
    // be edited and sent manually.
    if (isRecording) {
        if (speechRecognition) {
            try { speechRecognition.stop(); } catch (e) { /* already stopped */ }
        }
        isRecording = false;
        _setMicRecordingUI(false);
        return;
    }

    const rec = new SpeechRec();
    speechRecognition = rec;

    // Language for Roman-Urdu + English mixed speech recognition.
    // 'en-PK' is preferred (Pakistan-English accent handles Urdu loanwords
    // like "mehnga", "barh", "band" better than generic en-US).  Falls
    // back to 'en-US' if the browser rejects 'en-PK' at start time.
    // We preserve the exact transcript returned by the browser — no
    // transliteration or language conversion is performed.
    const preferredLang = _detectSTTLang();
    rec.lang = preferredLang;
    console.log('[STT] Recognition language:', preferredLang);

    rec.interimResults = true;   // live preview in the chat input while speaking
    rec.maxAlternatives = 1;
    rec.continuous = false;

    _wireRecognitionHandlers(rec);

    try {
        rec.start();
    } catch (e) {
        // e.g. InvalidStateError from a still-active recognition instance
        appendMessage('Voice error. Please type your message instead.', 'bot');
        isRecording = false;
        _setMicRecordingUI(false);
    }
}

/* ---------- PETROL HISTORY CHART (Canvas, no library) ---------- */

async function loadPetrolChart() {
    const canvas = document.getElementById('petrol-chart');
    if (!canvas) return;

    try {
        const res = await fetch('/api/petrol-history');
        const history = await res.json();

        if (!history || history.length === 0) return;

        const badge = document.getElementById('history-badge');
        if (badge) {
            badge.textContent = history.length + ' records';
        }

        const ctx = canvas.getContext('2d');
        const w = canvas.width = canvas.offsetWidth;
        const h = canvas.height = 180;

        const prices = history.map(r => r.price);
        const labels = history.map(r => {
            const d = new Date(r.checked_at);
            return d.toLocaleDateString('en-PK', { day: 'numeric', month: 'short' });
        });

        const minP = Math.min(...prices) - 5;
        const maxP = Math.max(...prices) + 5;
        const range = maxP - minP || 1;

        const padL = 50, padR = 16, padT = 20, padB = 30;
        const chartW = w - padL - padR;
        const chartH = h - padT - padB;

        // Background
        ctx.fillStyle = '#f8fafc';
        ctx.fillRect(0, 0, w, h);

        // Grid lines
        ctx.strokeStyle = '#e2e8f0';
        ctx.lineWidth = 1;
        for (let i = 0; i <= 4; i++) {
            const y = padT + (chartH / 4) * i;
            ctx.beginPath();
            ctx.moveTo(padL, y);
            ctx.lineTo(w - padR, y);
            ctx.stroke();

            // Price labels
            const val = maxP - (range / 4) * i;
            ctx.fillStyle = '#64748b';
            ctx.font = '10px system-ui, sans-serif';
            ctx.textAlign = 'right';
            ctx.fillText('Rs ' + val.toFixed(0), padL - 6, y + 4);
        }

        // Draw line
        ctx.strokeStyle = '#004D40';
        ctx.lineWidth = 2.5;
        ctx.beginPath();

        const points = [];
        for (let i = 0; i < prices.length; i++) {
            const x = padL + (chartW / Math.max(prices.length - 1, 1)) * i;
            const y = padT + chartH - ((prices[i] - minP) / range) * chartH;
            points.push({ x, y });
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }
        ctx.stroke();

        // Fill area under line
        ctx.lineTo(points[points.length - 1].x, padT + chartH);
        ctx.lineTo(points[0].x, padT + chartH);
        ctx.closePath();
        ctx.fillStyle = 'rgba(0, 77, 64, 0.1)';
        ctx.fill();

        // Draw dots + labels
        for (let i = 0; i < points.length; i++) {
            ctx.beginPath();
            ctx.arc(points[i].x, points[i].y, 4, 0, Math.PI * 2);
            ctx.fillStyle = '#004D40';
            ctx.fill();
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 2;
            ctx.stroke();

            // Date labels
            ctx.fillStyle = '#64748b';
            ctx.font = '9px system-ui, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(labels[i], points[i].x, h - 6);
        }

        // Current price label
        ctx.fillStyle = '#0f172a';
        ctx.font = 'bold 11px system-ui, sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText('Rs ' + prices[prices.length - 1], points[points.length - 1].x + 8, points[points.length - 1].y + 4);

    } catch (e) {
        console.error('Chart error:', e);
    }
}

/* ---------- PRINCIPAL: HYBRID SHIFT PREDICTOR ---------- */

function generateHybridTimetable() {
    const output = document.getElementById('schedule-output');
    if (!output) return;

    output.innerHTML = `<p style="color: var(--text-muted);">Activating hybrid schedule...</p>`;

    fetch('/api/toggle-hybrid', { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            if (data.active) {
                output.innerHTML = `
                    <div style="color: #065f46; background-color: #d1fae5; padding: 12px; border-radius: 8px; margin-bottom: 12px; font-weight: 600;">
                        <i class="fa-solid fa-circle-check"></i> Hybrid Schedule ACTIVATED at Rs ${data.petrol_at_trigger}/L
                    </div>
                    <p style="margin: 0; font-size: 0.875rem; line-height: 1.5;">
                        <strong>Group A (Primary):</strong> Mon / Wed / Fri (Physical)<br>
                        <strong>Group B (Secondary):</strong> Tue / Thu / Sat (Physical)<br>
                        <strong>Online Days:</strong> Tue / Thu<br>
                        <strong>Est. Parent Savings:</strong> 40% transport cost cut.
                    </p>
                `;
            } else {
                output.innerHTML = `
                    <div style="color: #92400e; background-color: #fef3c7; padding: 12px; border-radius: 8px; font-weight: 600;">
                        <i class="fa-solid fa-circle-xmark"></i> Hybrid Schedule Deactivated
                    </div>
                    <p style="margin: 8px 0 0; font-size: 0.875rem;">Back to 5-day physical schedule.</p>
                `;
            }
        })
        .catch(err => {
            output.innerHTML = `<p style="color: #ef4444;">Failed to toggle hybrid: ${err}</p>`;
        });
}

/* ---------- INIT ---------- */

// Start fuel price polling on any page that has the live-price element
if (document.getElementById('live-price')) {
    _startFuelPolling();
}

// Load petrol history chart on principal page
loadPetrolChart();
