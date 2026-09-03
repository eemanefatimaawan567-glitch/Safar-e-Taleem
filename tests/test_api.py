"""
Safar-e-Taleem — API & integration tests (Flask test client)
=============================================================
Exercises the app end-to-end: auth + CSRF, registration validation,
role-based authorization, the live-location / SOS safety flow, pod
coordination alerts, curriculum broadcast and the public data endpoints.

conftest gives every test a throwaway SQLite DB (auto-seeded with the 10
demo families), disables the network and turns rate limiting off — except
in TestRateLimiting, which re-enables it deliberately.
"""
import os
import sys
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module
from tests.conftest import get_csrf_token, login


AYESHA = 'ayesha@demo.com'       # Bahria pod coordinator (device owner, id 1)
HASSAN = 'hassan@demo.com'       # Bahria pod member (no device, id 2)
PRINCIPAL = 'principal@demo.com'
DEMO_PASSWORD = 'demo123'

# Coordinates inside the seeded Bahria Town Phase 8 cluster
BAHRIA = {'latitude': 33.5350, 'longitude': 73.1545}


@pytest.fixture(autouse=True)
def _offline_notifications(monkeypatch):
    """Force simulation mode — API tests must never reach a real provider."""
    for key in ('SMS_GATEWAY_URL', 'SMS_GATEWAY_USERNAME', 'SMS_GATEWAY_PASSWORD',
                'SMS_GATEWAY_SENDER', 'WHATSAPP_TOKEN', 'WHATSAPP_PHONE_NUMBER_ID'):
        monkeypatch.delenv(key, raising=False)


def login_as(client, email, password=DEMO_PASSWORD):
    return login(client, email, password)


# --- direct-DB helpers (clean shared state between tests) ------------------

def _clear_shares():
    with app_module.app.app_context():
        app_module.db.session.query(app_module.LocationShare).delete(synchronize_session=False)
        app_module.db.session.commit()


def _clear_hybrid():
    with app_module.app.app_context():
        app_module.db.session.query(app_module.HybridSchedule).delete(synchronize_session=False)
        app_module.db.session.commit()


def _reset_petrol_table():
    with app_module.app.app_context():
        app_module.db.session.query(app_module.PetrolPrice).delete(synchronize_session=False)
        app_module.db.session.add(app_module.PetrolPrice(price=343.00, source='seed'))
        app_module.db.session.commit()


def _delete_users(*emails):
    with app_module.app.app_context():
        app_module.db.session.query(app_module.User).filter(
            app_module.User.email.in_(emails)).delete(synchronize_session=False)
        app_module.db.session.commit()


# ============================================================
# 1. PUBLIC PAGES
# ============================================================
class TestPublicPages:
    def test_index(self, client):
        response = client.get('/')
        assert response.status_code == 200
        assert b'Safar-e-Taleem' in response.data

    def test_login_page_has_csrf(self, client):
        response = client.get('/login')
        assert response.status_code == 200
        assert b'name="_csrf_token"' in response.data

    def test_register_page_has_phone_field(self, client):
        response = client.get('/register')
        assert response.status_code == 200
        assert b'name="phone"' in response.data

    def test_service_worker_root_scope(self, client):
        response = client.get('/sw.js')
        assert response.status_code == 200
        assert response.headers['Service-Worker-Allowed'] == '/'
        assert 'javascript' in response.headers['Content-Type']

    def test_curriculum_packs_endpoint(self, client):
        response = client.get('/api/curriculum-packs')
        assert response.status_code == 200
        packs = response.get_json()
        assert [p['level'] for p in packs] == ['primary', 'middle', 'secondary']


