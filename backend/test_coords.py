import httpx

client = httpx.Client(headers={"User-Agent": "Tarang-MarineSafetyApp/1.0 (contact@tarang.app)"})

coords = [
    ("Delhi", 28.6139, 77.2090),
    ("Chennai", 13.0827, 80.2707),
    ("Offshore Chennai", 13.10, 80.35),
    ("Bengaluru", 12.9716, 77.5946),
]

for name, lat, lon in coords:
    try:
        r = client.get("https://nominatim.openstreetmap.org/reverse", params={
            "lat": lat,
            "lon": lon,
            "format": "json",
            "addressdetails": 1
        }, timeout=10.0)
        data = r.json()
        addr = data.get("address", {})
        print(f"=== {name} ({lat}, {lon}) ===")
        print("Display name:", data.get("display_name"))
        print("State:", addr.get("state"))
        print("Country code:", addr.get("country_code"))
    except Exception as e:
        print(f"Error for {name}: {e}")
