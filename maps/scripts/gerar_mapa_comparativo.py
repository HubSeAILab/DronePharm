"""Generates a single map comparing the urban route and the drone route.

This script does not recalculate routes. It reuses existing results:
- dados_entrada/relatorio_rota_urbana.json
- experimental_setup/coordenadas.json

Generated outputs:
- saida/mapa_drone_urbano.html
- saida/rotas_drone_urbano.geojson
- saida/resumo_comparativo.json

Usage:
    python gerar_mapa_comparativo.py
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import folium
from folium.plugins import AntPath


URBAN_COLOR = "#1769aa"
DRONE_COLOR = "#d93636"
BASE_COLOR = "#2d3436"


def read_json(path: Path) -> dict[str, Any]:
    """Read a JSON file and clean any mojibake text artifacts from its contents."""
    return clean_mojibake(json.loads(path.read_text(encoding="utf-8")))


def clean_text(value: str) -> str:
    """Repair common UTF-8 text decoded as Latin-1 when possible."""
    if "\u00c3" not in value and "\u00c2" not in value:
        return value
    try:
        return value.encode("latin1").decode("utf-8")
    except UnicodeError:
        return value


def clean_mojibake(value: Any) -> Any:
    """Recursively clean mojibake artifacts inside nested lists and dictionaries."""
    if isinstance(value, str):
        return clean_text(value)
    if isinstance(value, list):
        return [clean_mojibake(item) for item in value]
    if isinstance(value, dict):
        return {key: clean_mojibake(item) for key, item in value.items()}
    return value


def flatten_geometry_coordinates(geometry: dict[str, Any]) -> list[list[float]]:
    """Return [lon, lat] pairs from LineString or MultiLineString geometries."""
    geom_type = geometry.get("type")
    coordinates = geometry.get("coordinates", [])
    if geom_type == "LineString":
        return coordinates
    if geom_type == "MultiLineString":
        return [point for line in coordinates for point in line]
    raise ValueError(f"Unsupported geometry type: {geom_type}")


def lonlat_to_latlon(points: list[list[float]]) -> list[list[float]]:
    """Convert coordinate pairs from lon/lat order to lat/lon order for Folium."""
    return [[lat, lon] for lon, lat in points]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the Haversine distance between two latitude/longitude points."""
    radius_km = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return 2 * radius_km * math.asin(math.sqrt(a))


def calculate_drone_distance_km(waypoints: list[dict[str, Any]]) -> float:
    """Sum the straight-line distance between all consecutive drone waypoints."""
    distance = 0.0
    for origin, destination in zip(waypoints, waypoints[1:]):
        distance += haversine_km(
            float(origin["latitude"]),
            float(origin["longitude"]),
            float(destination["latitude"]),
            float(destination["longitude"]),
        )
    return distance


def add_numbered_marker(
    map_object: folium.Map,
    *,
    lat: float,
    lon: float,
    label: str,
    sequence: int,
    color: str,
    popup: str,
) -> None:
    """Add a numbered circular marker to a Folium feature group."""
    icon_html = f"""
    <div style="
        width:26px;height:26px;border-radius:50%;
        background:#fff;border:2px solid {color};
        color:{color};font:700 12px Arial;
        display:flex;align-items:center;justify-content:center;
        box-shadow:0 1px 4px rgba(0,0,0,.25);
    ">{sequence}</div>
    """
    folium.Marker(
        location=[lat, lon],
        tooltip=label,
        popup=folium.Popup(popup, max_width=280),
        icon=folium.DivIcon(html=icon_html, icon_size=(26, 26), icon_anchor=(13, 13)),
    ).add_to(map_object)


