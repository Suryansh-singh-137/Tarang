"""
session.session_store
---------------------
Server-side conversation session manager for Tarang V2 architecture.

Maintains authoritative session state so historical query locations and
device locations cannot be desynchronized or spoofed by client-side state.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from location.models import DeviceLocation, ResolvedLocation

# Session TTL: 24 hours
SESSION_TTL_SECONDS = 86400


@dataclass
class SessionRecord:
    conversation_id: str
    device_location: Optional[DeviceLocation] = None
    last_query_location: Optional[ResolvedLocation] = None
    last_explicit_location: Optional[ResolvedLocation] = None
    last_results: Dict[str, Any] = field(default_factory=dict)
    last_parsed_intent: Optional[Dict[str, Any]] = None
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "device_location": self.device_location,
            "last_query_location": self.last_query_location,
            "last_explicit_location": self.last_explicit_location,
            "last_results": self.last_results,
            "last_parsed_intent": self.last_parsed_intent,
            "conversation_history": self.conversation_history,
            "updated_at": self.updated_at,
        }


# In-memory session cache: {conversation_id: SessionRecord}
_SESSIONS: Dict[str, SessionRecord] = {}


def get_or_create_session(conversation_id: Optional[str] = None) -> SessionRecord:
    """Retrieve an existing session or create a new one with a fresh UUID."""
    now = time.time()
    if conversation_id and conversation_id in _SESSIONS:
        record = _SESSIONS[conversation_id]
        record.updated_at = now
        return record

    cid = conversation_id if conversation_id and conversation_id.strip() else f"conv-{uuid.uuid4().hex[:12]}"
    record = SessionRecord(conversation_id=cid, updated_at=now)
    _SESSIONS[cid] = record
    _prune_expired_sessions()
    return record


def save_session(record: SessionRecord) -> None:
    """Persist session record update in server cache."""
    record.updated_at = time.time()
    _SESSIONS[record.conversation_id] = record


def clear_session(conversation_id: str) -> None:
    """Delete a session record."""
    if conversation_id in _SESSIONS:
        del _SESSIONS[conversation_id]


def _prune_expired_sessions() -> None:
    """Remove sessions that haven't been accessed within SESSION_TTL_SECONDS."""
    now = time.time()
    expired = [cid for cid, s in _SESSIONS.items() if now - s.updated_at > SESSION_TTL_SECONDS]
    for cid in expired:
        del _SESSIONS[cid]
