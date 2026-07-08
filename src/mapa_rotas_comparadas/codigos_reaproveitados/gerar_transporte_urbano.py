"""Generates an urban ground route, themed maps, and an executive report.

O calculo principal usa o servico Trip do OSRM, que otimiza a ordem das
stops and returns distance, duration, legs, and geometry over the road network.

Exemplo:
    python gerar_transporte_urbano.py 
        --farmacias "dados_com_coordenadas(Sheet1).csv" 
        --pedidos pedidos_belo_horizonte.csv 
        --saida saida_transporte_urbano
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests


DEFAULT_OSRM = "https://router.project-osrm.org"


@dataclass
class Point:
    point_id: str
    label: str
    street: str
    lat: float
    lon: float
    kind: str


def parse_number(value: str) -> float:
    """Convert numeric text values into floats while supporting comma decimal separators."""
    text = str(value).strip()
    if "," in text and "." not in text:
        text = text.replace(",", ".")
    return float(text)


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read a CSV file using common encodings and delimiters used by the project datasets."""
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "latin1", "cp1252"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError(f"Could not read the encoding of {path}")
    delimiter = ";" if text[:4096].count(";") > text[:4096].count(",") else ","
    return list(csv.DictReader(text.splitlines(), delimiter=delimiter))


def get_value(row: dict[str, str], *names: str) -> str:
    """Return the first non-empty value from a row using a list of possible column names."""
    normalized = {key.lower().strip(): value for key, value in row.items()}
    for name in names:
        if name.lower() in normalized:
            return normalized[name.lower()]
    return ""


def load_base(path: Path, requested_name: str | None) -> Point:
    """Load the selected pharmacy base point from the pharmacy CSV."""
    candidates = []
    for row in read_csv(path):
        city = get_value(row, "Cidade", "city")
        lat = get_value(row, "Latitude", "lat")
        lon = get_value(row, "Longitude", "lon", "lng")
        name = get_value(row, "Farmacia", "Farmácia", "nome", "name")
        if city.lower().strip() != "belo horizonte" or not lat or not lon:
            continue
        try:
            point = Point(
                point_id="base",
                label=name or "Base pharmacy",
                street=get_value(row, "Endereco", "Endereço", "logradouro"),
                lat=parse_number(lat),
                lon=parse_number(lon),
                kind="base",
            )
        except ValueError:
            continue
        candidates.append(point)
        if requested_name and name.lower().strip() == requested_name.lower().strip():
            return point
    if requested_name:
        raise ValueError(f"Base pharmacy not found: {requested_name}")
    if not candidates:
        raise ValueError("No Belo Horizonte pharmacy with valid coordinates")
    return candidates[0]


def load_deliveries(path: Path, limit: int | None) -> list[Point]:
    """Load delivery points from the orders CSV and optionally limit their count."""
    points = []
    for index, row in enumerate(read_csv(path), start=1):
        try:
            order_id = get_value(row, "id_pedido", "pedido_id", "id") or str(index)
            points.append(
                Point(
                    point_id=f"pedido_{order_id}",
                    label=f"Pedido #{order_id}",
                    street=get_value(row, "nome_rua", "rua", "logradouro", "endereco"),
                    lat=parse_number(get_value(row, "Latitude", "lat")),
                    lon=parse_number(get_value(row, "Longitude", "lon", "lng")),
                    kind="delivery",
                )
            )
        except (TypeError, ValueError):
            continue
        if limit and len(points) >= limit:
            break
    if not points:
        raise ValueError("No order with valid coordinates")
    return points


