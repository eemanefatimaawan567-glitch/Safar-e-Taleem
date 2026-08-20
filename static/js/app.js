/* ============================================================
   Safar-e-Taleem — Shared Frontend Logic
   Full voice pipeline: mic input (STT) + spoken output (TTS)
   ============================================================ */

let isRecording = false;
let speechRecognition = null;
let _cachedVoice = null;

// Pick the best English voice (warm female preferred, always available)
function _pickEnglishVoice(voices) {
    return voices.find(v => /female|samantha|karen|victoria|zira/i.test(v.name) && v.lang.startsWith('en')) ||
           voices.find(v => v.lang === 'en-US') ||
           voices.find(v => v.lang.startsWith('en')) ||
           null;
}

// Preload voices
if (window.speechSynthesis) {
    speechSynthesis.onvoiceschanged = () => {
        _cachedVoice = _pickEnglishVoice(speechSynthesis.getVoices());
    };
    if (speechSynthesis.getVoices().length > 0) {
        speechSynthesis.onvoiceschanged();
    }
}

/* ---------- PETROL PRICE LIVE POLLING ---------- */

async function updatePrice() {
    try {
        const res = await fetch('/api/petrol-price');
        const data = await res.json();

        const priceEl = document.getElementById('live-price');
        if (priceEl) {
            priceEl.textContent = 'Rs ' + data.price + ' / L';
        }

        // Update direction on parent page
        const changeEl = document.querySelector('.petrol-change');
        if (changeEl && data.direction !== 'unchanged') {
            const color = data.direction === 'increase' ? '#fca5a5' : '#86efac';
            const dotColor = data.direction === 'increase' ? '#ef4444' : '#10b981';
            const sign = data.direction === 'increase' ? '+' : '';
            changeEl.innerHTML =
                '<span class="live-dot" style="background-color: ' + dotColor + ';"></span> ' +
                '<span style="color: ' + color + ';">Price ' + data.direction + 'd by Rs ' +
                Math.abs(data.difference) + ' (' + sign + data.percentage_change + '%)</span>';
        }

        // Update status text on principal page
        const statusEl = document.getElementById('status-text');
        if (statusEl && data.alert) {
            statusEl.innerHTML =
                '<span class="live-dot" style="background-color: #ef4444;"></span> ' +
                'High Alert: Critical Price Increase (+' + data.percentage_change + '%)';
        }
    } catch (e) {
        console.error('Error fetching price:', e);
    }
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
        speakResponse(data.text_response);
    } catch (e) {
        appendMessage("Sorry, I couldn't connect right now. Please try again.", 'bot');
    }
}

function handleKeyPress(e) {
    if (e.key === 'Enter') sendMessage();
}

/* ---------- VOICE: STT (Speech Recognition) + TTS (Speech Synthesis) ---------- */

function speakResponse(text) {
    if (!window.speechSynthesis) return;

    // Clean text for speech
    let clean = text
        .replace(/[\u{1F600}-\u{1F64F}\u{1F300}-\u{1F5FF}\u{1F680}-\u{1F6FF}\u{1F1E0}-\u{1F1FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\u{1F900}-\u{1F9FF}\u{200D}\u{FE0F}]/gu, '')
        .replace(/\n+/g, '. ')
        .replace(/\u2022/g, '')
        .replace(/Rs ([\d,]+)/g, '$1 rupees')
        .replace(/(\d+)%/g, '$1 percent')
        .trim();

    // Ensure voice loaded
    if (!_cachedVoice) {
        _cachedVoice = _pickEnglishVoice(speechSynthesis.getVoices());
    }

    speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(clean);
    utterance.lang = 'en-US';
    utterance.rate = 0.90;
    utterance.pitch = 1.0;
    if (_cachedVoice) utterance.voice = _cachedVoice;

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
    appendMessage(
        'Voice Info:\n' +
        'Total voices available: ' + voices.length + '\n' +
        'Currently using: ' + selected + '\n\n' +
        'All voices: ' + voices.slice(0, 10).map(v => v.name).join(', ') + (voices.length > 10 ? '...' : ''),
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

function recordVoiceCommand() {
    const { micBtn, micIcon } = _findMicElements();

    // Check browser support
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRec) {
        appendMessage('Voice not supported. Please use Chrome browser.', 'bot');
        return;
    }

    if (isRecording) {
        if (speechRecognition) speechRecognition.stop();
        isRecording = false;
        if (micBtn) micBtn.style.backgroundColor = '';
        if (micIcon) micIcon.className = 'fa-solid fa-microphone';
        return;
    }

    // Start speech recognition
    speechRecognition = new SpeechRec();
    // Use en-US for STT (universally supported, catches both English and Urdu loanwords)
    speechRecognition.lang = 'en-US';
    speechRecognition.interimResults = false;
    speechRecognition.maxAlternatives = 1;
    speechRecognition.continuous = false;

    speechRecognition.onstart = () => {
        isRecording = true;
        if (micBtn) micBtn.style.backgroundColor = '#ef4444';
        if (micIcon) micIcon.className = 'fa-solid fa-circle-stop';
    };

    speechRecognition.onresult = async (event) => {
        const transcript = event.results[0][0].transcript;
        appendMessage('🎤 ' + transcript, 'user');

        try {
            const res = await fetch('/api/ask-ammi-abba', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: transcript })
            });
            const data = await res.json();
            appendMessage(data.text_response, 'bot');
            speakResponse(data.text_response);
        } catch (e) {
            appendMessage('Sorry, could not process. Please try typing instead.', 'bot');
        }
    };

    speechRecognition.onerror = (event) => {
        if (event.error === 'no-speech') {
            appendMessage('Could not hear you. Press mic again and speak louder.', 'bot');
        } else if (event.error === 'not-allowed') {
            appendMessage('Mic permission denied. Allow microphone in browser settings.', 'bot');
        } else {
            appendMessage('Voice error. Please type your question instead.', 'bot');
        }
    };

    speechRecognition.onend = () => {
        isRecording = false;
        if (micBtn) micBtn.style.backgroundColor = '';
        if (micIcon) micIcon.className = 'fa-solid fa-microphone';
    };

    speechRecognition.start();
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
            ctx.font = '10px Inter, sans-serif';
            ctx.textAlign = 'right';
            ctx.fillText('Rs ' + val.toFixed(0), padL - 6, y + 4);
        }

        // Draw line
        ctx.strokeStyle = '#10b981';
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
        ctx.fillStyle = 'rgba(16, 185, 129, 0.1)';
        ctx.fill();

        // Draw dots + labels
        for (let i = 0; i < points.length; i++) {
            ctx.beginPath();
            ctx.arc(points[i].x, points[i].y, 4, 0, Math.PI * 2);
            ctx.fillStyle = '#10b981';
            ctx.fill();
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 2;
            ctx.stroke();

            // Date labels
            ctx.fillStyle = '#64748b';
            ctx.font = '9px Inter, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(labels[i], points[i].x, h - 6);
        }

        // Current price label
        ctx.fillStyle = '#0f172a';
        ctx.font = 'bold 11px Inter, sans-serif';
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

// Poll petrol price every 5 seconds on all pages
if (document.getElementById('live-price')) {
    setInterval(updatePrice, 5000);
}

// Load petrol history chart on principal page
loadPetrolChart();