# ============================================================
# 2. AUTH FLOW
# ============================================================
class TestAuthFlow:
    def test_login_requires_csrf(self, client):
        response = client.post('/login', data={
            'email': AYESHA, 'password': DEMO_PASSWORD,
        })
        assert response.status_code == 403

    def test_login_parent_redirects_to_dashboard(self, client):
        response = login_as(client, AYESHA)
        assert response.status_code == 302
        assert response.headers['Location'].endswith('/parent')

    def test_login_principal_redirects(self, client):
        response = login_as(client, PRINCIPAL)
        assert response.status_code == 302
        assert response.headers['Location'].endswith('/principal')

    def test_login_wrong_password(self, client):
        response = login_as(client, AYESHA, 'wrong-password')
        assert response.status_code == 200
        assert b'Invalid email or password' in response.data

    def test_login_unknown_email(self, client):
        response = login_as(client, 'nobody@demo.com')
        assert response.status_code == 200
        assert b'Invalid email or password' in response.data

    def test_demo_login_parent(self, client):
        response = client.get('/demo-login/parent')
        assert response.status_code == 302
        assert response.headers['Location'].endswith('/parent')

    def test_demo_login_principal(self, client):
        response = client.get('/demo-login/principal')
        assert response.status_code == 302
        assert response.headers['Location'].endswith('/principal')

    def test_demo_login_unknown_role(self, client):
        response = client.get('/demo-login/judge')
        assert response.status_code == 302
        assert response.headers['Location'].endswith('/login')

    def test_logout_clears_session(self, client):
        login_as(client, AYESHA)
        assert client.get('/parent').status_code == 200
        assert client.get('/logout').status_code == 302
        # dashboard is no longer reachable without a session
        assert client.get('/parent').status_code == 302

    @pytest.mark.parametrize('url', [
        '/parent', '/principal', '/api/location/pod',
        '/api/location/stream', '/api/pod/messages',
    ])
    def test_protected_routes_redirect_anonymous(self, client, url):
        response = client.get(url)
        assert response.status_code == 302
        assert response.headers['Location'].endswith('/login')


# ============================================================
# 3. REGISTRATION VALIDATION
# ============================================================
class TestRegistration:
    NEW_EMAIL = 'newparent@example.com'
    NEW_CNIC = '35201-9999999-9'

    def _post(self, client, **overrides):
        token = get_csrf_token(client, '/register')
        form = {
            'name': 'New Parent',
            'email': self.NEW_EMAIL,
            'password': 'password123',
            'role': 'parent',
            'cnic': self.NEW_CNIC,
            'phone': '03451234567',
            'children_count': '2',
            'neighborhood': '',
            'school_name': '',
        }
        form.update(overrides)
        form['_csrf_token'] = token
        return client.post('/register', data=form)

    def test_register_requires_csrf(self, client):
        response = client.post('/register', data={
            'name': 'X', 'email': 'x@example.com', 'password': 'password123',
            'cnic': '35201-1111111-1', '_csrf_token': 'bad-token',
        })
        assert response.status_code == 403

    def test_missing_name_rejected(self, client):
        response = self._post(client, name='')
        assert response.status_code == 200
        assert b'Name and email are required' in response.data

    def test_invalid_email_rejected(self, client):
        response = self._post(client, email='not-an-email')
        assert b'Invalid email address' in response.data

    def test_short_password_rejected(self, client):
        response = self._post(client, password='abc')
        assert b'Password must be at least 8 characters' in response.data

    def test_invalid_role_rejected(self, client):
        response = self._post(client, role='superadmin')
        assert b'Invalid role' in response.data

    def test_invalid_cnic_rejected(self, client):
        response = self._post(client, cnic='12345')
        assert b'Invalid CNIC format' in response.data

    def test_invalid_phone_rejected(self, client):
        response = self._post(client, phone='021-123')
        assert b'Invalid phone number' in response.data

    def test_duplicate_email_rejected(self, client):
        response = self._post(client, email=AYESHA, cnic='35201-7777777-7')
        assert b'Email is already registered' in response.data

    def test_duplicate_cnic_rejected(self, client):
        response = self._post(client, cnic='37405-1234501-1')  # Ayesha's CNIC
        assert b'CNIC is already registered' in response.data

    def test_successful_registration(self, client):
        try:
            response = self._post(client)
            assert response.status_code == 302
            assert response.headers['Location'].endswith('/parent')
            with app_module.app.app_context():
                user = app_module.User.query.filter_by(email=self.NEW_EMAIL).first()
                assert user is not None
                assert user.phone == '03451234567'
                assert user.children_count == 2
        finally:
            _delete_users(self.NEW_EMAIL)

    def test_phone_optional(self, client):
        try:
            response = self._post(client, email='nophone@example.com',
                                  cnic='35201-8888888-8', phone='')
            assert response.status_code == 302
            with app_module.app.app_context():
                user = app_module.User.query.filter_by(email='nophone@example.com').first()
                assert user.phone == ''
        finally:
            _delete_users('nophone@example.com')


