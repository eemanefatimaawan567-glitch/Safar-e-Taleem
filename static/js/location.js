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

    async function refreshPod() {
        try {
            const res = await fetch('/api/location/pod');
            if (!res.ok) return;
            const data = await res.json();
            const pod = data.pod || [];

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
        } catch (e) {
            // Silent fail — polling will retry
        }
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
        if (!simulatedPos) {
            simulatedPos = {
                latitude: (window.LIVE_LOCATION_USER && window.LIVE_LOCATION_USER.latitude) || 33.6844,
                longitude: (window.LIVE_LOCATION_USER && window.LIVE_LOCATION_USER.longitude) || 73.0479,
            };
        } else {
            // small jitter to look like a slow walk toward school
            simulatedPos = {
                latitude: simulatedPos.latitude + (Math.random() - 0.4) * 0.0006,
                longitude: simulatedPos.longitude + (Math.random() - 0.4) * 0.0006,
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
            const res = await fetch('/api/location/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(pos),
            });
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
                fetch('/api/location/ping', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(p),
                }).catch(() => {});
            }, PING_MS);

            refreshPod();
        } else {
            await fetch('/api/location/stop', { method: 'POST' });
            sharing = false;
            clearInterval(pingTimer);
            simulatedPos = null;

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
            await fetch('/api/location/sos-clear', { method: 'POST' });
            sosBtn.classList.remove('active');
            sosBtn.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> SOS — Need Help';
        } else {
            await fetch('/api/location/sos', { method: 'POST' });
            sosBtn.classList.add('active');
            sosBtn.innerHTML = '<i class="fa-solid fa-check"></i> SOS Sent — Tap to Cancel';
        }
        refreshPod();
    }

    // Expose to inline onclick handlers
    window.toggleLocationSharing = toggleLocationSharing;
    window.triggerSOS = triggerSOS;

    document.addEventListener('DOMContentLoaded', () => {
        if (!document.getElementById('location-map')) return; // page doesn't use this feature
        initMap();
        refreshPod();
        pollTimer = setInterval(refreshPod, POLL_MS);
    });
})();
