import httpx
import config
import base64
import re
import io
import wave

sample_full_answer = """
Here is Tarang's marine safety assessment for Thoothukudi (now):

## MODERATE RISK
Risk score: 35/100 (decision-support only - not an official safety clearance)
Primary risk driver: Wave Height (contributing 12.0/100 to the total). Evidence coverage: 4/4 signal types.

Marine Conditions
- Wave height: 1.8 m (SSE)
- Wind speed: 28 km/h (SW)
- Sea state: Moderate
- Visibility: 10 km
  (Source: Open-Meteo Marine API)

Fishing Potential Indicator (Chlorophyll Proxy)
- 3 indicator zone(s) found
- Nearest PFZ indicator: 14 km away
- Average chlorophyll-a: 0.85 mg/m3 (productivity: moderate)
  - Zone at 8.85 N, 78.25 E (14 km, CHL=0.92 mg/m3)
  - Zone at 8.92 N, 78.35 E (22 km, CHL=0.78 mg/m3)
  (Source: INCOIS ERDDAP)
Data Quality Note: Fishing potential zones above are derived from INCOIS Oceansat-2 chlorophyll-a historical satellite data. This is a scientific proxy indicator, not a real-time official INCOIS PFZ advisory. For official PFZ advisories, consult the INCOIS portal at incois.gov.in.

Weather Condition Hazard Indicators
No relevant hazard warning found in available data. This does not guarantee absence of hazard.
  (Source: INCOIS SAMUDRA RSS)
Cyclone advisory: Real-time cyclone warnings require direct consultation with IMD or INCOIS. The above represents weather-condition hazard indicators only.

Maritime Boundary
Nearest international maritime boundary is 42.5 km away. Safe distance from international border. (Source: INCOIS Geofence)

Overall Risk Assessment
Score: 35/100 (MODERATE)
- Wave Height: 40/100 (Weight: 30%, Contribution: 12.0 pts)
- Wind Speed: 50/100 (Weight: 20%, Contribution: 10.0 pts)
- Hazard Level: 0/100 (Weight: 30%, Contribution: 0.0 pts)
- Boundary Proximity: 0/100 (Weight: 20%, Contribution: 0.0 pts)

Conditions appear manageable for mechanized vessels. Small traditional craft should exercise caution.

Data Sources and Evidence
- Open-Meteo Marine: Significant wave height 1.8m, Wind speed 28 km/h
- INCOIS SAMUDRA: No active cyclone bulletin for Gulf of Mannar

Data Freshness and Quality
- Weather: Live
- PFZ: Historical Proxy
- Hazard: Live
- Geofence: Live
- Geospatial: Computed

Disclaimer: This is a decision-support assessment, not an official safety clearance. Tarang assesses available conditions as a navigational aid. Always follow advisories from IMD, INCOIS, and the Indian Coast Guard before departing.
"""

def clean_and_chunk(text: str, max_chunk_len: int = 450) -> list[str]:
    text = re.sub(r'[*#_~`|]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    curr = ""
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if len(curr) + len(s) + 1 <= max_chunk_len:
            curr = f"{curr} {s}".strip()
        else:
            if curr:
                chunks.append(curr)
            while len(s) > max_chunk_len:
                sub = s[:max_chunk_len]
                last_space = sub.rfind(" ")
                if last_space > 0:
                    chunks.append(s[:last_space].strip())
                    s = s[last_space:].strip()
                else:
                    chunks.append(sub)
                    s = s[max_chunk_len:]
            curr = s
    if curr:
        chunks.append(curr)
    return chunks

chunks = clean_and_chunk(sample_full_answer)
print(f"Total chunks: {len(chunks)}")

# Group chunks in batches of max 3 (Sarvam limit)
batches = [chunks[i:i+3] for i in range(0, len(chunks), 3)]
print(f"Total batches of <= 3 chunks: {len(batches)}")

headers = {
    "API-Subscription-Key": config.SARVAM_API_KEY,
    "Content-Type": "application/json"
}

all_wav_bytes = []
for idx, batch in enumerate(batches):
    payload = {
        "inputs": batch,
        "target_language_code": "en-IN",
        "speaker": "simran",
        "pitch": 0,
        "pace": 1.0,
        "loudness": 1.5,
        "speech_sample_rate": 8000,
        "enable_preprocessing": True,
        "model": "bulbul:v3"
    }
    r = httpx.post("https://api.sarvam.ai/text-to-speech", json=payload, headers=headers, timeout=20.0)
    if r.status_code != 200:
        print(f"Batch {idx+1} failed:", r.text)
        break
    audios = r.json().get("audios", [])
    if audios:
        all_wav_bytes.append(base64.b64decode(audios[0]))
        print(f"Batch {idx+1} ({len(batch)} chunks) succeeded, received {len(all_wav_bytes[-1])} bytes")

# Combine WAV files
if all_wav_bytes:
    combined_frames = bytearray()
    params = None
    for b in all_wav_bytes:
        f = io.BytesIO(b)
        with wave.open(f, 'rb') as w:
            if params is None:
                params = w.getparams()
            combined_frames.extend(w.readframes(w.getnframes()))
    
    out_io = io.BytesIO()
    with wave.open(out_io, 'wb') as out_w:
        out_w.setparams(params)
        out_w.writeframes(combined_frames)
    
    final_wav = out_io.getvalue()
    duration = len(combined_frames) / (params.nchannels * params.sampwidth * params.framerate)
    print(f"SUCCESS! Combined WAV size: {len(final_wav)} bytes, Duration: {duration:.1f}s (~{duration/60:.1f} mins)")
