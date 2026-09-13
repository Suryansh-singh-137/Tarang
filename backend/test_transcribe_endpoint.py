import requests
import io
import wave

# Test 1: Valid Audio
buf = io.BytesIO()
with wave.open(buf, 'wb') as wav_file:
    wav_file.setnchannels(1)
    wav_file.setsampwidth(2)
    wav_file.setframerate(16000)
    wav_file.writeframes(b'\x00\x00' * 16000)
wav_bytes = buf.getvalue()

resp1 = requests.post(
    "http://127.0.0.1:8000/transcribe",
    files={"audio": ("test.wav", wav_bytes, "audio/wav")}
)
print("Test 1 (Valid audio) -> Status:", resp1.status_code, "Body:", resp1.json())

# Test 2: Empty Audio
resp2 = requests.post(
    "http://127.0.0.1:8000/transcribe",
    files={"audio": ("empty.wav", b"", "audio/wav")}
)
print("Test 2 (Empty audio) -> Status:", resp2.status_code, "Body:", resp2.json())