# ============================================================
# 4. PETROL PRICE ENDPOINTS + DEMO SPIKE
# ============================================================
class TestPetrolEndpoints:
    def test_petrol_price_shape(self, client):
        response = client.get('/api/petrol-price')
        assert response.status_code == 200
        payload = response.get_json()
        for key in ('price', 'current_price', 'previous_price', 'difference',
                    'percentage_change', 'direction', 'alert', 'source', 'checked_at'):
            assert key in payload
        assert payload['price'] > 0

    def test_petrol_history(self, client):
        response = client.get('/api/petrol-history')
        assert response.status_code == 200
        history = response.get_json()
        assert isinstance(history, list) and len(history) >= 1
        for entry in history:
            assert set(entry.keys()) == {'price', 'checked_at', 'source'}

    def test_demo_spike_requires_principal(self, client):
        login_as(client, AYESHA)
        response = client.post('/api/demo/petrol-spike', json={'price': 380})
        assert response.status_code == 403

    def test_demo_spike_then_reset(self, client):
        # Deterministic baseline: clear the table, plant yesterday's price
        with app_module.app.app_context():
            app_module.db.session.query(app_module.PetrolPrice).delete(synchronize_session=False)
            app_module.db.session.add(app_module.PetrolPrice(
                price=343.00, source='test-baseline',
                checked_at=datetime.utcnow() - timedelta(days=1)))
            app_module.db.session.commit()

        try:
            login_as(client, PRINCIPAL)
            spike = client.post('/api/demo/petrol-spike', json={'price': 375.5})
            assert spike.status_code == 200
            assert spike.get_json()['price'] == 375.5

            tracked = client.get('/api/petrol-price').get_json()
            assert tracked['price'] == 375.5
            assert tracked['source'] == 'demo-spike'
            assert tracked['previous_price'] == 343.00
            assert tracked['direction'] == 'increase'
            assert tracked['alert'] is True  # +9.5% is above the 2% alert line

            reset = client.post('/api/demo/petrol-reset')
            assert reset.status_code == 200
            assert reset.get_json()['price'] == 343.00
        finally:
            _reset_petrol_table()


# ============================================================
# 5. HYBRID SCHEDULE
# ============================================================
class TestHybridSchedule:
    def test_status_endpoint(self, client):
        response = client.get('/api/hybrid-status')
        assert response.status_code == 200
        assert isinstance(response.get_json()['active'], bool)

    def test_toggle_requires_login(self, client):
        assert client.post('/api/toggle-hybrid').status_code == 302

    def test_toggle_requires_principal(self, client):
        login_as(client, AYESHA)
        assert client.post('/api/toggle-hybrid').status_code == 403

    def test_principal_toggles_on_then_off(self, client):
        try:
            login_as(client, PRINCIPAL)
            on = client.post('/api/toggle-hybrid')
            assert on.status_code == 200
            assert on.get_json()['active'] is True

            off = client.post('/api/toggle-hybrid')
            assert off.status_code == 200
            assert off.get_json()['active'] is False

            status = client.get('/api/hybrid-status').get_json()
            assert status['active'] is False
        finally:
            _clear_hybrid()


