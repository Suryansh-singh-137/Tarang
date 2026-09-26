"""
sms_sender.py
-------------
Outbound SMS notification dispatcher using Twilio API.
Dispatches critical maritime emergency alerts (such as geofence border crossings
and severe cyclone warnings) directly to fishermen's mobile phones via SMS text,
complementing the WhatsApp channel for fishermen with basic phones.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

import config

logger = logging.getLogger("orca.sms_sender")


def format_breach_sms_message(breach_data: Dict[str, Any]) -> str:
    """
    Format a concise single-segment GSM-7 SMS alert message for a maritime boundary breach.
    Kept strictly under 120 characters (pure ASCII) to ensure Twilio trial accounts
    (which prepend a 38-character notice) deliver in exactly 1 segment without error 30044.
    """
    coords = breach_data.get("coordinates", {})
    lat = coords.get("lat", 0.0)
    lon = coords.get("lon", 0.0)
    dist = breach_data.get("distance_km", 0.0)
    bearing = breach_data.get("bearing_to_safety", 270)
    cardinal = breach_data.get("bearing_cardinal", "W")
    cg_number = breach_data.get("coastguard_number", "1554")

    # Strictly pure ASCII, <= 120 chars to guarantee single-segment delivery
    return (
        f"TARANG ALERT: BORDER BREACH! Pos {lat:.4f}N, {lon:.4f}E (+{dist:.1f}km). "
        f"Steer {cardinal} ({int(bearing)} deg) NOW. CG:{cg_number}"
    )


def send_sms_message(to_phone: str, message_body: str) -> Dict[str, Any]:
    """
    Send an outbound SMS message via Twilio API.
    Normalizes phone format (strips 'whatsapp:' prefix if present).
    If Twilio credentials or SMS number are not configured, operates in safe simulation mode.
    """
    import os
    import re
    from dotenv import dotenv_values
    from pathlib import Path

    raw_phone = str(to_phone or "").strip()
    if not raw_phone:
        return {"success": False, "error": "No phone number provided"}

    # Strip whatsapp: prefix if present — SMS uses plain E.164
    if raw_phone.lower().startswith("whatsapp:"):
        raw_phone = raw_phone[len("whatsapp:"):]

    clean_digits = re.sub(r"[^\d+]", "", raw_phone)
    if not clean_digits:
        return {"success": False, "error": "Invalid phone number"}

    if not clean_digits.startswith("+"):
        if len(clean_digits) == 10 and clean_digits.isdigit():
            clean_digits = f"+91{clean_digits}"
        else:
            clean_digits = f"+{clean_digits}"

    clean_phone = clean_digits

    # Always read dynamically from .env on disk first, falling back to os.environ / config
    base_dir = Path(__file__).parent.parent
    env_dict = {**dotenv_values(base_dir.parent / ".env"), **dotenv_values(base_dir / ".env")}
    account_sid = (env_dict.get("TWILIO_ACCOUNT_SID") or os.getenv("TWILIO_ACCOUNT_SID") or getattr(config, "TWILIO_ACCOUNT_SID", "")).strip()
    auth_token = (env_dict.get("TWILIO_AUTH_TOKEN") or os.getenv("TWILIO_AUTH_TOKEN") or getattr(config, "TWILIO_AUTH_TOKEN", "")).strip()
    sms_number = (
        env_dict.get("TWILIO_PHONE_NUMBER")
        or env_dict.get("TWILIO_SMS_NUMBER")
        or os.getenv("TWILIO_PHONE_NUMBER")
        or os.getenv("TWILIO_SMS_NUMBER")
        or getattr(config, "TWILIO_PHONE_NUMBER", "")
    ).strip()

    # If no SMS-capable number configured, simulate delivery safely
    if not sms_number:
        logger.warning(
            "[SMSSender] TWILIO_PHONE_NUMBER not configured. "
            "Simulating SMS dispatch to %s:\n%s",
            clean_phone,
            message_body[:200],
        )
        return {
            "success": True,
            "simulated": True,
            "to": clean_phone,
            "from": "(no SMS number configured)",
            "message_preview": message_body[:300],
            "note": "Simulated SMS dispatch. Add TWILIO_PHONE_NUMBER to .env for real SMS delivery.",
        }

    # If no credentials configured, simulate delivery safely
    if not account_sid or not auth_token:
        logger.warning(
            "[SMSSender] TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN not configured. "
            "Simulating SMS dispatch to %s:\n%s",
            clean_phone,
            message_body[:200],
        )
        return {
            "success": True,
            "simulated": True,
            "to": clean_phone,
            "from": sms_number,
            "message_preview": message_body[:300],
            "note": "Simulated SMS dispatch. Add TWILIO_ACCOUNT_SID & TWILIO_AUTH_TOKEN to .env for real SMS delivery.",
        }

    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        msg = client.messages.create(
            from_=sms_number,
            to=clean_phone,
            body=message_body,
        )
        logger.info("[SMSSender] SMS dispatched successfully! SID=%s to %s", msg.sid, clean_phone)
        return {
            "success": True,
            "simulated": False,
            "sid": msg.sid,
            "to": clean_phone,
            "from": sms_number,
            "status": msg.status,
        }
    except Exception as exc:
        err_str = str(exc)
        if "unverified" in err_str.lower() or "21608" in err_str:
            friendly_err = f"Number {clean_phone} is unverified in Twilio Trial account. Add it to Twilio Console -> Verified Caller IDs."
        else:
            friendly_err = err_str
        logger.exception("[SMSSender] Failed to send SMS via Twilio: %s", exc)
        return {
            "success": False,
            "simulated": False,
            "error": friendly_err,
            "to": clean_phone,
        }


def send_geofence_breach_sms(to_phone: str, breach_data: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function: formats breach data and dispatches SMS alert."""
    text = format_breach_sms_message(breach_data)
    return send_sms_message(to_phone, text)
