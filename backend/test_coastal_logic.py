import math
import httpx
from typing import Tuple, Dict, Any, Optional

# Coastal States / UTs
COASTAL_STATES_UT = {
    "gujarat", "maharashtra", "goa", "karnataka", "kerala",
    "tamil nadu", "andhra pradesh", "odisha", "west bengal",
    "andaman and nicobar", "andaman & nicobar", "lakshadweep",
    "puducherry", "pondicherry",
    "daman and diu", "dadra and nagar haveli and daman and diu",
    "dadra and nagar haveli", "dadra & nagar haveli",
}

# Recognized Coastal Districts / Taluks / Regions of India
COASTAL_DISTRICTS = {
    # Gujarat
    "kutch", "kachchh", "morbi", "jamnagar", "devbhumi dwarka", "porbandar",
    "junagadh", "gir somnath", "amreli", "bhavnagar", "ahmedabad", "anand",
    "bharuch", "surat", "navsari", "valsad",
    # Maharashtra
    "palghar", "thane", "mumbai", "mumbai suburban", "mumbai city",
    "raigad", "ratnagiri", "sindhudurg",
    # Goa
    "north goa", "south goa", "goa",
    # Karnataka
    "uttara kannada", "north canara", "udupi", "dakshina kannada", "south canara",
    "kumta", "kumata", "honnavar", "bhatkal", "karwar", "ankola", "kundapura", "mangalore", "mangaluru",
    # Kerala
    "kasaragod", "kannur", "kozhikode", "malappuram", "thrissur",
    "ernakulam", "alappuzha", "kollam", "thiruvananthapuram",
    # Tamil Nadu
    "tiruvallur", "chennai", "chengalpattu", "viluppuram", "cuddalore",
    "mayiladuthurai", "nagapattinam", "tiruvarur", "thanjavur", "pudukkottai",
    "ramanathapuram", "thoothukudi", "tirunelveli", "kanniyakumari", "kanyakumari",
    "kalkulam", "rameswaram",
    # Andhra Pradesh
    "srikakulam", "vizianagaram", "visakhapatnam", "anakapalli", "kakinada",
    "konaseema", "dr. b.r. ambedkar konaseema", "west godavari", "krishna",
    "bapatla", "prakasam", "sri potti sriramulu nellore", "nellore", "tirupati",
    "nizampatnam", "gara",
    # Odisha
    "balasore", "baleshwar", "bhadrak", "kendrapara", "jagatsinghpur", "puri", "ganjam",
    "balaramgadi",
    # West Bengal
    "purba medinipur", "east midnapore", "south 24 parganas", "north 24 parganas",
    "howrah", "kolkata", "namkhana",
    # Islands & UTs (100% coastal)
    "andaman", "nicobar", "andaman and nicobar", "south andaman", "north and middle andaman", "nicobars",
    "diglipur", "port blair",
    "lakshadweep", "minicoy", "kavaratti", "agatti", "amini",
    "puducherry", "karaikal", "mahe", "yanam",
    "daman", "diu"
}

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def location_is_coastal(lat: float, lon: float, name: Optional[str] = None) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Validates whether coordinates belong to an Indian coastal zone or marine waters.
    Returns: (is_coastal, display_name, metadata)
    """
    # 1. Geographic envelope of India including all territorial waters & EEZ & islands:
    # Latitude: 6.0°N (Great Nicobar / Indira Point) to 25.0°N (Kutch / Sundarbans coastline limit)
    # Longitude: 68.0°E (Arabian Sea / Gujarat) to 94.5°E (Bay of Bengal / Andaman Sea)
    # If coordinates are north of 24.5°N in India (e.g. Delhi 28.6°, Punjab, Haryana, UP, Rajasthan):
    if lat > 24.5 or lat < 5.0 or lon < 65.0 or lon > 96.0:
        return False, name or f"Location ({lat:.2f}°N, {lon:.2f}°E)", {"reason": "outside_coastal_envelope"}

    # 2. Reverse geocode via Nominatim to inspect administrative boundaries
    try:
        with httpx.Client(timeout=6.0) as client:
            resp = client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={"lat": lat, "lon": lon, "format": "json", "addressdetails": 1},
                headers={"User-Agent": "Tarang-MarineSafetyApp/1.0 (contact@tarang.app)"}
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        # Fallback if network/geocoder is unreachable
        return True, name or f"Location ({lat:.2f}°N, {lon:.2f}°E)", {"reason": "geocoder_unreachable_permissive"}

    address = data.get("address", {})
    country_code = address.get("country_code", "").lower()
    state = address.get("state", "").lower()
    county = address.get("county", "").lower()
    district = address.get("state_district", "").lower() or address.get("district", "").lower()
    display_name = data.get("name") or address.get("city") or address.get("town") or address.get("village") or name or f"Location ({lat:.2f}°N, {lon:.2f}°E)"

    # Marine / Offshore check: if in Indian waters with no state, or in EEZ
    if country_code == "in" and not state:
        return True, display_name or "Offshore Coastal Waters", {"reason": "marine_territorial_waters"}

    # If foreign country and outside Indian EEZ
    if country_code and country_code != "in":
        return False, display_name, {"reason": "foreign_country", "country": country_code}

    # State-level check: Is the state a coastal state/UT?
    is_coastal_state = False
    for cs in COASTAL_STATES_UT:
        if cs in state:
            is_coastal_state = True
            break

    if not is_coastal_state:
        # State like Delhi, Rajasthan, UP, MP, Punjab, Bihar, Telangana, etc.
        return False, display_name, {"reason": "non_coastal_state", "state": state}

    # Island UTs are 100% coastal
    if any(isl in state for isl in ["andaman", "nicobar", "lakshadweep", "daman", "diu", "goa", "puducherry"]):
        return True, display_name, {"reason": "coastal_island_or_ut", "state": state}

    # Within mainland coastal states (TN, AP, Odisha, WB, Kerala, Karnataka, Maharashtra, Gujarat):
    # Check if district/county matches any known coastal district
    addr_tokens = f"{county} {district} {address.get('city', '')} {address.get('town', '')} {address.get('village', '')} {display_name}".lower()
    
    is_coastal_dist = False
    for cd in COASTAL_DISTRICTS:
        if cd in addr_tokens:
            is_coastal_dist = True
            break

    if is_coastal_dist:
        return True, display_name, {"reason": "coastal_district", "state": state}

    # If in coastal state but NOT a coastal district (e.g. Bangalore, Madurai, Coimbatore, Pune, Nagpur):
    return False, display_name, {"reason": "inland_district_in_coastal_state", "state": state, "district": district or county}

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
    ("Offshore Chennai (Marine)", 13.10, 80.35),
    
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

print(f"{'Location':<30} | {'Is Coastal?':<12} | {'Reason'}")
print("-" * 75)
for name, lat, lon in test_points:
    ok, disp, meta = location_is_coastal(lat, lon, name)
    print(f"{name:<30} | {str(ok):<12} | {meta.get('reason')} ({disp})")
