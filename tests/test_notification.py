"""Tests for modules/notification.py — provider routing, PK phone handling, fallbacks."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import requests

from modules import notification


class FakeResponse:
    def __init__(self, status_code=200, text='', payload=None):
        self.status_code = status_code
        self.text = text
        self._payload = payload
        self.content = text.encode() or b'{}'

    def json(self):
        return self._payload if self._payload is not None else {}


@pytest.fixture(autouse=True)
def clean_provider_env(monkeypatch):
    """Every test starts unconfigured (simulation mode)."""
    for key in (
        'SMS_GATEWAY_URL', 'SMS_GATEWAY_USERNAME', 'SMS_GATEWAY_PASSWORD',
        'SMS_GATEWAY_SENDER', 'WHATSAPP_TOKEN', 'WHATSAPP_PHONE_NUMBER_ID',
    ):
        monkeypatch.delenv(key, raising=False)
    yield


class TestNormalizePkPhone:
    @pytest.mark.parametrize('raw, expected', [
        ('03001234567', '+923001234567'),
        ('0300-1234567', '+923001234567'),
        ('0300 123 4567', '+923001234567'),
        ('+923001234567', '+923001234567'),
        ('923001234567', '+923001234567'),
        ('+92 300 1234567', '+923001234567'),
        ('', ''),
        (None, ''),
    ])
    def test_normalization(self, raw, expected):
        assert notification.normalize_pk_phone(raw) == expected


class TestDispatch:
    def test_unknown_channel(self):
        result = notification.send_notification('pigeon', '03001234567', 'hi')
        assert result['status'] == 'error'
        assert 'Unknown channel' in result['message']

    def test_simulation_whatsapp(self):
        result = notification.send_notification('whatsapp', '03001234567', 'study plan')
        assert result['status'] == 'delivered'
        assert result['message_id'].startswith('WA')
        assert result['provider'] == 'simulated'

    def test_simulation_sms(self):
        result = notification.send_notification('sms', '03001234567', 'study plan')
        assert result['status'] == 'delivered'
        assert result['message_id'].startswith('SMS')

    def test_simulation_ivr(self):
        result = notification.send_notification('ivr', '03001234567', 'study plan')
        assert result['status'] == 'delivered'
        assert result['message_id'].startswith('IVR')


class TestSmsGateway:
    def test_gateway_configured_sends_real_request(self, monkeypatch):
        monkeypatch.setenv('SMS_GATEWAY_URL', 'https://sms.example.pk/api/sendsms.php')
        monkeypatch.setenv('SMS_GATEWAY_USERNAME', 'safar')
        monkeypatch.setenv('SMS_GATEWAY_PASSWORD', 'secret')
        monkeypatch.setenv('SMS_GATEWAY_SENDER', 'SafarTaleem')

        captured = {}

        def fake_post(url, data=None, timeout=None):
            captured['url'] = url
            captured['data'] = data
            return FakeResponse(status_code=200, text='OK 100')

        monkeypatch.setattr(notification.requests, 'post', fake_post)

        result = notification.send_notification('sms', '03001234567', 'English packet ready')

        assert result['status'] == 'sent'
        assert result['provider'] == 'sms-gateway'
        assert captured['url'] == 'https://sms.example.pk/api/sendsms.php'
        assert captured['data']['receiver'] == '+923001234567'
        assert captured['data']['sender'] == 'SafarTaleem'
        assert 'English packet ready' in captured['data']['text']

    def test_gateway_http_error_marks_failed(self, monkeypatch):
        monkeypatch.setenv('SMS_GATEWAY_URL', 'https://sms.example.pk/api')
        monkeypatch.setenv('SMS_GATEWAY_USERNAME', 'u')
        monkeypatch.setenv('SMS_GATEWAY_PASSWORD', 'p')

        monkeypatch.setattr(
            notification.requests, 'post',
            lambda url, data=None, timeout=None: FakeResponse(status_code=500, text='error'),
        )
        result = notification.send_notification('sms', '03001234567', 'x')
        assert result['status'] == 'failed'

    def test_gateway_exception_never_raises(self, monkeypatch):
        monkeypatch.setenv('SMS_GATEWAY_URL', 'https://sms.example.pk/api')
        monkeypatch.setenv('SMS_GATEWAY_USERNAME', 'u')
        monkeypatch.setenv('SMS_GATEWAY_PASSWORD', 'p')

        def boom(url, data=None, timeout=None):
            raise requests.Timeout('gateway down')

        monkeypatch.setattr(notification.requests, 'post', boom)
        result = notification.send_notification('sms', '03001234567', 'x')
        assert result['status'] == 'failed'
        assert result['provider'] == 'sms-gateway'

    def test_partial_config_falls_back_to_simulation(self, monkeypatch):
        monkeypatch.setenv('SMS_GATEWAY_URL', 'https://sms.example.pk/api')
        # username/password missing → not configured → simulated
        result = notification.send_notification('sms', '03001234567', 'x')
        assert result['provider'] == 'simulated'


class TestWhatsAppCloud:
    def test_cloud_api_configured(self, monkeypatch):
        monkeypatch.setenv('WHATSAPP_TOKEN', 'EAAG-token')
        monkeypatch.setenv('WHATSAPP_PHONE_NUMBER_ID', '123456')

        captured = {}

        def fake_post(url, headers=None, json=None, timeout=None):
            captured['url'] = url
            captured['headers'] = headers
            captured['json'] = json
            return FakeResponse(
                status_code=200,
                payload={'messages': [{'id': 'wamid.HBgLMw=='}]},
            )

        monkeypatch.setattr(notification.requests, 'post', fake_post)

        result = notification.send_notification('whatsapp', '+923001234567', 'Math packet')

        assert result['status'] == 'sent'
        assert result['provider'] == 'whatsapp-cloud'
        assert result['message_id'] == 'wamid.HBgLMw=='
        assert '123456' in captured['url']
        assert captured['headers']['Authorization'] == 'Bearer EAAG-token'
        assert captured['json']['to'] == '+923001234567'
        assert 'Math packet' in captured['json']['text']['body']

    def test_cloud_api_failure_marks_failed(self, monkeypatch):
        monkeypatch.setenv('WHATSAPP_TOKEN', 'bad')
        monkeypatch.setenv('WHATSAPP_PHONE_NUMBER_ID', '123')

        def fake_post(url, headers=None, json=None, timeout=None):
            return FakeResponse(status_code=401, payload={'error': {'message': 'invalid'}})

        monkeypatch.setattr(notification.requests, 'post', fake_post)
        result = notification.send_notification('whatsapp', '03001234567', 'x')
        assert result['status'] == 'failed'

    def test_cloud_api_exception_never_raises(self, monkeypatch):
        monkeypatch.setenv('WHATSAPP_TOKEN', 't')
        monkeypatch.setenv('WHATSAPP_PHONE_NUMBER_ID', '1')

        def boom(url, headers=None, json=None, timeout=None):
            raise requests.ConnectionError('meta down')

        monkeypatch.setattr(notification.requests, 'post', boom)
        result = notification.send_notification('whatsapp', '03001234567', 'x')
        assert result['status'] == 'failed'
