"""
app.py — Disaster Detection Streamlit UI
Run: streamlit run app.py
"""

import os
import sys
import streamlit as st
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(__file__))
from engine import run_detection, fetch_earthquakes, magnitude_colour, magnitude_radius

import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Disaster Detection — Satellite Analysis",
    page_icon="🛰️",
    layout="wide",
)

st.markdown("## 🛰️ Disaster Detection System")
st.markdown("Real satellite and seismic data. Select a disaster type below.")
st.divider()

# ── Session state ─────────────────────────────────────────────────────────────

for key in ["flood_result", "flood_error", "quake_result", "quake_error"]:
    if key not in st.session_state:
        st.session_state[key] = None

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab_flood, tab_quake = st.tabs(["🌊  Flood Detection", "🔴  Earthquake Detection"])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — FLOOD DETECTION
# ══════════════════════════════════════════════════════════════════════════════

with tab_flood:

    FLOOD_PRESETS = {
        "Bangladesh (2024 floods)":  (23.685, 90.356,  "2024-08-01", "2024-09-30"),
        "Pakistan (2022 floods)":    (27.000, 68.000,  "2022-08-01", "2022-10-01"),
        "Nigeria (2022 floods)":     (7.500,  6.500,   "2022-10-01", "2022-11-30"),
        "Thailand (2024 floods)":    (15.870, 100.993, "2024-09-01", "2024-10-31"),
        "Custom location":           (23.685, 90.356,  "2024-08-01", "2024-09-30"),
    }

    f_col_ctrl, f_col_main = st.columns([1, 3])

    with f_col_ctrl:
        st.markdown("#### Settings")
        f_preset = st.selectbox("Known flood event", list(FLOOD_PRESETS.keys()), key="f_preset")
        fp_lat, fp_lon, fp_start, fp_end = FLOOD_PRESETS[f_preset]

        f_lat   = st.number_input("Latitude",  value=float(fp_lat),  min_value=-90.0,  max_value=90.0,  step=0.01, format="%.4f", key="f_lat")
        f_lon   = st.number_input("Longitude", value=float(fp_lon),  min_value=-180.0, max_value=180.0, step=0.01, format="%.4f", key="f_lon")
        f_start = st.date_input("Start date", value=date.fromisoformat(fp_start), key="f_start")
        f_end   = st.date_input("End date",   value=date.fromisoformat(fp_end),   key="f_end")
        f_cloud = st.slider("Max cloud cover (%)", 5, 80, 30, 5, key="f_cloud")

        f_run = st.button("Run Flood Detection", use_container_width=True, type="primary", key="f_run")

    # Trigger
    if f_run:
        st.session_state.flood_result = None
        st.session_state.flood_error  = None
        if f_start >= f_end:
            st.session_state.flood_error = "Start date must be before end date."
        else:
            date_range = f"{f_start.isoformat()}/{f_end.isoformat()}"
            with st.spinner("Fetching satellite imagery... (20–40 seconds)"):
                res = run_detection(f_lat, f_lon, date_range, f_cloud)
            if res["success"]:
                res["lat"] = f_lat
                res["lon"] = f_lon
                st.session_state.flood_result = res
            else:
                st.session_state.flood_error = res["error"]

    with f_col_main:
        if st.session_state.flood_error:
            st.error(f"Detection failed: {st.session_state.flood_error}")

        if st.session_state.flood_result is None:
            st.markdown("#### Area of Interest")
            m = folium.Map(location=[f_lat, f_lon], zoom_start=8, tiles="CartoDB dark_matter")
            folium.Marker([f_lat, f_lon], tooltip="Selected location",
                          icon=folium.Icon(color="blue", icon="info-sign")).add_to(m)
            st_folium(m, width=800, height=480, key="f_base_map")
            st.info("Select a preset or enter coordinates, then click **Run Flood Detection**.")

        else:
            r = st.session_state.flood_result

            st.markdown(f"### Flood Results — Scene: **{r['date']}**")
            m1, m2, m3 = st.columns(3)
            m1.metric("Flooded Area", f"{r['flood_pct']}%")
            m2.metric("Flood Points", len(r["flood_coords"]))
            m3.metric("Scene ID", r["scene_id"][:22] + "...")

            if r["flood_pct"] > 20:
                st.error(f"HIGH FLOOD RISK — {r['flood_pct']}% of the area shows water presence.")
            elif r["flood_pct"] > 5:
                st.warning(f"MODERATE FLOOD SIGNAL — {r['flood_pct']}% flagged.")
            else:
                st.success(f"LOW FLOOD SIGNAL — only {r['flood_pct']}% flagged.")

            map_col, img_col = st.columns([2, 1])

            with map_col:
                st.markdown("#### Flood Map")
                fmap = folium.Map(location=[r["lat"], r["lon"]], zoom_start=9, tiles="CartoDB dark_matter")
                folium.Marker([r["lat"], r["lon"]], tooltip="Centre",
                              icon=folium.Icon(color="white", icon="info-sign")).add_to(fmap)
                if r["flood_coords"]:
                    HeatMap(r["flood_coords"], radius=12, blur=8, min_opacity=0.5,
                            gradient={0.2: "blue", 0.5: "cyan", 0.8: "red"}).add_to(fmap)
                bbox = r["bbox"]
                folium.Rectangle(bounds=[[bbox[1], bbox[0]], [bbox[3], bbox[2]]],
                                 color="#64748b", fill=False, weight=1,
                                 tooltip="Satellite scene boundary").add_to(fmap)
                st_folium(fmap, width=600, height=420, key="f_flood_map")

            with img_col:
                st.markdown("#### NDWI Image")
                st.caption("Blue = water  |  Red = dry land")
                if os.path.exists(r["ndwi_path"]):
                    st.image(r["ndwi_path"], use_container_width=True)
                st.markdown(
                    "Each pixel is scored −1 to +1. Water absorbs infrared but "
                    "reflects green — score above **0.2** = flooded."
                )

            if st.button("Clear flood results", key="f_clear"):
                st.session_state.flood_result = None
                st.session_state.flood_error  = None
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — EARTHQUAKE DETECTION
# ══════════════════════════════════════════════════════════════════════════════