# ============================================================
# 6. LIVE LOCATION + SOS SAFETY FLOW
# ============================================================
class TestLocationSafetyFlow:
    @pytest.fixture(autouse=True)
    def _clean_shares(self):
        _clear_shares()
        yield
        _clear_shares()

    def test_start_requires_login(self, client):
        assert client.post('/api/location/start', json=BAHRIA).status_code == 302

    def test_start_rejects_missing_coordinates(self, client):
        login_as(client, AYESHA)
        response = client.post('/api/location/start', json={})
        assert response.status_code == 400
        assert 'must be numbers' in response.get_json()['error']

    def test_start_rejects_non_numeric(self, client):
        login_as(client, AYESHA)
        response = client.post('/api/location/start',
                               json={'latitude': 'abc', 'longitude': 73.1})
        assert response.status_code == 400

    def test_start_rejects_out_of_range_latitude(self, client):
        login_as(client, AYESHA)
        response = client.post('/api/location/start',
                               json={'latitude': 123.4, 'longitude': 73.1})
        assert response.status_code == 400
        assert 'between -90 and 90' in response.get_json()['error']

    def test_start_rejects_out_of_range_longitude(self, client):
        login_as(client, AYESHA)
        response = client.post('/api/location/start',
                               json={'latitude': 33.5, 'longitude': 999})
        assert response.status_code == 400
        assert 'between -180 and 180' in response.get_json()['error']

    def test_start_success(self, client):
        login_as(client, AYESHA)
        response = client.post('/api/location/start', json=BAHRIA)
        assert response.status_code == 200
        payload = response.get_json()
        assert payload['started'] is True
        assert payload['started_at']

    def test_ping_requires_active_share(self, client):
        login_as(client, HASSAN)
        response = client.post('/api/location/ping', json=BAHRIA)
        assert response.status_code == 400
        assert 'not active' in response.get_json()['error']

    def test_ping_updates_coordinates(self, client):
        login_as(client, AYESHA)
        client.post('/api/location/start', json=BAHRIA)
        response = client.post('/api/location/ping',
                               json={'latitude': 33.5400, 'longitude': 73.1600})
        assert response.status_code == 200
        assert response.get_json()['updated'] is True

        pod = client.get('/api/location/pod').get_json()
        me = next(e for e in pod['pod'] if e['is_me'])
        assert me['latitude'] == pytest.approx(33.5400)
        assert me['longitude'] == pytest.approx(73.1600)

    def test_ping_after_stop_rejected(self, client):
        login_as(client, AYESHA)
        client.post('/api/location/start', json=BAHRIA)
        client.post('/api/location/stop')
        assert client.post('/api/location/ping', json=BAHRIA).status_code == 400

    def test_stop_without_share_is_idempotent(self, client):
        login_as(client, HASSAN)
        response = client.post('/api/location/stop')
        assert response.status_code == 200
        assert response.get_json()['stopped'] is True

    def test_pod_payload_self_and_podmates(self, client):
        login_as(client, AYESHA)
        client.post('/api/location/start', json=BAHRIA)
        login_as(client, HASSAN)
        client.post('/api/location/start', json={'latitude': 33.5360, 'longitude': 73.1555})

        login_as(client, AYESHA)
        pod = client.get('/api/location/pod').get_json()
        assert pod['stale_after_seconds'] == 300
        assert {e['name'] for e in pod['pod']} == {'Ayesha Khan', 'Hassan Ali'}

        me = next(e for e in pod['pod'] if e['name'] == 'Ayesha Khan')
        assert me['is_me'] is True
        assert me['is_coordinator'] is True  # lowest id in the Bahria pod
        assert me['is_sos'] is False
        assert me['is_stale'] is False

        mate = next(e for e in pod['pod'] if e['name'] == 'Hassan Ali')
        assert mate['is_me'] is False

    def test_principal_sees_every_active_commute(self, client):
        login_as(client, AYESHA)
        client.post('/api/location/start', json=BAHRIA)
        login_as(client, HASSAN)
        client.post('/api/location/start', json={'latitude': 33.5360, 'longitude': 73.1555})

        login_as(client, PRINCIPAL)
        pod = client.get('/api/location/pod').get_json()
        assert {e['name'] for e in pod['pod']} == {'Ayesha Khan', 'Hassan Ali'}
        assert all(e['is_me'] is False for e in pod['pod'])

    def test_sos_requires_active_sharing(self, client):
        login_as(client, HASSAN)
        assert client.post('/api/location/sos').status_code == 400

    def test_sos_dispatches_to_pod_and_principals(self, client):
        login_as(client, HASSAN)
        client.post('/api/location/start', json={'latitude': 33.5360, 'longitude': 73.1555})
        response = client.post('/api/location/sos')
        assert response.status_code == 200
        payload = response.get_json()
        assert payload['sos'] is True
        # 2 Bahria pod-mates (Ayesha, Sana) + 1 principal
        assert payload['notified'] == 3

        with app_module.app.app_context():
            logs = app_module.NotificationLog.query.filter_by(
                curriculum_level='sos-alert').all()
            recipients = {log.recipient_name for log in logs}
        assert {'Ayesha Khan', 'Sana Ahmed', 'Dr. Zainab Qureshi'} <= recipients

        # The SOS shows on the pod-mates' live map and in-app alert feed
        login_as(client, AYESHA)
        pod = client.get('/api/location/pod').get_json()
        hassan = next(e for e in pod['pod'] if e['name'] == 'Hassan Ali')
        assert hassan['is_sos'] is True
        messages = client.get('/api/pod/messages').get_json()['messages']
        assert any(m['level'] == 'sos-alert' for m in messages)

    def test_sos_clear(self, client):
        login_as(client, HASSAN)
        client.post('/api/location/start', json=BAHRIA)
        client.post('/api/location/sos')
        response = client.post('/api/location/sos-clear')
        assert response.status_code == 200
        assert response.get_json()['cleared'] is True

        login_as(client, AYESHA)
        pod = client.get('/api/location/pod').get_json()
        hassan = next((e for e in pod['pod'] if e['name'] == 'Hassan Ali'), None)
        if hassan:
            assert hassan['is_sos'] is False

    def test_sse_stream_headers_and_cycle(self, client):
        login_as(client, AYESHA)
        response = client.get('/api/location/stream')
        assert response.status_code == 200
        assert response.headers['Content-Type'].startswith('text/event-stream')
        assert response.headers['Cache-Control'] == 'no-cache'
        assert response.headers['X-Accel-Buffering'] == 'no'
        # conftest sets SSE_CYCLE_SECONDS=0 — the stream closes immediately
        # with a reconnect event; EventSource re-subscribes automatically.
        assert b'event: cycle' in response.data
        assert b'reconnect' in response.data