def build_geojson(
    urban_result: dict[str, Any],
    drone_data: dict[str, Any],
    drone_lonlat: list[list[float]],
) -> dict[str, Any]:
    """Build a GeoJSON comparison layer containing both urban and drone route features."""
    features: list[dict[str, Any]] = [
        {
            "type": "Feature",
            "geometry": urban_result["geometry"],
            "properties": {
                "route_type": "urbana",
                "color": URBAN_COLOR,
                **urban_result.get("summary", {}),
            },
        },
        {
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": drone_lonlat},
            "properties": {
                "route_type": "drone",
                "color": DRONE_COLOR,
                "distance_km": drone_data.get("distancia_km"),
                "duration_min": drone_data.get("tempo_min"),
                "energy_wh": drone_data.get("energia_wh"),
                "payload_kg": drone_data.get("carga_kg"),
                "viable": drone_data.get("viavel"),
            },
        },
    ]

    for stop in urban_result.get("ordered_stops", []):
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [stop["longitude"], stop["latitude"]],
                },
                "properties": {
                    "route_type": "urbana",
                    "point_type": stop.get("kind"),
                    "sequence": stop.get("sequence"),
                    "label": stop.get("label"),
                    "street": stop.get("street"),
                },
            }
        )

    for waypoint in drone_data.get("waypoints_json", []):
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [waypoint["longitude"], waypoint["latitude"]],
                },
                "properties": {
                    "route_type": "drone",
                    "sequence": waypoint.get("seq"),
                    "label": waypoint.get("label"),
                    "altitude": waypoint.get("altitude"),
                },
            }
        )

    return {"type": "FeatureCollection", "features": features}


def add_legend(map_object: folium.Map, summary: dict[str, Any]) -> None:
    """Attach the route-comparison legend overlay to the Folium map."""
    html = f"""
    <div style="
      position: fixed; z-index: 9999; left: 18px; bottom: 18px;
      background: rgba(255,255,255,.94); border: 1px solid #d9dee3;
      border-radius: 8px; padding: 12px 14px;
      font: 13px Arial, sans-serif; color: #1f2933;
      box-shadow: 0 4px 16px rgba(0,0,0,.16);
      min-width: 250px;
    ">
      <div style="font-weight:700;font-size:14px;margin-bottom:8px;">Compared routes</div>
      <div><span style="display:inline-block;width:28px;height:4px;background:{URBAN_COLOR};margin-right:8px;vertical-align:middle;"></span>Urban route</div>
      <div style="margin-top:6px;"><span style="display:inline-block;width:28px;border-top:4px dashed {DRONE_COLOR};margin-right:8px;vertical-align:middle;"></span>Drone route</div>
      <hr style="border:0;border-top:1px solid #e3e7eb;margin:10px 0;">
      <div>Urban: <b>{summary['urban_distance_km']:.2f} km</b> | <b>{summary['urban_minutes']:.1f} min</b></div>
      <div>Drone: <b>{summary['drone_distance_km']:.2f} km</b> | <b>{summary['drone_minutes']:.1f} min</b></div>
      <div>Distance savings: <b>{summary['distance_reduction_percent']:.1f}%</b></div>
    </div>
    """
    map_object.get_root().html.add_child(folium.Element(html))