with tab_quake:

    QUAKE_PRESETS = {
        "Turkey–Syria (Feb 2023)":      (37.174, 37.032, "2023-02-01", "2023-02-28", 300),
        "Morocco (Sep 2023)":           (31.060, -8.380, "2023-09-08", "2023-09-30", 200),
        "Japan Noto (Jan 2024)":        (37.200, 137.20, "2024-01-01", "2024-01-31", 200),
        "Taiwan (Apr 2024)":            (23.820, 121.56, "2024-04-01", "2024-04-30", 200),
        "Afghanistan (Oct 2023)":       (34.568, 61.980, "2023-10-01", "2023-10-31", 300),
        "Custom location":              (37.174, 37.032, "2023-02-01", "2023-02-28", 300),
    }

    q_col_ctrl, q_col_main = st.columns([1, 3])

    with q_col_ctrl:
        st.markdown("#### Settings")
        q_preset = st.selectbox("Known earthquake event", list(QUAKE_PRESETS.keys()), key="q_preset")
        qp = QUAKE_PRESETS[q_preset]
        qp_lat, qp_lon, qp_start, qp_end, qp_radius = qp

        q_lat    = st.number_input("Latitude",  value=float(qp_lat),  min_value=-90.0,  max_value=90.0,  step=0.01, format="%.4f", key="q_lat")
        q_lon    = st.number_input("Longitude", value=float(qp_lon),  min_value=-180.0, max_value=180.0, step=0.01, format="%.4f", key="q_lon")
        q_start  = st.date_input("Start date",  value=date.fromisoformat(qp_start), key="q_start")
        q_end    = st.date_input("End date",    value=date.fromisoformat(qp_end),   key="q_end")
        q_radius = st.slider("Search radius (km)", 50, 1000, int(qp_radius), 50, key="q_radius")
        q_minmag = st.slider("Minimum magnitude", 2.0, 8.0, 4.0, 0.5, key="q_minmag")

        q_run = st.button("Run Earthquake Detection", use_container_width=True, type="primary", key="q_run")

    # Trigger
    if q_run:
        st.session_state.quake_result = None
        st.session_state.quake_error  = None
        if q_start >= q_end:
            st.session_state.quake_error = "Start date must be before end date."
        else:
            with st.spinner("Querying USGS Earthquake API..."):
                res = fetch_earthquakes(
                    q_lat, q_lon,
                    q_start.isoformat(), q_end.isoformat(),
                    q_radius, q_minmag,
                )
            if res["success"]:
                res["centre_lat"] = q_lat
                res["centre_lon"] = q_lon
                st.session_state.quake_result = res
            else:
                st.session_state.quake_error = res["error"]

    with q_col_main:
        if st.session_state.quake_error:
            st.error(f"Detection failed: {st.session_state.quake_error}")

        if st.session_state.quake_result is None:
            st.markdown("#### Area of Interest")
            qm = folium.Map(location=[q_lat, q_lon], zoom_start=6, tiles="CartoDB dark_matter")
            folium.Marker([q_lat, q_lon], tooltip="Search centre",
                          icon=folium.Icon(color="red", icon="info-sign")).add_to(qm)
            st_folium(qm, width=800, height=480, key="q_base_map")
            st.info("Select a preset or enter coordinates, then click **Run Earthquake Detection**.")

        else:
            r = st.session_state.quake_result
            lg = r["largest"]

            st.markdown("### Earthquake Results")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Earthquakes Found", r["count"])
            m2.metric("Largest Magnitude", f"M {r['max_magnitude']}")
            m3.metric("Average Magnitude", f"M {r['avg_magnitude']}")
            m4.metric("Search Radius", f"{r['radius_km']} km")

            # Alert banner based on largest quake
            mx = r["max_magnitude"]
            if mx >= 7.0:
                st.error(f"MAJOR EARTHQUAKE — M{mx} recorded. Significant damage expected.")
            elif mx >= 6.0:
                st.error(f"STRONG EARTHQUAKE — M{mx} recorded. Possible structural damage.")
            elif mx >= 5.0:
                st.warning(f"MODERATE EARTHQUAKE — M{mx} recorded. Felt widely, minor damage possible.")
            else:
                st.info(f"LIGHT SEISMIC ACTIVITY — largest M{mx}. Unlikely to cause damage.")

            if lg.get("tsunami"):
                st.error("TSUNAMI WARNING was issued for the largest event.")

            map_col, list_col = st.columns([2, 1])

            with map_col:
                st.markdown("#### Earthquake Map")
                st.caption("Circle size = magnitude  |  Colour: green < 5.0 → beige 4–5 → orange 5–6 → red 6–7 → darkred 7+")

                qmap = folium.Map(
                    location=[r["centre_lat"], r["centre_lon"]],
                    zoom_start=6,
                    tiles="CartoDB dark_matter",
                )

                # Search radius circle
                folium.Circle(
                    location=[r["centre_lat"], r["centre_lon"]],
                    radius=r["radius_km"] * 1000,
                    color="#334155", fill=False, weight=1,
                    tooltip=f"Search radius: {r['radius_km']} km",
                ).add_to(qmap)

                # Centre marker
                folium.Marker(
                    [r["centre_lat"], r["centre_lon"]],
                    tooltip="Search centre",
                    icon=folium.Icon(color="white", icon="screenshot"),
                ).add_to(qmap)

                # Earthquake circles
                for eq in r["earthquakes"]:
                    ts = eq["time"] / 1000
                    eq_date = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M UTC")
                    popup_html = (
                        f"<b>M{eq['magnitude']}</b><br>"
                        f"{eq['place']}<br>"
                        f"Depth: {eq['depth_km']} km<br>"
                        f"{eq_date}"
                    )
                    folium.CircleMarker(
                        location=[eq["lat"], eq["lon"]],
                        radius=magnitude_radius(eq["magnitude"]),
                        color=magnitude_colour(eq["magnitude"]),
                        fill=True,
                        fill_color=magnitude_colour(eq["magnitude"]),
                        fill_opacity=0.7,
                        popup=folium.Popup(popup_html, max_width=220),
                        tooltip=f"M{eq['magnitude']} — {eq['place']}",
                    ).add_to(qmap)

                st_folium(qmap, width=600, height=480, key="q_quake_map")

            with list_col:
                st.markdown("#### Top 10 Earthquakes")
                for i, eq in enumerate(r["earthquakes"][:10]):
                    ts = eq["time"] / 1000
                    eq_date = datetime.utcfromtimestamp(ts).strftime("%d %b %Y")
                    colour = magnitude_colour(eq["magnitude"])
                    st.markdown(
                        f"**{i+1}. M{eq['magnitude']}** — {eq_date}  \n"
                        f"{eq['place']}  \n"
                        f"Depth: {eq['depth_km']} km"
                    )
                    st.divider()

            if st.button("Clear earthquake results", key="q_clear"):
                st.session_state.quake_result = None
                st.session_state.quake_error  = None
                st.rerun()
