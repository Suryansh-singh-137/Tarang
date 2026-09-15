"""
whatsapp_formatter.py
---------------------
Formats Tarang multi-agent pipeline responses for WhatsApp readability:
- Converts Markdown (**bold**) to WhatsApp format (*bold*)
- Replaces markdown headers with clean WhatsApp bold lines
- Normalizes bullet lists
- Prepends clear safety/risk badges
- Keeps responses within comfortable reading length (<1600 chars)
"""

from __future__ import annotations

import re
from typing import Any


def format_for_whatsapp(raw_text: str, risk_data: dict[str, Any] | None = None) -> str:
    """Format final answer text and optional risk assessment for WhatsApp display."""
    if not raw_text:
        return "⚠️ Tarang could not generate a response for your query. Please try again with a specific coastal location."

    text = raw_text.strip()

    # 1. Convert Markdown headers (### Header -> *Header*)
    text = re.sub(r"^#{1,6}\s*(.+)$", r"*\1*", text, flags=re.MULTILINE)

    # 2. Convert standard markdown bold **bold** -> *bold*
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)

    # 3. Clean bullet points: replace "* " or "- " at start of line with "• "
    text = re.sub(r"^[*-]\s+", r"• ", text, flags=re.MULTILINE)

    # 4. Remove excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 5. Prepend Risk Badge if available
    if risk_data and isinstance(risk_data, dict):
        label = str(risk_data.get("risk_label", "")).upper()
        score = risk_data.get("composite_score")
        badge = ""
        if "LOW" in label:
            badge = "🟢 *RISK: LOW*"
        elif "MODERATE" in label or "MEDIUM" in label:
            badge = "🟡 *RISK: MODERATE*"
        elif "HIGH" in label:
            badge = "🔴 *RISK: HIGH*"

        if score is not None:
            badge += f" ({score:.0f}/100)"

        if badge and not text.startswith(badge):
            text = f"{badge}\n\n{text}"

    # 6. Safe length truncation (WhatsApp limit is 4096, but ~1600 is best for readability)
    if len(text) > 1600:
        truncated = text[:1550].rsplit("\n", 1)[0]
        text = truncated + "\n\n[...detailed report truncated for WhatsApp]"

    return text
