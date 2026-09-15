"""
whatsapp_session.py
-------------------
In-memory session manager for WhatsApp conversations.
Tracks conversation history, last_parsed_intent, and last_results
keyed by the user's WhatsApp phone number.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import config

logger = logging.getLogger("orca.whatsapp_session")


class WhatsAppSessionStore:
    def __init__(self, ttl_seconds: int = config.WHATSAPP_SESSION_TTL_SECONDS):
        self.ttl_seconds = ttl_seconds
        self._sessions: dict[str, dict[str, Any]] = {}

    def get_session(self, phone: str) -> dict[str, Any]:
        """
        Retrieve existing session or return a fresh empty session if
        none exists or if the session has expired.
        """
        session = self._sessions.get(phone)
        if not session:
            return self._new_session(phone)

        # Check TTL
        last_active = session.get("last_active")
        if last_active:
            age = (datetime.now(timezone.utc) - last_active).total_seconds()
            if age > self.ttl_seconds:
                logger.info(f"[WhatsAppSession] Session for {phone} expired (age={age:.1f}s). Resetting.")
                return self._new_session(phone)

        return session

    def update_session(
        self,
        phone: str,
        conversation: list[dict],
        last_parsed_intent: dict | None,
        last_results: dict[str, Any],
    ) -> None:
        """Update the session state with the latest turn data."""
        capped_conversation = conversation[-config.MAX_CONVERSATION_TURNS:]
        self._sessions[phone] = {
            "conversation": capped_conversation,
            "last_parsed_intent": last_parsed_intent,
            "last_results": last_results or {},
            "last_active": datetime.now(timezone.utc),
        }
        logger.info(f"[WhatsAppSession] Updated session for {phone} ({len(capped_conversation)} turns)")

    def clear_session(self, phone: str) -> None:
        """Clear/reset session for a user."""
        if phone in self._sessions:
            del self._sessions[phone]

    def _new_session(self, phone: str) -> dict[str, Any]:
        new_sess = {
            "conversation": [],
            "last_parsed_intent": None,
            "last_results": {},
            "last_active": datetime.now(timezone.utc),
        }
        self._sessions[phone] = new_sess
        return new_sess


# Singleton instance
session_store = WhatsAppSessionStore()
