"""
Safar-e-Taleem — Curriculum Delivery Channels (SMS / WhatsApp / IVR)
====================================================================

Routes each channel to a real provider when configured, and falls back to
the offline simulation otherwise (so the demo always works with zero setup):

  • SMS       → any Pakistani HTTP SMS gateway (SMS4Connect-style request
                shape: user / pwd / sender / receiver / text). Configure:
                  SMS_GATEWAY_URL, SMS_GATEWAY_USERNAME,
                  SMS_GATEWAY_PASSWORD, SMS_GATEWAY_SENDER
                Works with SMS4Connect, Jazz Business bulk SMS, Telenor
                gateways that expose a plain HTTP endpoint.

  • WhatsApp  → Meta WhatsApp Cloud API. Configure:
                  WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID

  • IVR       → simulated (plug a Twilio / Infobip / local voice provider
                into send_ivr when one is chosen).

Env vars are read at call time (not import time) so providers can be
enabled per-deployment without code changes. Every sender returns a dict
and NEVER raises — a provider outage must not break a broadcast.
"""
import os
import re
import logging
from datetime import datetime

import requests

logger = logging.getLogger('safar-e-taleem.notify')

WHATSAPP_GRAPH_URL = 'https://graph.facebook.com/v18.0/{phone_id}/messages'


# ---------------------------------------------------------
# PHONE HELPERS
# ---------------------------------------------------------

def normalize_pk_phone(raw):
    """
    Normalize a Pakistani mobile number to E.164 (+92XXXXXXXXXX).
    Accepts 03XXXXXXXXX, 92XXXXXXXXXX, +92XXXXXXXXXX, with dashes/spaces.
    Returns '' when no digits are present.
    """
    digits = re.sub(r'\D', '', str(raw or ''))
    if not digits:
        return ''
    if digits.startswith('92'):
        return '+' + digits
    if digits.startswith('0'):
        return '+92' + digits[1:]
    return '+' + digits


def _configured(*keys):
    """True when every listed env var is non-empty."""
    return all(os.getenv(key, '').strip() for key in keys)


def _simulated(prefix, preview):
    return {
        'status': 'delivered',
        'message_id': f'{prefix}{datetime.now().strftime("%Y%m%d%H%M%S%f")}',
        'preview': preview,
        'provider': 'simulated',
    }


# ---------------------------------------------------------
# CHANNEL SENDERS
# ---------------------------------------------------------

def send_sms(phone, content_preview):
    """
    SMS via a Pakistani HTTP gateway (SMS4Connect-style), else simulated.
    Gateway response body is stored in the preview so delivery logs show
    exactly what the provider answered.
    """
    if _configured('SMS_GATEWAY_URL', 'SMS_GATEWAY_USERNAME', 'SMS_GATEWAY_PASSWORD'):
        try:
            resp = requests.post(
                os.getenv('SMS_GATEWAY_URL'),
                data={
                    'user': os.getenv('SMS_GATEWAY_USERNAME'),
                    'pwd': os.getenv('SMS_GATEWAY_PASSWORD'),
                    'sender': os.getenv('SMS_GATEWAY_SENDER', 'SafarTaleem'),
                    'receiver': normalize_pk_phone(phone),
                    'text': content_preview[:480],
                },
                timeout=8,
            )
            body = (resp.text or '')[:200]
            ok = resp.status_code == 200 and 'error' not in body.lower()
            return {
                'status': 'sent' if ok else 'failed',
                'message_id': f'SMSGW{datetime.now().strftime("%Y%m%d%H%M%S%f")}',
                'preview': body,
                'provider': 'sms-gateway',
            }
        except Exception as e:
            logger.warning('SMS gateway error: %s', e)
            return {
                'status': 'failed',
                'message_id': '',
                'preview': str(e)[:200],
                'provider': 'sms-gateway',
            }
    return _simulated('SMS', f'📱 {content_preview[:100]}')


def send_whatsapp(phone, content_preview):
    """WhatsApp via Meta Cloud API, else simulated."""
    if _configured('WHATSAPP_TOKEN', 'WHATSAPP_PHONE_NUMBER_ID'):
        try:
            resp = requests.post(
                WHATSAPP_GRAPH_URL.format(phone_id=os.getenv('WHATSAPP_PHONE_NUMBER_ID')),
                headers={'Authorization': f'Bearer {os.getenv("WHATSAPP_TOKEN")}'},
                json={
                    'messaging_product': 'whatsapp',
                    'to': normalize_pk_phone(phone),
                    'type': 'text',
                    'text': {'body': content_preview[:1024]},
                },
                timeout=8,
            )
            data = resp.json() if resp.content else {}
            msg_id = (data.get('messages') or [{}])[0].get('id', '')
            return {
                'status': 'sent' if resp.status_code == 200 else 'failed',
                'message_id': msg_id,
                'preview': f'📚 {content_preview[:150]}',
                'provider': 'whatsapp-cloud',
            }
        except Exception as e:
            logger.warning('WhatsApp Cloud error: %s', e)
            return {
                'status': 'failed',
                'message_id': '',
                'preview': str(e)[:200],
                'provider': 'whatsapp-cloud',
            }
    return _simulated('WA', f'📚 {content_preview[:150]}')


def send_ivr(phone, content_preview):
    """
    IVR (automated voice call) — simulated until a voice provider is chosen.
    In production: Twilio Voice, Infobip, or a local IVR provider.
    """
    return _simulated('IVR', f'📞 {content_preview[:120]}')


# ---------------------------------------------------------
# DISPATCHER
# ---------------------------------------------------------

CHANNELS = {
    'whatsapp': send_whatsapp,
    'sms': send_sms,
    'ivr': send_ivr,
}


def send_notification(channel, phone, content_preview):
    """
    Route a notification to its channel. Always returns a dict:
        {'status', 'message_id', 'preview', 'provider'}
    """
    sender = CHANNELS.get(channel)
    if not sender:
        return {'status': 'error', 'message': f'Unknown channel: {channel}'}
    return sender(phone, content_preview)