# ============================================================
# 7. POD COORDINATION ALERTS
# ============================================================
class TestPodCoordination:
    def test_pod_notify_requires_login(self, client):
        assert client.post('/api/pod/notify', json={'message': 'hi'}).status_code == 302

    def test_pod_notify_principal_forbidden(self, client):
        login_as(client, PRINCIPAL)
        response = client.post('/api/pod/notify', json={'message': 'hi'})
        assert response.status_code == 403
        assert 'Only parents' in response.get_json()['error']

    def test_pod_notify_non_coordinator_forbidden(self, client):
        login_as(client, HASSAN)
        response = client.post('/api/pod/notify', json={'message': 'hi'})
        assert response.status_code == 403
        assert 'Group Coordinator' in response.get_json()['error']

    def test_pod_notify_empty_message_rejected(self, client):
        login_as(client, AYESHA)
        response = client.post('/api/pod/notify', json={'message': '   '})
        assert response.status_code == 400

    def test_coordinator_alerts_reach_pod_members(self, client):
        login_as(client, AYESHA)
        response = client.post('/api/pod/notify',
                               json={'message': 'Van will be 10 minutes late'})
        assert response.status_code == 200
        payload = response.get_json()
        assert payload['sent'] == 2
        assert sorted(payload['recipients']) == ['Hassan Ali', 'Sana Ahmed']

        # Simulated delivery is logged and readable in-app by the members
        login_as(client, HASSAN)
        messages = client.get('/api/pod/messages').get_json()['messages']
        alert = next(m for m in messages if m['level'] == 'pod-alert')
        assert 'Van will be 10 minutes late' in alert['preview']
        assert alert['status'] == 'delivered'  # simulation mode

    def test_pod_messages_empty_for_principal(self, client):
        login_as(client, PRINCIPAL)
        response = client.get('/api/pod/messages')
        assert response.status_code == 200
        assert response.get_json() == {'messages': []}


