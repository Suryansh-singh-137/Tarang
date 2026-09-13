# Tarang V2.1 Marine Intelligence Platform — Data Sources & Capabilities

This document provides a comprehensive inventory of all marine data sources, providers, variables, update frequencies, staleness thresholds, and known limitations used in Tarang.

---

## 1. Weather Capability (`weather_agent`)

* **Provider / Service**: Open-Meteo Marine API & Forecast API (ECMWF ERA5 reanalysis + DWD ICON global numerical weather prediction models).
* **Provenance Tier**: `GLOBAL_MODEL` (`open_meteo` in source registry).
* **Primary Variables**:
  * `wave_height_m`: Significant wave height in meters ($H_s$).
  * `wave_direction_deg`: Wave propagation direction in degrees (0–360°).
  * `wind_speed_kmh`: Sustained surface wind speed at 10m in km/h.
  * `wind_speed_ms`: Wind speed in m/s.
  * `wind_direction_deg`: Wind direction in degrees (0–360°).
  * `sea_state`: Categorical description (calm, slight, moderate, rough, very rough, high).
  * `pressure_msl_hpa`: Atmospheric surface pressure reduced to Mean Sea Level (MSL) in hectopascals (hPa).
  * `visibility_km`: Horizontal surface visibility in kilometers.
* **Separation of Concerns**: Weather capability explicitly does **not** claim or emit Sea Surface Temperature (SST). SST is exclusively owned and reported by the PFZ / Marine Productivity capability.
* **Update Frequency**: Hourly operational NWP model cycle.
* **Max Allowed Staleness**: 12 hours.
* **Failure Handling**: Fail-closed / no fabrication. If the live fetch fails, the agent sets `execution_status = "failed"`, `data_status = "unavailable"`, and `data = {}`. Silent fallback fabrication (e.g. defaulting to 2.0m waves) is strictly prohibited.
* **Known Limitations**: Global atmospheric model output; does not replace real-time localized in-situ moored buoy observations or official IMD coastal warnings.

---

## 2. PFZ / Marine Productivity Capability (`pfz_agent`)

* **Provider / Service**:
  1. *Tier 1*: INCOIS Official Operational PFZ Advisory (`incois_pfz_official`).
  2. *Tier 2*: INCOIS ERDDAP Oceansat-2 Chlorophyll-a satellite grid (`incois_chl_proxy`).
* **Provenance Tier**: `OFFICIAL_OPERATIONAL` (if official advisory endpoint responds) or `PROXY` (Oceansat-2 historical ocean color satellite grid).
* **Primary Variables**:
  * `zones`: Array of identified productive fishing zones with coordinates `[lon, lat]` (RFC 7946 GeoJSON format).
  * `nearest_zone_km`: Distance from user's resolved query location to the closest zone in km.
  * `zone_count`: Number of active zones identified within the search radius.
  * `avg_chl`: Average chlorophyll-a concentration in $\text{mg/m}^3$.
  * `overall_productivity`: Qualitative rating (`low`, `moderate`, `high`).
  * `sst_celsius`: Sea Surface Temperature in °C (owned exclusively by PFZ).
* **Update Frequency**: Daily for official operational advisories; historical multi-day revisit cycle for satellite proxies.
* **Max Allowed Staleness**: 24 hours for official operational advisory; 168 hours (7 days) for satellite proxy.
* **Attribution & Safety Rules**:
  * When using Oceansat-2 CHL data, it is strictly disclosed as a *chlorophyll-based fishing potential proxy*, **not** an official daily PFZ advisory.
  * If both official and ERDDAP fetches fail, the agent sets `execution_status = "failed"`, `data_status = "unavailable"`, and does not fabricate fake zones.
* **Known Limitations**: Satellite ocean color measurements cannot penetrate cloud cover during monsoon periods; Oceansat-2 historical records represent proxy indicators.

---

## 3. Ocean / Tide / Water Level Capability (`ocean_agent`)

* **Provider / Service**: INCOIS / Survey of India (SOI) Tide Tables Harmonic Constituent Model (`incois_soi_tide_harmonic`).
* **Provenance Tier**: `OFFICIAL_OPERATIONAL`.
* **Primary Variables**:
  * `water_level_m`: Instantaneous astronomical water level in meters.
  * `datum`: Reference vertical datum, strictly defined as **`Chart Datum` (CD)** (Lowest Astronomical Tide baseline).
  * `current_phase`: Tidal state (`Rising (Flood Tide)`, `Falling (Ebb Tide)`, `High Slack Water`, `Low Slack Water`).
  * `next_high_tide`: Time (UTC & IST) and predicted peak height in meters CD.
  * `next_low_tide`: Time (UTC & IST) and predicted trough height in meters CD.
  * `tidal_range_m`: Mean tidal range in meters between high and low tide.
  * `tidal_stream_knots`: Estimated tidal current velocity in knots.
  * `data_type` / `prediction_type`: Strictly categorized as `harmonic_prediction`.
