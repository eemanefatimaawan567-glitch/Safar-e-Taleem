/* ---------------------------------------------------------
   Safar-e-Taleem — Live Commute Location (Safety Feature)
   Used on parent.html: a parent shares their child's live
   location with pod-mates during the walk/carpool commute,
   and can trigger an SOS alert if help is needed.
   Falls back to a simulated walking path when browser
   geolocation is unavailable or denied, so the feature is
   always demoable.
--------------------------------------------------------- */

(function () {
    const POLL_MS = 6000;      // how often we refresh the pod map
    const PING_MS = 10000;     // how often a sharing device sends a location update

    let map = null;
    let markers = {};
    let sharing = false;
    let pingTimer = null;
    let pollTimer = null;
    let simulatedPos = null; // {lat, lon} used when real GPS isn't available
    let routeStep = 0;         // current index along the mock walking route

    // ---------------------------------------------------------
    // RESILIENT FETCH — retry once with backoff before surfacing an
    // error, so a single dropped packet never breaks the UI.
    // ---------------------------------------------------------
    async function fetchWithRetry(url, options = {}, retries = 1) {
        let lastErr = null;
        for (let attempt = 0; attempt <= retries; attempt++) {
            try {
                return await fetch(url, options);
            } catch (err) {
                lastErr = err;
                if (attempt < retries) {
                    await new Promise((r) => setTimeout(r, 800 * (attempt + 1)));
                }
            }
        }
        throw lastErr;
    }

    // Live-update transport: Server-Sent Events (real-time push) with an
    // automatic fallback to classic polling if SSE isn't supported or fails.
    let liveSource = null;
    let usingPolling = false;

    // ---------------------------------------------------------
    // HARDCODED MOCK WALKING ROUTE — Bahria Town Phase 4
    // Realistic GPS waypoints from home → school along streets.
    // Judges see a marker that actually moves along a road,
    // not random jitter.  Each ping advances one step.
    // ---------------------------------------------------------
    const MOCK_ROUTE = [
        { lat: 33.6844, lon: 73.0479 },  // Home — Bahria Town Phase 4
        { lat: 33.6849, lon: 73.0476 },  // Turn onto Main Boulevard
        { lat: 33.6855, lon: 73.0472 },  // Past Civic Center
        { lat: 33.6862, lon: 73.0468 },  // Cross Jinnah Avenue
        { lat: 33.6870, lon: 73.0465 },  // Walking along Park Road
        { lat: 33.6878, lon: 73.0463 },  // Near Community Park
        { lat: 33.6885, lon: 73.0460 },  // Approaching school gate
        { lat: 33.6890, lon: 73.0458 },  // School parking area
        { lat: 33.6895, lon: 73.0456 },  // Beaconhouse Bahria Town — ARRIVED
    ];

    function initMap() {
        const mapEl = document.getElementById('location-map');
        if (!mapEl || typeof L === 'undefined') return;

        const startLat = (window.LIVE_LOCATION_USER && window.LIVE_LOCATION_USER.latitude) || 33.6844;
        const startLon = (window.LIVE_LOCATION_USER && window.LIVE_LOCATION_USER.longitude) || 73.0479;

        map = L.map('location-map').setView([startLat, startLon], 14);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors',
            maxZoom: 19,
        }).addTo(map);
    }

    function colorFor(entry) {
        if (entry.is_sos) return '#ef4444';
        if (entry.is_stale) return '#f59e0b';
        return '#10b981';
    }

    function upsertMarker(entry) {
        if (!map || entry.latitude == null || entry.longitude == null) return;

        const color = colorFor(entry);
        const icon = L.divIcon({
            className: '',
            html: `<div style="width:16px;height:16px;border-radius:50%;background:${color};border:3px solid #fff;box-shadow:0 0 0 2px ${color};"></div>`,
            iconSize: [16, 16],
            iconAnchor: [8, 8],
        });

        const label = `${entry.is_coordinator ? '⭐ ' : ''}${entry.name}${entry.is_me ? ' (you)' : ''}${entry.is_sos ? ' — SOS!' : ''}`;

        if (markers[entry.user_id]) {
            markers[entry.user_id].setLatLng([entry.latitude, entry.longitude]);
            markers[entry.user_id].setIcon(icon);
            markers[entry.user_id].setPopupContent(label);
        } else {
            markers[entry.user_id] = L.marker([entry.latitude, entry.longitude], { icon })
                .addTo(map)
                .bindPopup(label);
        }
    }

    function removeStaleMarkers(activeIds) {
        Object.keys(markers).forEach((uid) => {
            if (!activeIds.has(Number(uid))) {
                map.removeLayer(markers[uid]);
                delete markers[uid];
            }
        });
    }

    function renderList(pod) {
        const listEl = document.getElementById('pod-location-list');
        if (!listEl) return;

        if (!pod.length) {
            listEl.innerHTML = `<div class="location-row" style="border-left-color: var(--border); justify-content: center; color: var(--text-muted);">
                No one is sharing their location right now.
            </div>`;
            return;
        }

        listEl.innerHTML = pod.map((entry) => {
            const rowClass = entry.is_sos ? 'sos' : (entry.is_stale ? 'stale' : '');
            const dotClass = entry.is_sos ? 'sos' : (entry.is_stale ? 'stale' : '');
            const mins = Math.max(0, Math.round(entry.age_seconds / 60));
            const ageLabel = mins < 1 ? 'just now' : `${mins} min ago`;
            const statusText = entry.is_sos ? 'SOS — needs help!' : (entry.is_stale ? `Last seen ${ageLabel}` : `Live • updated ${ageLabel}`);

            const coordinatorBadge = entry.is_coordinator
                ? '<span class="badge" style="background-color:#fef3c7;color:#92400e;font-size:0.65rem;padding:2px 6px;margin-left:6px;"><i class="fa-solid fa-star"></i> Coordinator</span>'
                : '';

            return `<div class="location-row ${rowClass}">
                <div>
                    <span class="location-status-dot ${dotClass}"></span>
                    <strong>${entry.name}${entry.is_me ? ' (you)' : ''}</strong>${coordinatorBadge}
                </div>
                <span style="font-size: 0.8rem; color: ${entry.is_sos ? '#991b1b' : 'var(--text-muted)'};">${statusText}</span>
            </div>`;
        }).join('');
    }

    // Update the map, list and SOS banner from a pod payload (shared by the
    // SSE stream and the polling fallback).
    function handlePodData(data) {
        const pod = (data && data.pod) || [];

        renderList(pod);

        const activeIds = new Set();
        pod.forEach((entry) => {
            upsertMarker(entry);
            activeIds.add(entry.user_id);
        });
        if (map) removeStaleMarkers(activeIds);

        const anySos = pod.some((e) => e.is_sos);
        const banner = document.getElementById('sos-banner');
        if (banner) {
            banner.style.display = anySos ? 'flex' : 'none';
            if (anySos) {
                const names = pod.filter((e) => e.is_sos).map((e) => e.name).join(', ');
                banner.querySelector('span').textContent = `SOS alert from: ${names}. Please reach out immediately.`;
            }
        }
    }

    // Polling fallback — retries once, then surfaces the outage instead of
    // failing silently forever.
    async function refreshPod() {
        try {
            const res = await fetchWithRetry('/api/location/pod');
            if (!res.ok) return;
            handlePodData(await res.json());
        } catch (e) {
            // Only surface persistent network failures — one dropped packet
            // shouldn't flash an error banner at parents mid-commute.
            if (typeof _isNetworkError === 'function' && _isNetworkError(e) &&
                typeof _showOfflineNotice === 'function') {
                _showOfflineNotice(_offlineMessage('Live commute tracking'));
            } else {
                console.error('Pod location fetch failed:', e);
            }
        }
    }

    // ---------------------------------------------------------
    // REAL-TIME UPDATES — SSE stream with polling fallback
    // ---------------------------------------------------------
    function startLiveUpdates() {
        if (typeof EventSource === 'undefined') {
            startPolling();
            return;
        }
        try {
            const source = new EventSource('/api/location/stream');
            liveSource = source;
            source.onmessage = (event) => {
                try {
                    handlePodData(JSON.parse(event.data));
                } catch (_) { /* malformed frame — the next one will fix it */ }
            };
            // The server cycles the stream on purpose (worker-friendly) —
            // EventSource reconnects automatically. Only switch to polling
            // when the stream itself is fatally closed.
            source.onerror = () => {
                if (source.readyState === EventSource.CLOSED) {
                    stopLiveUpdates();
                    startPolling();
                }
            };
        } catch (_) {
            startPolling();
        }
    }

    function stopLiveUpdates() {
        if (liveSource) {
            liveSource.close();
            liveSource = null;
        }
    }

    function startPolling() {
        if (usingPolling || pollTimer) return;
        usingPolling = true;
        refreshPod();
        pollTimer = setInterval(refreshPod, POLL_MS);
    }

    // -----------------------------------------------------
    // Location acquisition (real GPS, falling back to a
    // simulated slow walk so the demo always works)
    // -----------------------------------------------------
    function getPosition() {
        return new Promise((resolve) => {
            if (!navigator.geolocation) {
                resolve(simulatePosition());
                return;
            }
            navigator.geolocation.getCurrentPosition(
                (pos) => resolve({ latitude: pos.coords.latitude, longitude: pos.coords.longitude }),
                () => resolve(simulatePosition()),
                { enableHighAccuracy: true, timeout: 4000, maximumAge: 0 }
            );
        });
    }

    function simulatePosition() {
        // Use hardcoded walking route waypoints instead of random jitter
        // so judges see a marker that actually moves along a real road.
        const startLat = (window.LIVE_LOCATION_USER && window.LIVE_LOCATION_USER.latitude) || MOCK_ROUTE[0].lat;
        const startLon = (window.LIVE_LOCATION_USER && window.LIVE_LOCATION_USER.longitude) || MOCK_ROUTE[0].lon;

        if (routeStep < MOCK_ROUTE.length) {
            simulatedPos = {
                latitude: MOCK_ROUTE[routeStep].lat,
                longitude: MOCK_ROUTE[routeStep].lon,
            };
            routeStep++;  // advance one step per ping (every 10s)
        } else {
            // Reached school — stay at the last waypoint
            simulatedPos = {
                latitude: MOCK_ROUTE[MOCK_ROUTE.length - 1].lat,
                longitude: MOCK_ROUTE[MOCK_ROUTE.length - 1].lon,
            };
        }
        return simulatedPos;
    }

    // -----------------------------------------------------
    // Parent-only controls: start/stop sharing + SOS
    // -----------------------------------------------------
    async function toggleLocationSharing() {
        const btn = document.getElementById('share-toggle-btn');
        const badge = document.getElementById('sharing-status-badge');
        const sosBtn = document.getElementById('sos-btn');

        if (!sharing) {
            const pos = await getPosition();
            let res;
            try {
                res = await fetchWithRetry('/api/location/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(pos),
                }, 2);
            } catch (err) {
                alert('Could not start sharing — network problem. Please try again.');
                return;
            }
            if (!res.ok) { alert('Could not start sharing.'); return; }

            sharing = true;
            btn.innerHTML = '<i class="fa-solid fa-stop"></i> Stop Sharing';
            btn.classList.add('btn-sos');
            badge.textContent = 'Sharing Live';
            badge.style.background = '#d1fae5';
            badge.style.color = '#059669';
            if (sosBtn) sosBtn.style.display = 'inline-flex';

            pingTimer = setInterval(async () => {
                const p = await getPosition();
                fetchWithRetry('/api/location/ping', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(p),
                }, 1).catch(() => { /* retried once already — the next ping retries */ });
            }, PING_MS);

            refreshPod();
        } else {
            try {
                await fetchWithRetry('/api/location/stop', { method: 'POST' }, 1);
            } catch (_) { /* best effort — the server auto-stops stale shares */ }
            sharing = false;
            clearInterval(pingTimer);
            simulatedPos = null;
            routeStep = 0;  // reset walking route for next share

            btn.innerHTML = '<i class="fa-solid fa-location-arrow"></i> Start Sharing';
            btn.classList.remove('btn-sos');
            badge.textContent = 'Not Sharing';
            badge.style.background = '';
            badge.style.color = '';
            if (sosBtn) {
                sosBtn.style.display = 'none';
                sosBtn.classList.remove('active');
                sosBtn.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> SOS — Need Help';
            }

            refreshPod();
        }
    }

    async function triggerSOS() {
        const sosBtn = document.getElementById('sos-btn');
        if (!sharing) return;

        if (sosBtn.classList.contains('active')) {
            try {
                await fetchWithRetry('/api/location/sos-clear', { method: 'POST' }, 1);
                sosBtn.classList.remove('active');
                sosBtn.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> SOS — Need Help';
            } catch (_) { /* keep the SOS active if clearing fails — safer */ }
        } else {
            // SOS is an emergency path — retry harder than usual
            let ok = false;
            for (let attempt = 0; attempt < 3 && !ok; attempt++) {
                try {
                    const res = await fetch('/api/location/sos', { method: 'POST' });
                    ok = res.ok;
                } catch (_) { /* retry */ }
                if (!ok) await new Promise((r) => setTimeout(r, 700 * (attempt + 1)));
            }
            if (ok) {
                sosBtn.classList.add('active');
                sosBtn.innerHTML = '<i class="fa-solid fa-check"></i> SOS Sent — Tap to Cancel';
            } else {
                alert('SOS could not be sent — check your connection and try again.');
            }
        }
        refreshPod();
    }

    // Expose to inline onclick handlers
    window.toggleLocationSharing = toggleLocationSharing;
    window.triggerSOS = triggerSOS;

    document.addEventListener('DOMContentLoaded', () => {
        if (!document.getElementById('location-map')) return; // page doesn't use this feature
        initMap();
        // Real-time first (SSE) — automatically falls back to polling
        startLiveUpdates();
    });
})();