def call_osrm_trip(points: list[Point], base_url: str, timeout: float) -> dict[str, Any]:
    """Call OSRM's trip endpoint to optimize the order of urban ground stops."""
    coordinates = ";".join(f"{point.lon:.6f},{point.lat:.6f}" for point in points)
    url = f"{base_url.rstrip('/')}/trip/v1/driving/{coordinates}"
    params = {
        "roundtrip": "true",
        "source": "first",
        "destination": "first",
        "overview": "full",
        "geometries": "geojson",
        "steps": "true",
        "annotations": "true",
    }
    response = requests.get(
        url,
        params=params,
        timeout=timeout,
        headers={"User-Agent": "DronePharm-urban-route-report/1.0"},
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != "Ok" or not payload.get("trips"):
        raise RuntimeError(f"OSRM did not return a valid trip: {payload}")
    return payload


def build_result(
    input_points: list[Point],
    payload: dict[str, Any],
    fuel_km_l: float,
    fuel_price: float,
    co2_kg_l: float,
    stop_minutes: float,
) -> dict[str, Any]:
    """Transform OSRM trip output into the project's urban-route result structure."""
    trip = payload["trips"][0]
    ordered_pairs = sorted(
        ((waypoint["waypoint_index"], index) for index, waypoint in enumerate(payload["waypoints"])),
        key=lambda item: item[0],
    )
    ordered = [input_points[input_index] for _, input_index in ordered_pairs]
    ordered_loop = ordered + [ordered[0]]
    legs = []
    for index, leg in enumerate(trip.get("legs", [])):
        origin = ordered_loop[index]
        destination = ordered_loop[index + 1]
        steps = []
        for step in leg.get("steps", []):
            maneuver = step.get("maneuver", {})
            steps.append(
                {
                    "instruction": maneuver.get("type", "continue"),
                    "modifier": maneuver.get("modifier"),
                    "road": step.get("name") or "Via sem nome",
                    "distance_m": round(step.get("distance", 0), 1),
                    "duration_s": round(step.get("duration", 0), 1),
                }
            )
        legs.append(
            {
                "sequence": index + 1,
                "origin_id": origin.point_id,
                "origin": origin.label,
                "destination_id": destination.point_id,
                "destination": destination.label,
                "street": destination.street,
                "distance_m": round(leg["distance"], 1),
                "distance_km": round(leg["distance"] / 1000, 3),
                "duration_s": round(leg["duration"], 1),
                "duration_min": round(leg["duration"] / 60, 2),
                "steps": steps,
            }
        )
    distance_km = trip["distance"] / 1000
    driving_minutes = trip["duration"] / 60
    service_minutes = len(ordered) - 1
    service_minutes *= stop_minutes
    fuel_l = distance_km / fuel_km_l
    return {
        "metadata": {
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "routing_api": "OSRM Trip API",
            "api_base_url": DEFAULT_OSRM,
            "profile": "driving",
            "roundtrip": True,
        },
        "base": point_to_dict(ordered[0]),
        "ordered_stops": [point_to_dict(point) | {"sequence": i} for i, point in enumerate(ordered)],
        "legs": legs,
        "geometry": trip["geometry"],
        "summary": {
            "deliveries": len(ordered) - 1,
            "distance_km": round(distance_km, 3),
            "driving_minutes": round(driving_minutes, 2),
            "service_minutes": round(service_minutes, 2),
            "total_minutes": round(driving_minutes + service_minutes, 2),
            "average_speed_kmh": round(distance_km / (driving_minutes / 60), 2),
            "fuel_efficiency_km_l": fuel_km_l,
            "estimated_fuel_l": round(fuel_l, 3),
            "fuel_price_brl_l": fuel_price,
            "estimated_fuel_cost_brl": round(fuel_l * fuel_price, 2),
            "estimated_co2_kg": round(fuel_l * co2_kg_l, 3),
            "co2_factor_kg_l": co2_kg_l,
        },
    }


def build_cached_dispatch_result(
    cache_path: Path,
    base: Point,
    deliveries: list[Point],
    fuel_km_l: float,
    fuel_price: float,
    co2_kg_l: float,
    stop_minutes: float,
) -> dict[str, Any]:
    """Build an urban dispatch result from previously cached OSRM route calculations."""
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    pharmacies = cache.get("pharmacies", [])
    selected = next(
        (item for item in pharmacies if item.get("name", "").strip().lower() == base.label.strip().lower()),
        pharmacies[0] if pharmacies else None,
    )
    if not selected:
        raise ValueError("OSRM cache has no pharmacies")
    routes_by_id = {route.get("point_id"): route for route in selected.get("routes", [])}
    legs = []
    lines = []
    ordered_stops = [point_to_dict(base) | {"sequence": 0}]
    distance_m = 0.0
    duration_s = 0.0
    for sequence, point in enumerate(deliveries, start=1):
        route = routes_by_id.get(point.point_id)
        if not route or route.get("status") != "ok" or not route.get("polyline_geojson"):
            continue
        leg_distance = float(route["distance_meters"])
        leg_duration = float(route["duration_seconds"])
        distance_m += leg_distance
        duration_s += leg_duration
        lines.append(route["polyline_geojson"]["coordinates"])
        ordered_stops.append(point_to_dict(point) | {"sequence": sequence})
        legs.append(
            {
                "sequence": sequence,
                "origin_id": base.point_id,
                "origin": base.label,
                "destination_id": point.point_id,
                "destination": point.label,
                "street": point.street,
                "distance_m": round(leg_distance, 1),
                "distance_km": round(leg_distance / 1000, 3),
                "duration_s": round(leg_duration, 1),
                "duration_min": round(leg_duration / 60, 2),
                "steps": [],
            }
        )
    if not legs:
        raise ValueError("OSRM cache has no valid routes for the selected orders")
    distance_km = distance_m / 1000
    driving_minutes = duration_s / 60
    service_minutes = len(legs) * stop_minutes
    fuel_l = distance_km / fuel_km_l
    return {
        "metadata": {
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "routing_api": "OSRM Route API (cache de respostas reais)",
            "api_base_url": cache.get("metadata", {}).get("osrm_base_url", DEFAULT_OSRM),
            "profile": "driving",
            "roundtrip": False,
            "route_model": "individual dispatches from the pharmacy to each order",
            "cache_file": str(cache_path),
        },
        "base": point_to_dict(base),
        "ordered_stops": ordered_stops,
        "legs": legs,
        "geometry": {"type": "MultiLineString", "coordinates": lines},
        "summary": {
            "deliveries": len(legs),
            "distance_km": round(distance_km, 3),
            "driving_minutes": round(driving_minutes, 2),
            "service_minutes": round(service_minutes, 2),
            "total_minutes": round(driving_minutes + service_minutes, 2),
            "average_speed_kmh": round(distance_km / (driving_minutes / 60), 2),
            "fuel_efficiency_km_l": fuel_km_l,
            "estimated_fuel_l": round(fuel_l, 3),
            "fuel_price_brl_l": fuel_price,
            "estimated_fuel_cost_brl": round(fuel_l * fuel_price, 2),
            "estimated_co2_kg": round(fuel_l * co2_kg_l, 3),
            "co2_factor_kg_l": co2_kg_l,
        },
    }


def point_to_dict(point: Point) -> dict[str, Any]:
    """Serialize a Point object into a plain dictionary for JSON output."""
    return {
        "point_id": point.point_id,
        "label": point.label,
        "street": point.street,
        "latitude": point.lat,
        "longitude": point.lon,
        "kind": point.kind,
    }


def write_geojson(result: dict[str, Any], path: Path) -> None:
    """Write the urban route and stop data as a GeoJSON file."""
    features = [
        {
            "type": "Feature",
            "geometry": result["geometry"],
            "properties": {"type": "optimized_urban_route", **result["summary"]},
        }
    ]
    for stop in result["ordered_stops"]:
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [stop["longitude"], stop["latitude"]],
                },
                "properties": {key: value for key, value in stop.items() if key not in {"latitude", "longitude"}},
            }
        )
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, indent=2), encoding="utf-8")


