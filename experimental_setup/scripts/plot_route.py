"""
Generates dynamic Folium/Leaflet maps for the drone route in 4 tile styles:
  1. CartoDB Positron
  2. OpenStreetMap
  3. CartoDB Voyager
  4. Satellite (Esri World Imagery)

No overlaid legends or panels, only the route and numbered markers.

It also exports a multi-page PDF (one page per style) in high resolution
using Selenium to capture each rendered map.

IMPORTANT NOTE ABOUT ZOOM QUALITY:
This PDF is generated from screenshots (raster/PNG). Even at high
resolution (6000x6000 effective pixels per page here), applying very
strong zoom in a PDF/article will eventually pixelate the image; this is
an inherent limitation of any tile-map capture (Leaflet, Google
Maps, etc).

If you need VECTOR quality (infinite lossless zoom, ideal for
printed scientific papers), use the script 'plot_route.py' (matplotlib),
which generates lines, markers, and text as real vectors; only the background tile
is raster, and the document as a whole remains much sharper when zoomed.

Requirements:
    pip install folium geopy selenium webdriver-manager pillow

Google Chrome must also be installed.

Usage:
    python plot_rota_multitile.py
"""

import json
import os
import time

import folium
from folium.plugins import AntPath

# ---------------------------------------------------------
# 1. Load data
# ---------------------------------------------------------
with open("coordinates.json", "r", encoding="utf-8") as f:
    data = json.load(f)

waypoints = data["waypoints_json"]
drone_id = data["drone_id"]
distancia = data["distancia_km"]
tempo = data["tempo_min"]
energia = data["energia_wh"]
carga = data["carga_kg"]

coords = [(wp["latitude"], wp["longitude"]) for wp in waypoints]
seqs = [wp["seq"] for wp in waypoints]
labels = [wp["label"] for wp in waypoints]
alts = [wp["altitude"] for wp in waypoints]

center_lat = sum(c[0] for c in coords) / len(coords)
center_lon = sum(c[1] for c in coords) / len(coords)
base_idx = {0, len(waypoints) - 1}

# ---------------------------------------------------------
# 2. Map style definitions (tile, attribution, name)
# ---------------------------------------------------------
TILE_LAYERS = {
    "cartodb_positron": {
        "tiles": "CartoDB positron",
        "attr": None,
        "titulo": "CartoDB Positron",
    },
    "openstreetmap": {
        "tiles": "OpenStreetMap",
        "attr": None,
        "titulo": "OpenStreetMap",
    },
    "cartodb_voyager": {
        "tiles": "CartoDB voyager",
        "attr": None,
        "titulo": "CartoDB Voyager",
    },
    "satellite_esri": {
        "tiles": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "attr": "Esri World Imagery",
        "titulo": "Satellite (Esri)",
    },
}


# ---------------------------------------------------------
# 3. Function that builds a Folium map with a single tile layer
# ---------------------------------------------------------
def build_map(tiles, attr, titulo):
    """Create an interactive Folium map showing pharmacies, delivery points, and routes."""
    if attr:
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=13,
            tiles=tiles,
            attr=attr,
            control_scale=True,
            zoom_control=False,
        )
    else:
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=13,
            tiles=tiles,
            control_scale=True,
            zoom_control=False,
        )

    # Rota
    AntPath(
        locations=coords,
        color="#1f4e8c",
        weight=3,
        opacity=0.9,
        dash_array=[10, 20],
        delay=800,
        pulse_color="#ffffff",
    ).add_to(m)

    # Marcadores
    for i, ((lat, lon), seq, label, alt) in enumerate(zip(coords, seqs, labels, alts)):
        popup_html = (
            f"<b>{label}</b><br>"
            f"Seq: {seq}<br>"
            f"Lat: {lat:.6f}<br>"
            f"Lon: {lon:.6f}<br>"
            f"Altitude: {alt} m"
        )
        if i in base_idx:
            folium.Marker(
                location=(lat, lon),
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=label,
                icon=folium.Icon(color="red", icon="home", prefix="fa"),
            ).add_to(m)
        else:
            folium.Marker(
                location=(lat, lon),
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=f"#{seq} - {label}",
                icon=folium.DivIcon(
                    html=f"""
                    <div style="
                        background-color:#ffffff;
                        border:2px solid #1f4e8c;
                        border-radius:50%;
                        width:26px; height:26px;
                        display:flex; align-items:center; justify-content:center;
                        font-size:12px; font-weight:bold; color:#1f4e8c;
                        box-shadow:0 1px 3px rgba(0,0,0,0.4);
                    ">{seq}</div>
                    """
                ),
            ).add_to(m)

    m.fit_bounds(coords, padding=(30, 30))
    return m


# ---------------------------------------------------------
# 4. Gerar os 4 arquivos HTML
# ---------------------------------------------------------
html_files = {}
for key, cfg in TILE_LAYERS.items():
    m = build_map(cfg["tiles"], cfg["attr"], cfg["titulo"])
    filename = f"drone_route_{key}.html"
    m.save(filename)
    html_files[key] = (filename, cfg["titulo"])
    print(f"Gerado: {filename}")


# ---------------------------------------------------------
# 5. Capture each HTML file in high resolution with Selenium
#    and build a multi-page PDF
# ---------------------------------------------------------
EXPORTAR_PDF = True  # set to True to generate the PDF

if EXPORTAR_PDF:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    from PIL import Image

    WIDTH, HEIGHT = 2000, 2000
    SCALE = 3  # resolution factor (3x = ~6000x6000 effective pixels per page)

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument(f"--window-size={WIDTH},{HEIGHT}")
    options.add_argument("--hide-scrollbar")
    options.add_argument(f"--force-device-scale-factor={SCALE}")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options,
    )

    png_paths = []
    for key, (filename, titulo) in html_files.items():
        html_path = os.path.abspath(filename)
        driver.get(f"file://{html_path}")
        time.sleep(4)  # aguarda os tiles carregarem completamente

        png_path = f"drone_route_{key}.png"
        driver.save_screenshot(png_path)
        png_paths.append(png_path)
        print(f"Capturado: {png_path}")

    driver.quit()

    # Build multi-page PDF (force RGB to avoid JPEG encoder errors)
    images = [Image.open(p).convert("RGB") for p in png_paths]
    first, rest = images[0], images[1:]
    first.save(
        "drone_route_maps.pdf",
        format="PDF",
        save_all=True,
        append_images=rest,
        resolution=300.0,
    )
    print("PDF generated: drone_route_maps.pdf")
else:
    print(
        "\nTo generate a high-resolution PDF with the 4 map styles,\n"
        "edit this file, set EXPORTAR_PDF = True, then run it again.\n"
        "Additional requirements: pip install selenium webdriver-manager pillow\n"
        "e Google Chrome instalado."
    )



