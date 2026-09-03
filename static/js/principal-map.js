/* ============================================================
   Safar-e-Taleem — Principal Live Safety Map

   The parent dashboard already draws one child's walk to school.
   This is the oversight view: EVERY child currently sharing a
   commute, on one map, refreshed on a poll.

   Data comes from GET /api/location/pod, which returns the full
   active set for a principal:
     { pod: [{ name, latitude, longitude, age_seconds,
               is_stale, is_sos, is_coordinator }],
       stale_after_seconds }

   Kept in its own file (not the page's inline script) so it can
   be reasoned about and tested independently.
   ============================================================ */
(function () {
    'use strict';

    const MAP_EL_ID = 'principal-map';
    const POLL_MS = 15000;

    // Used only until the first payload arrives; after that the map
    // frames whatever children are actually on the move.
    const DEFAULT_CENTER = [33.6844, 73.0479]; // Islamabad
    const DEFAULT_ZOOM = 12;

    let map = null;
    let layer = null;
    let timer = null;
    let haveFittedBounds = false;
    // Signature of the last payload we drew, so an unchanged poll does not tear
    // the markers down. Redrawing every 15 s flickers the map and slams shut any
    // popup the principal is in the middle of reading.
    let lastSignature = null;
    let openPopupId = null;

    function setStatus(message) {
        const el = document.getElementById('principal-map-status');
        if (el) el.textContent = message;
    }

    function setBadge(active, sosCount) {
        const el = document.getElementById('map-live-count');
        if (!el) return;
        if (sosCount > 0) {
            el.textContent = sosCount + ' SOS active';
            el.style.background = '#dc2626';
            el.style.color = '#fff';
        } else {
            el.textContent = active + ' on the move';
            el.style.background = '';
            el.style.color = '';
        }
    }

    // SOS red, stale grey, live green. Circle markers rather than pin
    // images: no icon assets to load, and they stay legible when twenty
    // of them overlap on one street.
    function styleFor(entry) {
        if (entry.is_sos) return { color: '#dc2626', fill: '#dc2626', radius: 10 };
        if (entry.is_stale) return { color: '#9ca3af', fill: '#9ca3af', radius: 6 };
        return { color: '#16a34a', fill: '#16a34a', radius: 7 };
    }

    function labelFor(entry) {
        const name = entry.name || 'A child';
        if (entry.is_sos) return '<strong>' + name + '</strong><br>SOS — needs help now';

        const age = typeof entry.age_seconds === 'number' ? entry.age_seconds : null;
        const when = age === null
            ? 'location unknown'
            : 'updated ' + (age < 60 ? age + 's' : Math.round(age / 60) + ' min') + ' ago';
        const state = entry.is_stale ? ' (stale)' : '';
        return '<strong>' + name + '</strong><br>' + when + state;
    }

    function initMap() {
        map = L.map(MAP_EL_ID).setView(DEFAULT_CENTER, DEFAULT_ZOOM);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors',
            maxZoom: 19,
            // Must be CORS. Without it Leaflet's <img> tiles come back opaque,
            // which the service worker's tile cache cannot store — so this map
            // would not work offline. See static/sw.js.
            crossOrigin: 'anonymous',
        }).addTo(map);
        layer = L.layerGroup().addTo(map);

        // Remember whose popup is open so a genuine data change can restore it
        // instead of leaving the principal staring at a marker that just closed.
        map.on('popupopen', function (e) {
            const src = e.popup.getSource();
            openPopupId = src ? src._safarUserId : null;
        });
        map.on('popupclose', function () { openPopupId = null; });
    }

    function render(entries) {
        const signature = entries.map(function (e) {
            return [e.user_id, e.latitude, e.longitude, e.is_sos, e.is_stale].join('|');
        }).join(';');

        // Nothing moved since the last poll: leave the markers (and any open
        // popup) exactly as they are.
        if (signature === lastSignature) return;

        // Capture before clearLayers() -- tearing the markers down fires
        // popupclose, which would otherwise wipe this.
        const reopenId = openPopupId;
        lastSignature = signature;
        layer.clearLayers();

        const points = [];
        const markersById = {};
        let sosCount = 0;

        entries.forEach(function (entry) {
            if (typeof entry.latitude !== 'number' || typeof entry.longitude !== 'number') return;
            if (entry.is_sos) sosCount += 1;

            const style = styleFor(entry);
            const marker = L.circleMarker([entry.latitude, entry.longitude], {
                radius: style.radius,
                color: style.color,
                weight: 2,
                fillColor: style.fill,
                fillOpacity: 0.85,
            });
            marker.bindPopup(labelFor(entry));
            marker._safarUserId = entry.user_id;
            layer.addLayer(marker);
            markersById[entry.user_id] = marker;
            points.push([entry.latitude, entry.longitude]);
        });

        setBadge(points.length, sosCount);

        if (points.length === 0) {
            setStatus('No child is sharing a commute right now. Markers appear as soon as a parent starts the walk.');
            return;
        }

        // Frame the children on the first load only. Re-fitting on every poll
        // would yank the map around while the principal is trying to look at
        // something, so afterwards we just update the markers in place.
        if (!haveFittedBounds) {
            if (points.length === 1) {
                map.setView(points[0], 16);
            } else {
                map.fitBounds(L.latLngBounds(points).pad(0.2));
            }
            haveFittedBounds = true;
        }

        if (reopenId != null && markersById[reopenId]) {
            markersById[reopenId].openPopup();
        }

        setStatus(points.length + ' live ' +
                  (sosCount > 0 ? '· ' + sosCount + ' SOS ' : '') +
                  '· refreshed ' + new Date().toLocaleTimeString());
    }

    async function refresh() {
        try {
            const res = await fetch('/api/location/pod', { headers: { 'Accept': 'application/json' } });
            if (!res.ok) {
                setStatus('Could not load live locations (HTTP ' + res.status + ').');
                return;
            }
            const data = await res.json();
            render(Array.isArray(data.pod) ? data.pod : []);
        } catch (e) {
            // Offline or server down. Keep the last markers on screen — a stale
            // map is still useful, and the poll will recover on its own.
            setStatus('Live locations unavailable — showing the last known positions.');
        }
    }

    function start() {
        const el = document.getElementById(MAP_EL_ID);
        // Not the principal page, or the Leaflet CDN was blocked. Fail quietly
        // rather than throwing on every other dashboard that loads this file.
        if (!el || typeof L === 'undefined') return;
        if (map) return; // already initialised

        initMap();
        refresh();
        timer = setInterval(refresh, POLL_MS);

        // Stop polling when the tab is hidden; a background tab does not need
        // to hit the server every 15 seconds.
        document.addEventListener('visibilitychange', function () {
            if (document.hidden) {
                clearInterval(timer);
                timer = null;
            } else if (!timer && map) {
                refresh();
                timer = setInterval(refresh, POLL_MS);
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', start);
    } else {
        start();
    }
})();