* **Separation of Concerns**: Water level above Chart Datum (meters) is strictly distinguished from Atmospheric MSL Pressure (hPa) and Sea Surface Temperature (°C).
* **Update Frequency**: Continuous deterministic harmonic computation based on principal lunar semi-diurnal ($M_2$) and solar constituents.
* **Max Allowed Staleness**: 24 hours.
* **Known Limitations**: Harmonic predictions reflect astronomical tides; meteorological storm surges or cyclone-induced sea surges must be assessed in conjunction with hazard advisories.

---

## 4. Hazard Capability (`hazard_agent`)

* **Provider / Service**:
  1. *Tier 1*: India Meteorological Department (IMD) official coastal warnings (`imd`).
  2. *Tier 2*: Global Disaster Alert and Coordination System (GDACS) Tropical Cyclone active alerts (`gdacs`).
  3. *Tier 3*: Open-Meteo WMO weather-code condition interpretation (`open_meteo_wmo`).
* **Provenance Tier**: Hierarchical: `OFFICIAL_OPERATIONAL` (IMD) → `SCIENTIFIC_MODEL` (GDACS) → `PROXY` (WMO weather codes).
* **Primary Variables**:
  * `overall_hazard_level`: `none`, `low`, `moderate`, `high`, `extreme`.
  * `active_warnings`: Array of alert tags (e.g. `cyclone_warning`, `rough_sea_advisory`, `thunderstorm`, `high_wind`).
  * `cyclone_warning`: Boolean flag.
  * `cyclone_name`, `cyclone_distance_km`, `cyclone_wind_kmh`, `cyclone_alert_level`: Distance and parameters of nearest tropical cyclone.
  * `lightning_advisory`, `rough_sea_advisory`: Boolean flags.
* **Update Frequency**: 6 hours for IMD advisories; real-time for GDACS cyclone feeds.
* **Max Allowed Staleness**: 6 hours for IMD/GDACS; 12 hours for WMO proxy.
* **Safety Rule**: Absence of an active warning in available data is phrased as *"no relevant warning found in available data"*, **never** as a guarantee of safe ocean conditions. Direct consultation of IMD/INCOIS is always recommended for cyclone advisories.
* **Known Limitations**: WMO weather codes are forecast proxies, not official government warnings.

---

## 5. Geofence / Maritime Boundary Capability (`geofence_agent`)

* **Provider / Service**: International Maritime Boundary Line (IMBL) bilateral agreement coordinates between India and Sri Lanka (1974 & 1976 treaties), loaded from `data/imbl_boundary.geojson` (`imbl_boundary_geojson`).
* **Provenance Tier**: `OFFICIAL_OPERATIONAL`.
* **Primary Variables**:
  * `distance_to_boundary_km`: Great-circle minimum geometric distance from the query point to the IMBL polyline in km.
  * `inside_boundary`: Boolean indicating whether vessel is on the Indian side of the maritime boundary.
  * `boundary_risk`: Proximity classification (`low`, `moderate`, `high`, `critical`).
  * `warning`: Explicit proximity warning string if distance < 20 km (e.g. critical alert when < 10 km).
  * `geometry_source`: String identifier (`data/imbl_boundary.geojson`).
* **Update Frequency**: Static international maritime boundary geometry.
* **Max Allowed Staleness**: Permanent / 8760 hours.
* **Known Limitations**: Applies to the Palk Strait / Gulf of Mannar maritime border. Does not track dynamic navy/coastguard prohibited zones or live fishing ban polygons.

---

## 6. Risk Capability (`risk_agent`)

* **Provider / Service**: Tarang Composite Marine Risk Model v1 (transparent deterministic weighted algorithm).
* **Formula & Weights**:
  $$\text{Risk Score} = 0.30 \times \text{WaveScore} + 0.20 \times \text{WindScore} + 0.30 \times \text{HazardScore} + 0.20 \times \text{BoundaryScore}$$
* **Primary Variables**:
  * `composite_score`: 0.0 (safest) to 100.0 (extreme hazard).
  * `risk_label`: `LOW` (0–25), `MODERATE` (26–50), `HIGH` (51–75), `EXTREME` (76–100), or `UNKNOWN`.
  * `components`: Itemized list of factor contributions with label, raw value, unit, component score, weight, and contribution points.
  * `recommendation`: Actionable advisory for small-craft fishermen.
  * `risk_sufficient_data`: Boolean flag.
* **Fail-Closed Contract (PRD §10 & §20)**:
  * If critical input data (Weather or Hazard) is unavailable, missing, or failed:
    * The risk model **fails closed**.
    * `composite_score` = `None`.
    * `risk_label` = `"UNKNOWN"`.
    * `status` = `"insufficient_data"`.
    * `execution_status` = `"failed"`.
    * `data_status` = `"unavailable"`.
    * `error` = `"CRITICAL_DATA_UNAVAILABLE"`.
    * No fallback numbers (e.g. 2.0m waves / 30km/h wind) are fabricated.
* **Known Limitations**: Navigational and decision-support aid only; does not constitute legal safety clearance.
