"""
Safar-e-Taleem — Low-Data Curriculum Delivery (WhatsApp/SMS/IVR Simulation)

Simulates pushing curriculum content to families without digital devices
via three channels:
  • WhatsApp: Rich text summary with subjects & key topics (simulated API call)
  • SMS:        Short text with today's main topic per subject (simulated API call)
  • IVR:        Automated voice call reading the day's study plan (simulated API call)

All messages are logged in the database (NotificationLog) for delivery tracking.
In production, replace the _send_* functions with actual API calls
(WhatsApp Business API, Twilio SMS, Twilio IVR, etc.).
"""
from datetime import datetime


# ---------------------------------------------------------
# CHANNEL SIMULATORS
# ---------------------------------------------------------

def send_whatsapp(phone, content_preview):
    """
    Simulate sending curriculum via WhatsApp Business API.
    In production: POST to https://graph.facebook.com/v18.0/{phone_id}/messages
    """
    return {
        "status": "delivered",
        "message_id": f"WA{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "preview": f"📚 {content_preview[:150]}",
    }


def send_sms(phone, content_preview):
    """
    Simulate sending curriculum summary via SMS.
    In production: Use Twilio, Telenor Bulk SMS, or Jazz SMS Gateway API.
    """
    return {
        "status": "delivered",
        "message_id": f"SMS{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "preview": f"📱 {content_preview[:100]}",
    }


def send_ivr(phone, content_preview):
    """
    Simulate an IVR (automated voice) call delivering curriculum.
    In production: Use Twilio Voice API or a local IVR provider like
    Infobip or Mobilink Enterprise.
    """
    return {
        "status": "delivered",
        "message_id": f"IVR{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "preview": f"📞 {content_preview[:120]}",
    }


# ---------------------------------------------------------
# DISPATCHER
# ---------------------------------------------------------

CHANNELS = {
    "whatsapp": send_whatsapp,
    "sms": send_sms,
    "ivr": send_ivr,
}


def send_notification(channel, phone, content_preview):
    """Route a notification to the correct channel simulator."""
    sender = CHANNELS.get(channel)
    if not sender:
        return {"status": "error", "message": f"Unknown channel: {channel}"}
    return sender(phone, content_preview)
