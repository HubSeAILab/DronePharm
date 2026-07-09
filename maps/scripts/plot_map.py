"""
Geocodes pharmacy addresses, adds the central depot, builds an interactive map,
and optionally exports the map as a PDF.

Requirements:
    pip install pandas openpyxl geopy folium selenium pillow --break-system-packages
    Selenium, Pillow, and ChromeDriver are only required for PDF export.

Usage:
    python plot_map.py input.xlsx
"""

import json
import os
import sys
import time

import folium
import pandas as pd
from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import Nominatim


INPUT_FILE = sys.argv[1] if len(sys.argv) > 1 else "entrada.xlsx"
CACHE_FILE = "geocode_cache.json"
HTML_MAP_FILE = "mapa_pontos.html"
PDF_MAP_FILE = "mapa_pontos.pdf"

TILE_STYLE = "cartodbpositron"

CENTRAL_DEPOT = {
    "FarmÃ¡cia": "DROGARIA ARAUJO S A",
    "EndereÃ§o": "AVENIDA DO CONTORNO, 6714",
    "Bairro": "LOURDES",
    "Cidade": "Belo Horizonte",
    "Estado": "MG",
    "Latitude": -19.9391827,
    "Longitude": -43.9416411,
}

COLUMN_ALIASES = {
    "pharmacy": ["FarmÃ¡cia", "Farmacia", "name"],
    "address": ["EndereÃ§o", "Endereco", "address"],
    "district": ["Bairro", "district"],
    "city": ["Cidade", "city"],
    "state": ["Estado", "UF", "state"],
}


def find_column(df, aliases, required=True):
    """Find the first DataFrame column that matches one of the expected aliases."""
    for alias in aliases:
        if alias in df.columns:
            return alias
    if required:
        raise ValueError(f"Required column not found. Expected one of: {aliases}")
    return None


def load_data(path):
    """Load the input spreadsheet or CSV and verify that required location columns exist."""
    if path.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path)

    address_col = find_column(df, COLUMN_ALIASES["address"])
    city_col = find_column(df, COLUMN_ALIASES["city"])
    find_column(df, COLUMN_ALIASES["district"])
    find_column(df, COLUMN_ALIASES["state"])

    df = df.dropna(subset=[address_col, city_col]).reset_index(drop=True)
    return df