# ============================================================
# 8. CURRICULUM BROADCAST + DELIVERY LOG
# ============================================================
class TestBroadcastCurriculum:
    def test_broadcast_requires_principal(self, client):
        login_as(client, AYESHA)
        response = client.post('/api/broadcast-curriculum',
                               json={'level': 'primary', 'channel': 'whatsapp'})
        assert response.status_code == 403

    def test_broadcast_invalid_channel(self, client):
        login_as(client, PRINCIPAL)
        response = client.post('/api/broadcast-curriculum',
                               json={'level': 'primary', 'channel': 'pigeon'})
        assert response.status_code == 400

    def test_broadcast_invalid_level(self, client):
        login_as(client, PRINCIPAL)
        response = client.post('/api/broadcast-curriculum',
                               json={'level': 'university', 'channel': 'sms'})
        assert response.status_code == 400

    def test_broadcast_reaches_unmatched_families(self, client):
        login_as(client, PRINCIPAL)
        response = client.post('/api/broadcast-curriculum',
                               json={'level': 'primary', 'channel': 'whatsapp'})
        assert response.status_code == 200
        payload = response.get_json()
        # Maryam (Satellite Town) is the only seeded family with no device
        # and no nearby host — she gets the offline curriculum delivery
        assert payload['sent'] == 1
        assert payload['channel'] == 'WhatsApp'
        assert '1 family' in payload['message']

    def test_notification_log_principal_only(self, client):
        login_as(client, AYESHA)
        assert client.get('/api/notification-log').status_code == 403

        login_as(client, PRINCIPAL)
        response = client.get('/api/notification-log')
        assert response.status_code == 200
        logs = response.get_json()
        assert isinstance(logs, list)
        for entry in logs:
            assert set(entry.keys()) == {'recipient', 'channel', 'preview',
                                         'level', 'status', 'sent_at'}


# ============================================================
# 9. ASK AMMI-ABBA CHAT
# ============================================================
class TestChatAssistant:
    def test_empty_message_gets_prompt(self, client):
        response = client.post('/api/ask-ammi-abba', json={'message': ''})
        assert response.status_code == 200
        assert response.get_json()['text_response'] == \
            'Please type or speak your question. I am here to help!'

    def test_question_answered_from_fallback(self, client):
        login_as(client, AYESHA)
        response = client.post('/api/ask-ammi-abba',
                               json={'message': 'school van ka kharcha kam kaise karein?'})
        assert response.status_code == 200
        payload = response.get_json()
        assert payload['text_response']
        # conftest clears DASHSCOPE_API_KEY → deterministic rule-based answer
        assert payload['source'] == 'fallback'

    def test_anonymous_can_ask(self, client):
        response = client.post('/api/ask-ammi-abba',
                               json={'message': 'petrol ki qeemat kya hai?'})
        assert response.status_code == 200
        assert response.get_json()['text_response']


# ============================================================
# 10. RATE LIMITING (re-enabled for this test only)
# ============================================================
class TestRateLimiting:
    def test_ask_ammi_abba_throttled_after_limit(self, client, monkeypatch):
        monkeypatch.delenv('RATE_LIMIT_DISABLED', raising=False)
        codes = []
        response = None
        for _ in range(31):  # the endpoint allows 30 requests / 60 s
            response = client.post('/api/ask-ammi-abba', json={'message': ''})
            codes.append(response.status_code)
        assert codes[:30] == [200] * 30
        assert codes[30] == 429
        assert 'Too many requests' in response.get_json()['error']