TILE_STYLES = {
    "claro": {
        "name": "Mapa claro",
        "url": "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
        "attribution": "OpenStreetMap / CARTO",
    },
    "osm": {
        "name": "OpenStreetMap detalhado",
        "url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        "attribution": "OpenStreetMap contributors",
    },
    "ruas": {
        "name": "Simplified urban map",
        "url": "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png",
        "attribution": "OpenStreetMap / CARTO",
    },
    "satelite": {
        "name": "Imagem de satelite",
        "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "attribution": "Esri World Imagery",
    },
}


def leaflet_html(result: dict[str, Any], style: dict[str, str]) -> str:
    """Render a complete Leaflet HTML page for one map style."""
    stops = result["ordered_stops"]
    route = result["geometry"]
    tile_url = style["url"]
    summary = result["summary"]
    route_label = "Optimized circular urban route" if result["metadata"].get("roundtrip") else "Urban dispatch plan"
    return f"""<!doctype html>
<html lang=\"pt-BR\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width\">
<title>{style['name']} - ground route</title>
<link rel=\"stylesheet\" href=\"https://unpkg.com/leaflet@1.9.4/dist/leaflet.css\">
<style>html,body,#map{{height:100%;margin:0}} .panel{{position:absolute;z-index:999;top:16px;left:16px;background:#fffffff0;padding:12px 16px;border-radius:8px;font:14px Arial;box-shadow:0 2px 10px #0003}} .panel b{{font-size:16px}} .number{{background:white;border:2px solid #1d4f7a;border-radius:50%;width:25px;height:25px;line-height:21px;text-align:center;font-weight:bold;color:#173f61}}</style></head>
<body><div id=\"map\"></div><div class=\"panel\"><b>{style['name']}</b><br>{route_label}<br>{summary['distance_km']:.2f} km | {summary['driving_minutes']:.1f} min dirigindo | {summary['deliveries']} entregas</div>
<script src=\"https://unpkg.com/leaflet@1.9.4/dist/leaflet.js\"></script><script>
const map=L.map('map',{{zoomControl:true}});
L.tileLayer({json.dumps(tile_url)},{{maxZoom:19,attribution:{json.dumps(style['attribution'])},subdomains:'abcd'}}).addTo(map);
const geometry={json.dumps(route)};
const route=L.geoJSON(geometry,{{style:{{color:'#174f7c',weight:5,opacity:.85}}}}).addTo(map);
const stops={json.dumps(stops, ensure_ascii=False)};
stops.forEach((p,i)=>{{
 const html=i===0?'&#127968;':String(i);
 const icon=L.divIcon({{className:'number',html:html,iconSize:[25,25],iconAnchor:[12,12]}});
 L.marker([p.latitude,p.longitude],{{icon}}).bindPopup(`<b>${{p.label}}</b><br>${{p.street}}<br>Sequencia: ${{i}}`).addTo(map);
}});
map.fitBounds(route.getBounds(),{{padding:[35,35]}});
</script></body></html>"""


