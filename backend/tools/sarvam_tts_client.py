import base64
import io
import logging
import re
from typing import Optional, List
import wave
import httpx

import config

logger = logging.getLogger(__name__)


def strip_markdown_for_speech(text: str) -> str:
    """Remove markdown symbols that confuse TTS models."""
    # Remove markdown headers, bold, italics, bullets, code marks, pipes
    text = re.sub(r'[*#_~`|]', ' ', text)
    # Condense whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def clean_and_chunk_text(text: str, max_chunk_len: int = 450) -> List[str]:
    """
    Split text into sentence-aware chunks that each respect Sarvam's 500-char limit.
    """
    clean_text = strip_markdown_for_speech(text)
    # Split on punctuation followed by space
    sentences = re.split(r'(?<=[.!?])\s+', clean_text)
    chunks: List[str] = []
    curr = ""

    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if len(curr) + len(s) + 1 <= max_chunk_len:
            curr = f"{curr} {s}".strip() if curr else s
        else:
            if curr:
                chunks.append(curr)
            # Handle exceptionally long single sentences
            while len(s) > max_chunk_len:
                sub = s[:max_chunk_len]
                last_space = sub.rfind(" ")
                if last_space > 0:
                    chunks.append(s[:last_space].strip())
                    s = s[last_space:].strip()
                else:
                    chunks.append(sub)
                    s = s[max_chunk_len:].strip()
            curr = s

    if curr:
        chunks.append(curr)

    return chunks


def synthesize_speech(text: str, language: str) -> Optional[bytes]:
    """
    Calls Sarvam AI Bulbul V3 TTS API to convert text to speech.
    Supports long text by chunking into <= 450 char sentences, batching up to
    3 chunks per request (Sarvam API limit), and stitching audio frames into a single WAV.
    Returns wav bytes on success, or None on failure.
    """
    if not config.SARVAM_API_KEY:
        logger.warning("SARVAM_API_KEY not configured.")
        return None

    chunks = clean_and_chunk_text(text)
    if not chunks:
        logger.warning("Empty text after markdown stripping.")
        return None

    # Sarvam enforces maximum 3 items in the inputs list per request
    batches = [chunks[i:i + 3] for i in range(0, len(chunks), 3)]

    # Map languages to Sarvam codes and recommended voices for bulbul:v3
    lang_map = {
        "en": ("en-IN", "simran"),
        "hi": ("hi-IN", "aditya"),
        "ta": ("ta-IN", "gokul"),
    }
    target_lang, speaker = lang_map.get(language, ("hi-IN", "aditya"))

    url = "https://api.sarvam.ai/text-to-speech"
    headers = {
        "API-Subscription-Key": config.SARVAM_API_KEY,
        "Content-Type": "application/json",
    }

    all_wav_parts: List[bytes] = []

    try:
        with httpx.Client(timeout=30.0) as client:
            for batch_idx, batch in enumerate(batches):
                payload = {
                    "inputs": batch,
                    "target_language_code": target_lang,
                    "speaker": speaker,
                    "pitch": 0,
                    "pace": 1.0,
                    "loudness": 1.5,
                    "speech_sample_rate": 8000,
                    "enable_preprocessing": True,
                    "model": "bulbul:v3",
                }
                resp = client.post(url, json=payload, headers=headers)
                resp.raise_for_status()

                data = resp.json()
                audios = data.get("audios", [])
                if not audios:
                    logger.error("Sarvam TTS returned empty audios for batch %d.", batch_idx)
                    return None

                all_wav_parts.append(base64.b64decode(audios[0]))

    except Exception as exc:
        logger.error(f"Sarvam TTS API failed: {exc}")
        return None

    if not all_wav_parts:
        return None

    if len(all_wav_parts) == 1:
        return all_wav_parts[0]

    # Combine multiple WAV chunks by stitching PCM frames
    try:
        combined_frames = bytearray()
        params = None

        for part in all_wav_parts:
            part_io = io.BytesIO(part)
            with wave.open(part_io, "rb") as w:
                if params is None:
                    params = w.getparams()
                combined_frames.extend(w.readframes(w.getnframes()))

        out_io = io.BytesIO()
        with wave.open(out_io, "wb") as out_w:
            out_w.setparams(params)
            out_w.writeframes(combined_frames)

        logger.info(
            "Stitched %d WAV audio batches into unified WAV (%d bytes)",
            len(all_wav_parts),
            len(out_io.getvalue()),
        )
        return out_io.getvalue()

    except Exception as exc:
        logger.error("Failed to stitch WAV audio parts: %s", exc)
        # Fallback to returning the first part
        return all_wav_parts[0]

