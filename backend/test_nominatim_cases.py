import httpx
import time

client = httpx.Client(headers={"User-Agent": "Tarang-MarineSafetyApp/1.0 (contact@tarang.app)"})

test_points = [
    # 1. Coastal towns NOT in gazetteer
    ("Kumta (Karnataka)", 14.426, 74.408),
    ("Honnavar (Karnataka)", 14.280, 74.444),
    ("Colachel (Tamil Nadu)", 8.177, 77.256),
    ("Dhanushkodi (Tamil Nadu)", 9.176, 79.416),
    ("Nizampatnam (Andhra Pradesh)", 15.904, 80.668),
    ("Kalingapatnam (Andhra Pradesh)", 18.341, 84.127),
    ("Chandipur (Odisha)", 21.470, 87.020),
    ("Bakkhali (West Bengal)", 21.564, 88.256),
    ("Diglipur (North Andaman)", 13.266, 93.004),
    ("Minicoy (Lakshadweep)", 8.283, 73.033),
    ("Port Blair (Andaman)", 11.623, 92.727),
    
    # 2. Inland cities in coastal states
    ("Bengaluru (Karnataka)", 12.9716, 77.5946),
    ("Madurai (Tamil Nadu)", 9.9252, 78.1198),
    ("Coimbatore (Tamil Nadu)", 11.0168, 76.9558),
    ("Nagpur (Maharashtra)", 21.1458, 79.0882),
    ("Pune (Maharashtra)", 18.5204, 73.8567),
    
    # 3. Inland cities in non-coastal states
    ("New Delhi", 28.6139, 77.2090),
    ("Jaipur", 26.9124, 75.7873),
    ("Lucknow", 26.8467, 80.9462),
]

for name, lat, lon in test_points:
    time.sleep(1.0)
    try:
        r = client.get("https://nominatim.openstreetmap.org/reverse", params={
            "lat": lat,
            "lon": lon,
            "format": "json",
            "addressdetails": 1
        }, timeout=8.0)
        data = r.json()
        addr = data.get("address", {})
        print(f"=== {name} ({lat}, {lon}) ===")
        print("  State:", addr.get("state"))
        print("  County/District:", addr.get("county") or addr.get("state_district") or addr.get("district"))
        print("  Country:", addr.get("country_code"))
    except Exception as e:
        print(f"Error for {name}: {e}")