def build_map(urban_result: dict[str, Any], drone_data: dict[str, Any], output_html: Path) -> dict[str, Any]:
    """Create an interactive Folium map showing pharmacies, delivery points, and routes."""
    urban_lonlat = flatten_geometry_coordinates(urban_result["geometry"])
    urban_latlon = lonlat_to_latlon(urban_lonlat)
    drone_waypoints = drone_data["waypoints_json"]
    drone_latlon = [[wp["latitude"], wp["longitude"]] for wp in drone_waypoints]
    drone_lonlat = [[wp["longitude"], wp["latitude"]] for wp in drone_waypoints]

    all_points = urban_latlon + drone_latlon
    center = [
        sum(point[0] for point in all_points) / len(all_points),
        sum(point[1] for point in all_points) / len(all_points),
    ]

    route_map = folium.Map(
        location=center,
        zoom_start=12,
        tiles="CartoDB positron",
        control_scale=True,
    )
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap").add_to(route_map)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery",
        name="Satelite",
    ).add_to(route_map)

    urban_group = folium.FeatureGroup(name="Rota urbana", show=True).add_to(route_map)
    drone_group = folium.FeatureGroup(name="Rota drone", show=True).add_to(route_map)

    folium.GeoJson(
        urban_result["geometry"],
        name="Linha urbana",
        style_function=lambda _: {"color": URBAN_COLOR, "weight": 5, "opacity": 0.84},
        tooltip="Rota urbana sobre ruas",
    ).add_to(urban_group)

    AntPath(
        locations=drone_latlon,
        color=DRONE_COLOR,
        weight=4,
        opacity=0.92,
        dash_array=[12, 18],
        delay=900,
        pulse_color="#ffffff",
    ).add_to(drone_group)

    for stop in urban_result.get("ordered_stops", []):
        sequence = int(stop.get("sequence", 0))
        popup = (
            f"<b>Rota urbana</b><br>{stop.get('label', '')}<br>"
            f"{stop.get('street', '')}<br>Sequencia: {sequence}<br>"
            f"Lat: {stop['latitude']:.6f}<br>Lon: {stop['longitude']:.6f}"
        )
        add_numbered_marker(
            urban_group,
            lat=stop["latitude"],
            lon=stop["longitude"],
            label=f"Urbana {sequence} - {stop.get('label', '')}",
            sequence=sequence,
            color=URBAN_COLOR if sequence else BASE_COLOR,
            popup=popup,
        )

    last_drone_index = len(drone_waypoints) - 1
    for waypoint in drone_waypoints:
        sequence = int(waypoint.get("seq", 0))
        popup = (
            f"<b>Rota drone</b><br>{waypoint.get('label', '')}<br>"
            f"Sequencia: {sequence}<br>Altitude: {waypoint.get('altitude', '')} m<br>"
            f"Lat: {waypoint['latitude']:.6f}<br>Lon: {waypoint['longitude']:.6f}"
        )
        marker_color = BASE_COLOR if sequence in {0, last_drone_index} else DRONE_COLOR
        add_numbered_marker(
            drone_group,
            lat=waypoint["latitude"],
            lon=waypoint["longitude"],
            label=f"Drone {sequence} - {waypoint.get('label', '')}",
            sequence=sequence,
            color=marker_color,
            popup=popup,
        )

    urban_summary = urban_result.get("summary", {})
    drone_distance_km = float(drone_data.get("distancia_km") or calculate_drone_distance_km(drone_waypoints))
    urban_distance_km = float(urban_summary.get("distance_km", 0))
    summary = {
        "urban_distance_km": urban_distance_km,
        "urban_minutes": float(urban_summary.get("driving_minutes", urban_summary.get("total_minutes", 0))),
        "urban_total_minutes": float(urban_summary.get("total_minutes", 0)),
        "drone_distance_km": drone_distance_km,
        "drone_minutes": float(drone_data.get("tempo_min", 0)),
        "drone_energy_wh": float(drone_data.get("energia_wh", 0)),
        "drone_payload_kg": float(drone_data.get("carga_kg", 0)),
        "drone_viable": bool(drone_data.get("viavel")),
        "distance_reduction_km": urban_distance_km - drone_distance_km,
        "distance_reduction_percent": (
            ((urban_distance_km - drone_distance_km) / urban_distance_km) * 100 if urban_distance_km else 0
        ),
        "urban_base": urban_result.get("base", {}),
        "drone_base": drone_waypoints[0],
    }

    add_legend(route_map, summary)
    folium.LayerControl(collapsed=False).add_to(route_map)
    route_map.fit_bounds(all_points, padding=(35, 35))
    route_map.save(str(output_html))
    return summary


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments that configure inputs, outputs, and routing behavior."""
    base_dir = Path(__file__).resolve().parent
    project_root = base_dir.parent.parent
    parser = argparse.ArgumentParser(description="Generates a comparative map for the urban route and drone route.")
    parser.add_argument("--urbana", type=Path, default=base_dir / "dados_entrada" / "relatorio_rota_urbana.json")
    parser.add_argument("--drone", type=Path, default=project_root / "experimental_setup" / "coordenadas.json")
    parser.add_argument("--saida", type=Path, default=base_dir / "saida")
    return parser.parse_args()


def main() -> None:
    """Run the script workflow from command-line parsing through output generation."""
    args = parse_args()
    args.saida.mkdir(parents=True, exist_ok=True)

    urban_result = read_json(args.urbana)
    drone_data = read_json(args.drone)
    drone_lonlat = [[wp["longitude"], wp["latitude"]] for wp in drone_data["waypoints_json"]]

    html_path = args.saida / "mapa_drone_urbano.html"
    geojson_path = args.saida / "rotas_drone_urbano.geojson"
    summary_path = args.saida / "resumo_comparativo.json"

    summary = build_map(urban_result, drone_data, html_path)
    geojson = build_geojson(urban_result, drone_data, drone_lonlat)

    geojson_path.write_text(json.dumps(geojson, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Mapa comparativo gerado:")
    print(f"  HTML: {html_path}")
    print(f"  GeoJSON: {geojson_path}")
    print(f"  Resumo: {summary_path}")


if __name__ == "__main__":
    main()


