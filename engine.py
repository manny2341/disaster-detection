"""
engine.py — Disaster Detection Engine
Flood: Fetches real Sentinel-2 satellite imagery and detects water using NDWI.
Earthquake: Fetches real seismic events from the USGS Earthquake API.
"""

import os
import warnings
import numpy as np
import requests
import planetary_computer as pc
import pystac_client

warnings.filterwarnings("ignore")


# ── Catalogue connection ───────────────────────────────────────────────────────

def get_catalog():
    """Connect to Microsoft Planetary Computer STAC catalogue."""
    return pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=pc.sign_inplace,
    )


# ── Search for satellite imagery ──────────────────────────────────────────────

def search_sentinel2(lat: float, lon: float, date_range: str, max_cloud: int = 30):
    """
    Search for Sentinel-2 imagery around a location.
    Returns a list of matching satellite scenes, clearest first.
    """
    catalog = get_catalog()

    # Bounding box: ±0.5° around the point (~55 km box)
    bbox = [lon - 0.5, lat - 0.5, lon + 0.5, lat + 0.5]

    search = catalog.search(
        collections=["sentinel-2-l2a"],
        bbox=bbox,
        datetime=date_range,
        query={"eo:cloud_cover": {"lt": max_cloud}},
        sortby=[{"field": "properties.eo:cloud_cover", "direction": "asc"}],
        max_items=5,
    )

    return list(search.items())


# ── Download a single band ────────────────────────────────────────────────────

def fetch_band(item, band_name: str) -> np.ndarray:
    """Download one spectral band and return it as a 512x512 numpy array."""
    import rasterio
    from rasterio.enums import Resampling

    asset = item.assets.get(band_name)
    if asset is None:
        raise ValueError(f"Band '{band_name}' not found in this scene.")

    signed_href = pc.sign(asset.href)

    with rasterio.open(signed_href) as src:
        data = src.read(
            1,
            out_shape=(512, 512),
            resampling=Resampling.bilinear,
        ).astype(np.float32)

    return data


# ── NDWI flood detection ──────────────────────────────────────────────────────

