import base64
import logging
import re
from typing import Optional
import httpx

import config

logger = logging.getLogger(__name__)

def strip_markdown_for_speech(text: str) -> str:
    """Remove markdown symbols that confuse TTS models."""
    # Remove bold, italics, headers
    text = re.sub(r'[*#_~`]', '', text)
    # Remove emoji (basic range)
    text = re.sub(r'[^\w\s.,!?;:()\'"-]', '', text)
    # Condense whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def synthesize_speech(text: str, language: str) -> Optional[bytes]:
    """
    Calls Sarvam AI Bulbul V3 TTS API to convert text to speech.
    Returns wav bytes on success, or None on failure.
    """
    if not config.SARVAM_API_KEY:
        logger.warning("SARVAM_API_KEY not configured.")
        return None

    clean_text = strip_markdown_for_speech(text)
    
    # Map languages to Sarvam codes and recommended voices
    lang_map = {
        "en": ("en-IN", "avery"),
        "hi": ("hi-IN", "amartya"),
        "ta": ("ta-IN", "arvind")
    }
    
    target_lang, speaker = lang_map.get(language, ("hi-IN", "amartya"))
    
    url = "https://api.sarvam.ai/text-to-speech"
    headers = {
        "API-Subscription-Key": config.SARVAM_API_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "inputs": [clean_text],
        "target_language_code": target_lang,
        "speaker": speaker,
        "pitch": 0,
        "pace": 1.0,
        "loudness": 1.5,
        "speech_sample_rate": 8000,
        "enable_preprocessing": True,
        "model": "bulbul:v1"
    }
    
    try:
        with httpx.Client(timeout=6.0) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            audios = data.get("audios", [])
            if audios:
                # The audio is returned as a base64 encoded string
                audio_base64 = audios[0]
                return base64.b64decode(audio_base64)
            else:
                logger.error("Sarvam TTS returned empty audios array.")
                return None
    except Exception as exc:
        logger.error(f"Sarvam TTS API failed: {exc}")
        return None
