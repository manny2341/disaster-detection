# Disaster Detection — Satellite & Seismic Analysis

A real-data disaster detection system built with Python and Streamlit. Detects floods using live satellite imagery and earthquakes using live seismic data.

---

## Features

### 🌊 Flood Detection
- Fetches real **ESA Sentinel-2** satellite imagery via Microsoft Planetary Computer
- Calculates **NDWI** (Normalised Difference Water Index) per pixel
- Highlights flooded areas as a heatmap on an interactive map
- Saves a colour-coded NDWI image (blue = water, red = dry land)

### 🔴 Earthquake Detection
- Queries the live **USGS Earthquake API** in real time
- Maps every earthquake as a circle — size and colour scaled by magnitude
- Lists the top 10 events with depth, location, and date
- Alert banner classifies severity: light / moderate / strong / major

---

## Preset Events

| Disaster | Event | Year |
|---|---|---|
| Flood | Bangladesh | 2024 |
| Flood | Pakistan | 2022 |
| Flood | Nigeria | 2022 |
| Flood | Thailand | 2024 |
| Earthquake | Turkey–Syria | 2023 |
| Earthquake | Morocco | 2023 |
| Earthquake | Japan (Noto) | 2024 |
| Earthquake | Taiwan | 2024 |
| Earthquake | Afghanistan | 2023 |

---

## Tech Stack

- **UI:** Streamlit
- **Maps:** Folium + streamlit-folium
- **Satellite data:** Microsoft Planetary Computer (Sentinel-2 L2A)
- **Seismic data:** USGS Earthquake API (free, no key needed)
- **Image processing:** Rasterio, NumPy, Matplotlib

---

## Quick Start

```bash
git clone https://github.com/manny2341/disaster-detection
cd disaster-detection
pip install -r requirements.txt
streamlit run app.py
```

Open `http://localhost:8501`

---

## Project Structure

```
disaster-detection/
├── app.py            # Streamlit UI — two tabs (flood / earthquake)
├── engine.py         # Detection logic — satellite download, NDWI, USGS API
├── requirements.txt  # Dependencies
├── data/             # Local cache for downloaded data
└── outputs/          # Saved NDWI images
```

---

## Author

[@manny2341](https://github.com/manny2341)