def load_cache():
    """Load cached geocoding results from disk when the cache file exists."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    return {}


def save_cache(cache):
    """Persist geocoding cache data to disk as formatted JSON."""
    with open(CACHE_FILE, "w", encoding="utf-8") as file:
        json.dump(cache, file, ensure_ascii=False, indent=2)


def value(row, aliases, default=""):
    """Fetch the first available value from a row using configured column aliases."""
    for alias in aliases:
        if alias in row and pd.notna(row[alias]):
            return row[alias]
    return default


def build_full_address(row):
    """Build a complete address string from the available address-related columns."""
    parts = [
        str(value(row, COLUMN_ALIASES["address"])).strip(),
        str(value(row, COLUMN_ALIASES["district"])).strip(),
        str(value(row, COLUMN_ALIASES["city"])).strip(),
        str(value(row, COLUMN_ALIASES["state"])).strip(),
        "Brazil",
    ]
    return ", ".join([part for part in parts if part])


def add_depot(df, cache):
    """Add the central depot to the dataset and seed its coordinates in the cache."""
    full_address = build_full_address(pd.Series(CENTRAL_DEPOT))
    cache[full_address] = [CENTRAL_DEPOT["Latitude"], CENTRAL_DEPOT["Longitude"]]
    save_cache(cache)

    name_col = find_column(df, COLUMN_ALIASES["pharmacy"], required=False) or df.columns[1]
    depot_name = CENTRAL_DEPOT["FarmÃ¡cia"]

    df = df[df[name_col] != depot_name].reset_index(drop=True)
    new_row = {col: CENTRAL_DEPOT.get(col) for col in df.columns}
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    return df


def geocode_data(df):
    """Geocode each address, using cached results and fallback address formats when possible."""
    cache = load_cache()

    geolocator = Nominatim(user_agent="relatorio_pontos_mapa")
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

    latitudes, longitudes, full_addresses = [], [], []

    for idx, row in df.iterrows():
        full_address = build_full_address(row)
        district = value(row, COLUMN_ALIASES["district"], None)
        city = value(row, COLUMN_ALIASES["city"])
        state = value(row, COLUMN_ALIASES["state"])
        fallback_address = f"{district}, {city}, {state}, Brazil" if pd.notna(district) else f"{city}, {state}, Brazil"

        if full_address in cache:
            lat, lon = cache[full_address]
        else:
            lat, lon = None, None
            for attempt in (full_address, fallback_address):
                try:
                    location = geocode(attempt, timeout=10)
                except Exception as error:
                    print(f"  [error] {attempt}: {error}")
                    location = None

                if location:
                    lat, lon = location.latitude, location.longitude
                    break
                time.sleep(0.5)

            cache[full_address] = [lat, lon]
            save_cache(cache)

        status = "OK" if lat is not None else "NOT FOUND"
        print(f"[{idx + 1}/{len(df)}] {full_address} -> {status}")

        latitudes.append(lat)
        longitudes.append(lon)
        full_addresses.append(full_address)

    df = df.copy()
    df["Latitude"] = latitudes
    df["Longitude"] = longitudes
    df["EnderecoCompleto"] = full_addresses

    return df


def create_map(df):
    """Create an interactive map with the depot, pharmacies, and connecting guide lines."""
    valid_df = df.dropna(subset=["Latitude", "Longitude"])

    if valid_df.empty:
        raise ValueError("No address was geocoded successfully.")

    center_lat = valid_df["Latitude"].mean()
    center_lon = valid_df["Longitude"].mean()

    point_map = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=12,
        tiles=TILE_STYLE,
        control_scale=True,
    )

    name_col = find_column(valid_df, COLUMN_ALIASES["pharmacy"], required=False) or valid_df.columns[1]
    depot_name = CENTRAL_DEPOT["FarmÃ¡cia"]

    depot_row = valid_df[valid_df[name_col] == depot_name]
    depot_coords = None
    if not depot_row.empty:
        row = depot_row.iloc[0]
        depot_coords = (row["Latitude"], row["Longitude"])

    address_col = find_column(valid_df, COLUMN_ALIASES["address"])
    district_col = find_column(valid_df, COLUMN_ALIASES["district"])
    city_col = find_column(valid_df, COLUMN_ALIASES["city"])
    state_col = find_column(valid_df, COLUMN_ALIASES["state"])

    for _, row in valid_df.iterrows():
        name = row.get(name_col, "")
        is_depot = name == depot_name

        popup_html = f"""
        <div style="font-family: Arial, sans-serif; font-size: 13px; max-width: 220px;">
            <b>{name}</b>{' (Central Depot)' if is_depot else ''}<br>
            {row[address_col]}<br>
            {row[district_col]} - {row[city_col]}/{row[state_col]}
        </div>
        """

        if is_depot:
            folium.Marker(
                location=[row["Latitude"], row["Longitude"]],
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=name,
                icon=folium.Icon(color="red", icon="warehouse", prefix="fa"),
            ).add_to(point_map)
        else:
            folium.CircleMarker(
                location=[row["Latitude"], row["Longitude"]],
                radius=6,
                color="#2c3e50",
                weight=1,
                fill=True,
                fill_color="#3498db",
                fill_opacity=0.85,
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=name,
            ).add_to(point_map)

            if depot_coords is not None:
                folium.PolyLine(
                    locations=[depot_coords, (row["Latitude"], row["Longitude"])],
                    color="#7f8c8d",
                    weight=1.5,
                    opacity=0.6,
                    dash_array="4,6",
                ).add_to(point_map)

    sw = valid_df[["Latitude", "Longitude"]].min().values.tolist()
    ne = valid_df[["Latitude", "Longitude"]].max().values.tolist()
    point_map.fit_bounds([sw, ne], padding=(30, 30))

    point_map.save(HTML_MAP_FILE)
    print(f"\nInteractive map saved at: {HTML_MAP_FILE}")

    invalid_count = len(df) - len(valid_df)
    if invalid_count:
        print(f"Warning: {invalid_count} address(es) were not geocoded and were left out of the map.")

    return point_map, valid_df


def export_pdf(html_path, pdf_path):
    """Capture the generated HTML map with Selenium and save it as a PDF."""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
    except ImportError:
        print("\n[Warning] Selenium is not installed. Skipping PDF export.")
        print("Install it with: pip install selenium pillow --break-system-packages")
        print("Make sure Chromium/ChromeDriver is available on the system.")
        return

    try:
        from PIL import Image
    except ImportError:
        print("\n[Warning] Pillow is not installed. Skipping PDF export.")
        print("Install it with: pip install pillow --break-system-packages")
        return

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1400,1000")
    options.add_argument("--no-sandbox")

    try:
        driver = webdriver.Chrome(options=options)
    except Exception as error:
        print(f"\n[Warning] Could not start Chrome/ChromeDriver: {error}")
        print("Skipping PDF export.")
        return

    abs_path = "file://" + os.path.abspath(html_path)
    driver.get(abs_path)
    time.sleep(2)  # Wait for map tiles to load.

    temp_png = "_mapa_temp.png"
    driver.save_screenshot(temp_png)
    driver.quit()

    image = Image.open(temp_png).convert("RGB")
    image.save(pdf_path, "PDF", resolution=150.0)
    os.remove(temp_png)

    print(f"PDF map saved at: {pdf_path}")


if __name__ == "__main__":
    print(f"Loading data from '{INPUT_FILE}'...")
    data_frame = load_data(INPUT_FILE)

    print(f"\nGeocoding {len(data_frame)} addresses. This may take a few minutes...")
    geocode_cache = load_cache()
    data_frame = add_depot(data_frame, geocode_cache)
    geocoded_df = geocode_data(data_frame)

    # Save the coordinate table for validation and later use.
    geocoded_df.to_excel("data_with_coordinates.xlsx", index=False)
    print("\nCoordinate table saved at: data_with_coordinates.xlsx")

    print("\nCreating map...")
    create_map(geocoded_df)

    print("\nGenerating map PDF...")
    export_pdf(HTML_MAP_FILE, PDF_MAP_FILE)

    print("\nDone!")