def compute_ndwi(green: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """
    Normalised Difference Water Index.
    NDWI = (Green - NIR) / (Green + NIR)
    Values above 0.2 indicate water or flooded land.
    """
    denom = green + nir
    denom = np.where(denom == 0, 1e-6, denom)
    return (green - nir) / denom


def detect_flood(item) -> dict:
    """
    Run flood detection on one satellite scene.
    Returns NDWI grid, flood mask, flood percentage, bbox, and date.
    """
    green = fetch_band(item, "B03")   # Green band
    nir   = fetch_band(item, "B08")   # Near-Infrared band

    ndwi       = compute_ndwi(green, nir)
    flood_mask = ndwi > 0.2
    flood_pct  = float(np.sum(flood_mask) / flood_mask.size * 100)
    bbox       = item.bbox
    date       = item.datetime.strftime("%Y-%m-%d") if item.datetime else "Unknown"

    return {
        "ndwi":       ndwi,
        "flood_mask": flood_mask,
        "flood_pct":  round(flood_pct, 2),
        "bbox":       bbox,
        "date":       date,
        "item":       item,
    }


# ── Convert flood pixels to lat/lon coordinates ───────────────────────────────

def get_flood_coordinates(result: dict, sample_points: int = 200) -> list:
    """
    Convert flood mask pixels to real-world [lat, lon] points.
    Used by the map to highlight flooded areas.
    """
    mask = result["flood_mask"]
    bbox = result["bbox"]   # [min_lon, min_lat, max_lon, max_lat]

    rows, cols = np.where(mask)
    if len(rows) == 0:
        return []

    h, w = mask.shape
    lons = bbox[0] + (cols / w) * (bbox[2] - bbox[0])
    lats = bbox[1] + (rows / h) * (bbox[3] - bbox[1])

    coords = list(zip(lats.tolist(), lons.tolist()))
    if len(coords) > sample_points:
        step = len(coords) // sample_points
        coords = coords[::step]

    return coords


# ── Save NDWI image ───────────────────────────────────────────────────────────

def save_ndwi_image(result: dict, output_path: str = "outputs/ndwi.png") -> str:
    """Save a colour-coded NDWI image (blue = water, red = dry land)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs("outputs", exist_ok=True)

    fig, ax = plt.subplots(figsize=(6, 6))
    im = ax.imshow(result["ndwi"], cmap="RdYlBu", vmin=-1, vmax=1)
    plt.colorbar(im, ax=ax, label="NDWI  (blue = water)")
    ax.set_title(f"NDWI — {result['date']}\nFlooded area: {result['flood_pct']}%")
    ax.axis("off")
    plt.tight_layout()
    plt.savefig(output_path, dpi=100)
    plt.close()

    return output_path


# ── Full pipeline (called by app.py) ─────────────────────────────────────────

def run_detection(lat: float, lon: float, date_range: str, max_cloud: int = 30) -> dict:
    """
    Full pipeline: search → download → analyse → return results for the UI.

    Returns:
        success      : True or False
        error        : message if failed
        date         : scene capture date
        flood_pct    : % of area flagged as flooded
        flood_coords : list of [lat, lon] flood points for the map
        ndwi_path    : path to the saved NDWI image
        bbox         : scene bounding box
        scene_id     : satellite scene identifier
    """
    try:
        items = search_sentinel2(lat, lon, date_range, max_cloud)

        if not items:
            return {
                "success": False,
                "error":   (
                    "No satellite imagery found for this location and date range. "
                    "Try widening the date range or increasing the cloud cover limit."
                ),
            }

        best_item = items[0]   # lowest cloud cover
        result    = detect_flood(best_item)
        coords    = get_flood_coordinates(result)
        img_path  = save_ndwi_image(result)

        return {
            "success":      True,
            "date":         result["date"],
            "flood_pct":    result["flood_pct"],
            "flood_coords": coords,
            "ndwi_path":    img_path,
            "bbox":         result["bbox"],
            "scene_id":     best_item.id,
        }

    except Exception as e:
        return {
            "success": False,
            "error":   str(e),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# EARTHQUAKE DETECTION — USGS Earthquake API (free, real-time data)
# ═══════════════════════════════════════════════════════════════════════════════

USGS_API = "https://earthquake.usgs.gov/fdsnws/event/1/query"


def fetch_earthquakes(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    radius_km: int = 500,
    min_magnitude: float = 4.0,
) -> dict:
    """
    Fetch real earthquake events from the USGS API within a radius of a location.

    Args:
        lat / lon      : centre point
        start_date     : "YYYY-MM-DD"
        end_date       : "YYYY-MM-DD"
        radius_km      : search radius in kilometres
        min_magnitude  : only return quakes at or above this magnitude

    Returns:
        dict with success, list of earthquakes, and summary stats
    """
    try:
        params = {
            "format":       "geojson",
            "starttime":    start_date,
            "endtime":      end_date,
            "latitude":     lat,
            "longitude":    lon,
            "maxradiuskm":  radius_km,
            "minmagnitude": min_magnitude,
            "orderby":      "magnitude",
        }

        resp = requests.get(USGS_API, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        features = data.get("features", [])

        if not features:
            return {
                "success": False,
                "error":   (
                    f"No earthquakes found with magnitude ≥ {min_magnitude} "
                    f"within {radius_km} km of this location between {start_date} and {end_date}. "
                    "Try lowering the minimum magnitude or widening the date range."
                ),
            }

        earthquakes = []
        for f in features:
            props = f["properties"]
            coords = f["geometry"]["coordinates"]  # [lon, lat, depth]
            earthquakes.append({
                "lat":       coords[1],
                "lon":       coords[0],
                "depth_km":  round(coords[2], 1),
                "magnitude": props.get("mag", 0),
                "place":     props.get("place", "Unknown location"),
                "time":      props.get("time", 0),      # Unix ms timestamp
                "url":       props.get("url", ""),
                "alert":     props.get("alert", None),  # green/yellow/orange/red
                "tsunami":   props.get("tsunami", 0),
            })

        magnitudes  = [e["magnitude"] for e in earthquakes]
        largest     = max(earthquakes, key=lambda x: x["magnitude"])

        return {
            "success":        True,
            "earthquakes":    earthquakes,
            "count":          len(earthquakes),
            "max_magnitude":  round(max(magnitudes), 1),
            "avg_magnitude":  round(sum(magnitudes) / len(magnitudes), 2),
            "largest":        largest,
            "radius_km":      radius_km,
            "min_magnitude":  min_magnitude,
        }

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error":   f"Could not reach USGS API: {e}",
        }
    except Exception as e:
        return {
            "success": False,
            "error":   str(e),
        }


def magnitude_colour(mag: float) -> str:
    """Return a colour based on earthquake magnitude."""
    if mag >= 7.0:
        return "darkred"
    elif mag >= 6.0:
        return "red"
    elif mag >= 5.0:
        return "orange"
    elif mag >= 4.0:
        return "beige"
    else:
        return "green"


def magnitude_radius(mag: float) -> int:
    """Return a circle radius (pixels) scaled by magnitude."""
    return max(6, int((mag ** 2.2) * 1.5))