def write_html_maps(result: dict[str, Any], output_dir: Path) -> list[Path]:
    """Generate all configured interactive HTML map variants for the urban route."""
    paths = []
    for key, style in TILE_STYLES.items():
        path = output_dir / f"mapa_terrestre_{key}.html"
        path.write_text(leaflet_html(result, style), encoding="utf-8")
        paths.append(path)
    return paths


def render_report(result: dict[str, Any], output_path: Path) -> None:
    """Create a PDF report summarizing distance, time, cost, emissions, and route legs."""
    try:
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_pdf import PdfPages
    except ImportError as exc:
        raise RuntimeError("The PDF report requires matplotlib") from exc

    summary = result["summary"]
    raw_coords = result["geometry"]["coordinates"]
    coords = raw_coords if result["geometry"]["type"] == "LineString" else [coord for line in raw_coords for coord in line]
    xs = [coord[0] for coord in coords]
    ys = [coord[1] for coord in coords]
    with PdfPages(output_path) as pdf:
        fig = plt.figure(figsize=(8.27, 11.69))
        fig.suptitle("Relatorio Executivo de Transporte Urbano", fontsize=18, fontweight="bold", y=.97)
        fig.text(.08, .935, f"Gerado em: {result['metadata']['generated_at']} | Motor: OSRM (driving)", fontsize=8, color="#555")
        ax = fig.add_axes([.08, .56, .84, .34])
        ax.plot(xs, ys, color="#174f7c", linewidth=2.0, zorder=1)
        for stop in result["ordered_stops"]:
            if stop["sequence"] == 0:
                ax.scatter(stop["longitude"], stop["latitude"], s=90, marker="s", color="#c0392b", zorder=3)
            else:
                ax.scatter(stop["longitude"], stop["latitude"], s=55, color="white", edgecolor="#174f7c", linewidth=1.5, zorder=3)
                ax.text(stop["longitude"], stop["latitude"], str(stop["sequence"]), ha="center", va="center", fontsize=6, zorder=4)
        route_title = "Optimized route over the road network" if result["metadata"].get("roundtrip") else "Ground dispatches calculated over the road network"
        ax.set_title(route_title, fontsize=11)
        ax.set_aspect("equal", adjustable="datalim")
        ax.grid(alpha=.2)
        ax.tick_params(labelsize=6)
        cards = [
            ("DISTANCIA", f"{summary['distance_km']:.2f} km"),
            ("TEMPO TOTAL", f"{summary['total_minutes']:.1f} min"),
            ("COMBUSTIVEL", f"{summary['estimated_fuel_l']:.2f} L"),
            ("CUSTO ESTIMADO", f"R$ {summary['estimated_fuel_cost_brl']:.2f}"),
        ]
        for i, (label, value) in enumerate(cards):
            x = .08 + i * .215
            fig.text(x, .49, label, fontsize=8, color="#555")
            fig.text(x, .455, value, fontsize=15, fontweight="bold", color="#173f61")
        fig.text(.08, .405, "Indicadores operacionais", fontsize=12, fontweight="bold")
        indicators = [
            ("Entregas", summary["deliveries"]),
            ("Travel time", f"{summary['driving_minutes']:.2f} min"),
            ("Service time", f"{summary['service_minutes']:.2f} min"),
            ("Calculated average speed", f"{summary['average_speed_kmh']:.2f} km/h"),
            ("Consumo adotado", f"{summary['fuel_efficiency_km_l']:.2f} km/L"),
            ("Emissao estimada", f"{summary['estimated_co2_kg']:.2f} kg CO2"),
        ]
        y = .37
        for label, value in indicators:
            fig.text(.09, y, label, fontsize=9)
            fig.text(.67, y, str(value), fontsize=9, fontweight="bold")
            y -= .035
        fig.text(.08, .13, "Notas metodologicas", fontsize=11, fontweight="bold")
        fig.text(.08, .105, f"Distancia, duracao e geometria foram calculadas por {result['metadata']['routing_api']} no perfil driving.", fontsize=8)
        fig.text(.08, .085, "Fuel, cost, and CO2 are parameterized estimates; real-time congestion is not included.", fontsize=8)
        pdf.savefig(fig)
        plt.close(fig)

        rows_per_page = 13
        legs = result["legs"]
        for page_start in range(0, len(legs), rows_per_page):
            fig, ax = plt.subplots(figsize=(8.27, 11.69))
            ax.axis("off")
            fig.suptitle("Route leg details", fontsize=16, fontweight="bold", y=.96)
            page_legs = legs[page_start:page_start + rows_per_page]
            table_data = []
            for leg in page_legs:
                table_data.append([
                    leg["sequence"],
                    f"{leg['origin']} -> {leg['destination']}",
                    leg["street"][:30],
                    f"{leg['distance_km']:.3f}",
                    f"{leg['duration_min']:.2f}",
                ])
            table = ax.table(
                cellText=table_data,
                colLabels=["#", "Origem -> Destino", "Endereco", "km", "min"],
                colWidths=[.05, .37, .32, .1, .1],
                cellLoc="left",
                loc="upper center",
                bbox=[.03, .22, .94, .67],
            )
            table.auto_set_font_size(False)
            table.set_fontsize(7.5)
            table.scale(1, 1.6)
            for (row, _), cell in table.get_celld().items():
                if row == 0:
                    cell.set_facecolor("#174f7c")
                    cell.set_text_props(color="white", fontweight="bold")
                elif row % 2 == 0:
                    cell.set_facecolor("#eef3f7")
            fig.text(.07, .15, "Times are routing-engine estimates and may vary with traffic, road work, and temporary restrictions.", fontsize=8)
            pdf.savefig(fig)
            plt.close(fig)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments that configure inputs, outputs, and routing behavior."""
    base_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Generates a ground urban transport route and report")
    parser.add_argument("--farmacias", type=Path, default=base_dir / "dados_com_coordenadas(Sheet1).csv")
    parser.add_argument("--pedidos", type=Path, default=base_dir / "pedidos_belo_horizonte.csv")
    parser.add_argument("--saida", type=Path, default=base_dir / "saida_transporte_urbano")
    parser.add_argument("--farmacia-base")
    parser.add_argument("--max-pedidos", type=int, default=20)
    parser.add_argument("--osrm-url", default=os.environ.get("OSRM_BASE_URL", DEFAULT_OSRM))
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--consumo-km-l", type=float, default=10.0)
    parser.add_argument("--preco-combustivel", type=float, default=6.20)
    parser.add_argument("--co2-kg-l", type=float, default=2.31)
    parser.add_argument("--tempo-parada-min", type=float, default=3.0)
    parser.add_argument("--cache-osrm", type=Path, default=base_dir / "saida_rotas_pedidos" / "rotas_farmacias.json")
    parser.add_argument("--usar-cache", action="store_true", help="Usa diretamente as respostas OSRM ja salvas")
    parser.add_argument("--sem-cache", action="store_true", help="Falha se a consulta online nao responder")
    return parser.parse_args()


def main() -> None:
    """Run the script workflow from command-line parsing through output generation."""
    args = parse_args()
    args.saida.mkdir(parents=True, exist_ok=True)
    base = load_base(args.farmacias, args.farmacia_base)
    deliveries = load_deliveries(args.pedidos, args.max_pedidos)
    points = [base, *deliveries]
    print(f"[1/5] Preparando calculo OSRM para {len(deliveries)} entregas...")
    started = time.monotonic()
    payload = None
    try:
        if args.usar_cache:
            raise requests.ConnectionError("cache mode requested")
        else:
            payload = call_osrm_trip(points, args.osrm_url, args.timeout)
            print(f"      Resposta recebida em {time.monotonic() - started:.1f}s")
            result = build_result(
                points,
                payload,
                fuel_km_l=args.consumo_km_l,
                fuel_price=args.preco_combustivel,
                co2_kg_l=args.co2_kg_l,
                stop_minutes=args.tempo_parada_min,
            )
            result["metadata"]["api_base_url"] = args.osrm_url
    except requests.RequestException as exc:
        if args.sem_cache or not args.cache_osrm.exists():
            raise
        print(f"      API indisponivel ({exc.__class__.__name__}); usando cache OSRM: {args.cache_osrm}")
        result = build_cached_dispatch_result(
            args.cache_osrm,
            base,
            deliveries,
            fuel_km_l=args.consumo_km_l,
            fuel_price=args.preco_combustivel,
            co2_kg_l=args.co2_kg_l,
            stop_minutes=args.tempo_parada_min,
        )
    print("[2/5] Gravando JSON e GeoJSON...")
    (args.saida / "relatorio_rota_urbana.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if payload is not None:
        (args.saida / "resposta_osrm_original.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    write_geojson(result, args.saida / "rota_urbana.geojson")
    print("[3/5] Generating four interactive maps...")
    write_html_maps(result, args.saida)
    print("[4/5] Generating PDF report...")
    render_report(result, args.saida / "relatorio_transporte_urbano.pdf")
    print("[5/5] Done")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()



