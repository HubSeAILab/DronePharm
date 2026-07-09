"""
Executive Telemetry and Route Feasibility Report
=========================================================

Modular script for:
1. Loading settings (settings.json) and the route (coordinates.json);
2. Calculating geodesic distances (Haversine), bearings, and wind impact
   on cruise speed (ground speed);
3. Estimating flight time, energy use, financial cost, efficiency
   and battery margin (SoC);
4. Generating an executive PDF report (reportlab) with a KPI dashboard,
   a detailed navigation table, and a footer with page numbering.

Author: Software Engineering - Autonomous Logistics and Telemetry
"""

from __future__ import annotations

import json
import math
import os
from datetime import datetime
from typing import Any, Dict, List, Tuple

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# ---------------------------------------------------------------------------
# Global constants
# ---------------------------------------------------------------------------

RAIO_TERRA_KM: float = 6371.0  # Mean Earth radius used in the Haversine formula


# ---------------------------------------------------------------------------
# Data loading and processing
# ---------------------------------------------------------------------------

def carregar_json(caminho: str) -> Dict[str, Any]:
    """Loads and returns the contents of a JSON file.

    Args:
        caminho: Absolute or relative path to the JSON file.

    Returns:
        Dictionary (or list, depending on the structure) with the JSON contents.

    Raises:
        FileNotFoundError: If the file does not exist at the given path.
        ValueError: If the file contents are not valid JSON.
    """
    if not os.path.isfile(caminho):
        raise FileNotFoundError(f"File not found: '{caminho}'")

    try:
        with open(caminho, "r", encoding="utf-8") as arquivo:
            return json.load(arquivo)
    except json.JSONDecodeError as erro:
        raise ValueError(f"Invalid JSON in '{caminho}': {erro}") from erro


def carregar_dados(
    caminho_settings: str, caminho_coordenadas: str
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Loads and normalizes settings and route data.

    The function accepts both the "complete" format (with financial,
    environmental, and electrical drone keys) and the simplified format already
    present in the sample files provided by the user, applying
    sensible default values when a key is missing.

    Args:
        caminho_settings: Path to the settings.json file.
        caminho_coordenadas: Path to the coordinates.json file.

    Returns:
        A tuple (configuracoes, pontos_rota), where:
            - configuracoes is an already-normalized dictionary with all
              parameters required for the calculations;
            - pontos_rota is a list of dictionaries in the format
              {"nome": str, "lat": float, "lng": float}.

    Raises:
        FileNotFoundError: If any file does not exist.
        ValueError: If any file has invalid JSON or the
            coordinate structure is empty/incomplete.
    """
    settings_bruto = carregar_json(caminho_settings)
    coordenadas_bruto = carregar_json(caminho_coordenadas)

    configuracoes = _normalizar_settings(settings_bruto)
    pontos_rota = _normalizar_coordenadas(coordenadas_bruto)

    if len(pontos_rota) < 2:
        raise ValueError(
            "The coordinates file must contain at least 2 points to "
            "form a route."
        )

    return configuracoes, pontos_rota


def _normalizar_settings(dados: Dict[str, Any]) -> Dict[str, Any]:
    """Normalizes the settings dictionary into a single format.

    Supports two input formats:
      1. "Example" format described in the prompt (chaves diretas, ex.:
         drone.velocidade_cruzeiro_kmh).
      2. "Real" format provided by the user (settings.json com a estrutura
         parametros_fisicos_e_operacionais / limites_operacionais, em que
         each parameter is an object {"valor": ..., "unidade": ..., ...}).

    Args:
        dados: Raw dictionary loaded from settings.json.

    Returns:
        Normalized dictionary containing the keys:
            drone: velocidade_cruzeiro_kmh, consumo_nominal_w,
                   capacidade_bateria_wh, tensao_nominal_v
            ambiente: direcao_vento_graus, velocidade_vento_kmh
            financeiro: custo_kwh, taxa_depreciacao_por_voo
    """

    drone_bruto = dados.get("drone", {})
    ambiente_bruto = dados.get("ambiente", dados.get("vento", {}))
    financeiro_bruto = dados.get("financeiro", {})

    # --- Detects whether the data uses the "complex" format (com sub-objetos valor/unidade)
    parametros = drone_bruto.get("parametros_fisicos_e_operacionais")

    if parametros:
        # User-provided real format: extracts numeric values from sub-objects.
        def _valor(chave: str, padrao: float) -> float:
            """Extract a numeric setting value from the complex settings format."""
            item = parametros.get(chave)
            if isinstance(item, dict):
                return float(item.get("valor", padrao))
            if item is not None:
                return float(item)
            return padrao

        velocidade_kmh = _valor("velocidade_kmh", 36.0)
        consumo_base_wh_km = _valor("consumo_base_wh_km", 15.0)
        autonomia_max_km = _valor("autonomia_max_km", 10.0)

        # Battery capacity estimated from range and consumption
        # base (Wh/km), since the real format does not provide Wh directly.
        capacidade_bateria_wh = autonomia_max_km * consumo_base_wh_km

        # Nominal consumption in watts: consumption (Wh/km) * speed (km/h)
        # results in Wh/h = W.
        consumo_nominal_w = consumo_base_wh_km * velocidade_kmh

        tensao_nominal_v = 22.2  # Default value (not provided in the real format)

        limites_vento = dados.get("vento", {}).get("limites_operacionais", {})

        def _valor_vento(chave: str, padrao: float) -> float:
            """Extract a numeric wind-limit value from the complex settings format."""
            item = limites_vento.get(chave)
            if isinstance(item, dict):
                return float(item.get("valor", padrao))
            if item is not None:
                return float(item)
            return padrao

        # The real format does not provide wind direction/speed per flight;
        # assumes no wind (0 km/h) as a conservative default.
        direcao_vento_graus = float(
            ambiente_bruto.get("direcao_vento_graus", 0.0)
        )
        velocidade_vento_kmh = float(
            ambiente_bruto.get("velocidade_vento_kmh", 0.0)
        )

        custo_kwh = float(financeiro_bruto.get("custo_kwh", 0.85))
        taxa_depreciacao = float(
            financeiro_bruto.get("taxa_depreciacao_por_voo", 5.00)
        )

    else:
        # Simplified "example" format, as described in the prompt.
        velocidade_kmh = float(drone_bruto.get("velocidade_cruzeiro_kmh", 50.0))
        consumo_nominal_w = float(drone_bruto.get("consumo_nominal_w", 400.0))
        capacidade_bateria_wh = float(
            drone_bruto.get("capacidade_bateria_wh", 550.0)
        )
        tensao_nominal_v = float(drone_bruto.get("tensao_nominal_v", 22.2))

        direcao_vento_graus = float(
            ambiente_bruto.get("direcao_vento_graus", 0.0)
        )
        velocidade_vento_kmh = float(
            ambiente_bruto.get("velocidade_vento_kmh", 0.0)
        )

        custo_kwh = float(financeiro_bruto.get("custo_kwh", 0.85))
        taxa_depreciacao = float(
            financeiro_bruto.get("taxa_depreciacao_por_voo", 5.00)
        )

    return {
        "drone": {
            "velocidade_cruzeiro_kmh": velocidade_kmh,
            "consumo_nominal_w": consumo_nominal_w,
            "capacidade_bateria_wh": capacidade_bateria_wh,
            "tensao_nominal_v": tensao_nominal_v,
        },
        "ambiente": {
            "direcao_vento_graus": direcao_vento_graus,
            "velocidade_vento_kmh": velocidade_vento_kmh,
        },
        "financeiro": {
            "custo_kwh": custo_kwh,
            "taxa_depreciacao_por_voo": taxa_depreciacao,
        },
    }


def _normalizar_coordenadas(dados: Any) -> List[Dict[str, Any]]:
    """Normalizes the coordinate structure into a list of points.

    Supports two formats:
      1. List of points {"nome": str, "lat": float, "lng": float}
         (example format from the prompt).
      2. Dictionary with the "waypoints_json" key containing a list of
         objetos {"seq", "latitude", "longitude", "altitude", "label"}
         (real format provided by the user).

    Args:
        dados: Raw content from coordinates.json (list or dictionary).

    Returns:
        List of points no formato {"nome": str, "lat": float, "lng": float}.
    """
    if isinstance(dados, list):
        pontos = []
        for item in dados:
            pontos.append(
                {
                    "nome": str(item.get("nome", "Ponto")),
                    "lat": float(item["lat"]),
                    "lng": float(item["lng"]),
                }
            )
        return pontos

    if isinstance(dados, dict) and "waypoints_json" in dados:
        waypoints = sorted(dados["waypoints_json"], key=lambda w: w.get("seq", 0))
        pontos = []
        for wp in waypoints:
            pontos.append(
                {
                    "nome": str(wp.get("label", f"Waypoint {wp.get('seq', '')}")),
                    "lat": float(wp["latitude"]),
                    "lng": float(wp["longitude"]),
                }
            )
        return pontos

    raise ValueError(
        "Unrecognized coordinate format. Expected a list of "
        "points or a dictionary with the key 'waypoints_json'."
    )


# ---------------------------------------------------------------------------
# Geographic calculations
# ---------------------------------------------------------------------------

def calcular_haversine(
    lat1: float, lng1: float, lat2: float, lng2: float
) -> float:
    """Calculates the geodesic distance between two points using Haversine.

    Args:
        lat1: Origin point latitude (graus decimais).
        lng1: Origin point longitude (graus decimais).
        lat2: Destination point latitude (graus decimais).
        lng2: Destination point longitude (graus decimais).

    Returns:
        Distance between the two points in kilometers.
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return RAIO_TERRA_KM * c


def calcular_azimute(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculates the initial bearing between two geographic points.

    The bearing is the angle measured from true north (0 degrees),
    clockwise, indicating the direction from the origin point to the
    de destino.

    Args:
        lat1: Origin point latitude (graus decimais).
        lng1: Origin point longitude (graus decimais).
        lat2: Destination point latitude (graus decimais).
        lng2: Destination point longitude (graus decimais).

    Returns:
        Azimute em graus, no intervalo [0, 360).
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_lambda = math.radians(lng2 - lng1)

    x = math.sin(delta_lambda) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(
        delta_lambda
    )

    azimute_rad = math.atan2(x, y)
    azimute_graus = (math.degrees(azimute_rad) + 360.0) % 360.0

    return azimute_graus


# ---------------------------------------------------------------------------
# Wind speed adjustment (vector decomposition)
# ---------------------------------------------------------------------------

def ajustar_velocidade_vento(
    velocidade_cruzeiro_kmh: float,
    azimute_trecho_graus: float,
    direcao_vento_graus: float,
    velocidade_vento_kmh: float,
) -> float:
    """Calculates actual ground speed.

    Uses simple vector decomposition: projects the wind vector onto
    the drone travel direction, adding tailwind or
    subtracting headwind from the longitudinal component of wind speed.
    cruzeiro.

    Wind direction (direcao_vento_graus) is provided as the direction
    the wind comes from (meteorological convention), so its movement
    vector points toward (direcao_vento_graus + 180 degrees).

    Args:
        velocidade_cruzeiro_kmh: Drone cruise speed (km/h).
        azimute_trecho_graus: Bearing of the flight leg (graus).
        direcao_vento_graus: Wind origin direction (graus, 0 = Norte).
        velocidade_vento_kmh: Wind speed (km/h).

    Returns:
        Actual ground speed (ground speed) em km/h. O valor
        is limited to a minimum of 0.1 km/h to avoid flight times
        infinitos em casos extremos de vento de proa muito forte.
    """
    # Vetor de deslocamento do vento (para onde o vento sopra)
    direcao_deslocamento_vento = (direcao_vento_graus + 180.0) % 360.0

    # Angle between wind travel direction and drone bearing
    angulo_relativo = math.radians(
        direcao_deslocamento_vento - azimute_trecho_graus
    )

    # Wind component along the drone travel direction
    componente_vento_longitudinal = velocidade_vento_kmh * math.cos(angulo_relativo)

    ground_speed = velocidade_cruzeiro_kmh + componente_vento_longitudinal

    return max(ground_speed, 0.1)


# ---------------------------------------------------------------------------
# Full-route telemetry calculations
# ---------------------------------------------------------------------------

def calcular_telemetria_rota(
    configuracoes: Dict[str, Any], pontos_rota: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Calculates all telemetry metrics for the full route.

    Args:
        configuracoes: Normalized settings dictionary (ver
            `carregar_dados`).
        pontos_rota: List of route points (ver `carregar_dados`).

    Returns:
        Dictionary containing:
            - "trechos": list of dictionaries with details for each
              leg (origin, destination, distance, bearing, ground speed,
              time);
            - "resumo": dictionary with mission totals and KPIs
              (total distance, total time, consumption, cost, efficiency,
              final SoC, effective average speed, safety warning).
    """
    drone = configuracoes["drone"]
    ambiente = configuracoes["ambiente"]
    financeiro = configuracoes["financeiro"]

    velocidade_cruzeiro_kmh = drone["velocidade_cruzeiro_kmh"]
    consumo_nominal_w = drone["consumo_nominal_w"]
    capacidade_bateria_wh = drone["capacidade_bateria_wh"]

    direcao_vento_graus = ambiente["direcao_vento_graus"]
    velocidade_vento_kmh = ambiente["velocidade_vento_kmh"]

    custo_kwh = financeiro["custo_kwh"]
    taxa_depreciacao_por_voo = financeiro["taxa_depreciacao_por_voo"]

    trechos: List[Dict[str, Any]] = []
    distancia_total_km = 0.0
    tempo_total_h = 0.0

    for indice in range(len(pontos_rota) - 1):
        origem = pontos_rota[indice]
        destino = pontos_rota[indice + 1]

        distancia_km = calcular_haversine(
            origem["lat"], origem["lng"], destino["lat"], destino["lng"]
        )
        azimute_graus = calcular_azimute(
            origem["lat"], origem["lng"], destino["lat"], destino["lng"]
        )
        ground_speed_kmh = ajustar_velocidade_vento(
            velocidade_cruzeiro_kmh,
            azimute_graus,
            direcao_vento_graus,
            velocidade_vento_kmh,
        )

        tempo_h = distancia_km / ground_speed_kmh

        trechos.append(
            {
                "origem": origem["nome"],
                "destino": destino["nome"],
                "distancia_km": distancia_km,
                "azimute_graus": azimute_graus,
                "ground_speed_kmh": ground_speed_kmh,
                "tempo_h": tempo_h,
                "tempo_min": tempo_h * 60.0,
            }
        )

        distancia_total_km += distancia_km
        tempo_total_h += tempo_h

    # --- Total energy consumption ---
    consumo_total_wh = consumo_nominal_w * tempo_total_h

    # --- Financial analysis ---
    consumo_total_kwh = consumo_total_wh / 1000.0
    custo_energia = consumo_total_kwh * custo_kwh
    custo_total = custo_energia + taxa_depreciacao_por_voo

    # --- Energy efficiency (Wh/km) ---
    eficiencia_wh_km = (
        consumo_total_wh / distancia_total_km if distancia_total_km > 0 else 0.0
    )

    # --- Battery safety margin (SoC final) ---
    if capacidade_bateria_wh > 0:
        soc_final_percentual = max(
            0.0,
            (1.0 - (consumo_total_wh / capacidade_bateria_wh)) * 100.0,
        )
    else:
        soc_final_percentual = 0.0

    aviso_bateria_baixa = soc_final_percentual < 20.0

    # --- Effective average mission speed ---
    velocidade_media_efetiva_kmh = (
        distancia_total_km / tempo_total_h if tempo_total_h > 0 else 0.0
    )

    # --- Overall route safety status ---
    if aviso_bateria_baixa:
        status_seguranca = "WARNING: Insufficient battery for the complete route"
    elif soc_final_percentual < 30.0:
        status_seguranca = "ALERTA: Margem de bateria reduzida"
    else:
        status_seguranca = "Route is feasible within safety parameters"

    resumo = {
        "distancia_total_km": distancia_total_km,
        "tempo_total_h": tempo_total_h,
        "tempo_total_min": tempo_total_h * 60.0,
        "consumo_total_wh": consumo_total_wh,
        "consumo_total_kwh": consumo_total_kwh,
        "custo_energia": custo_energia,
        "taxa_depreciacao_por_voo": taxa_depreciacao_por_voo,
        "custo_total": custo_total,
        "eficiencia_wh_km": eficiencia_wh_km,
        "soc_final_percentual": soc_final_percentual,
        "velocidade_media_efetiva_kmh": velocidade_media_efetiva_kmh,
        "aviso_bateria_baixa": aviso_bateria_baixa,
        "status_seguranca": status_seguranca,
        "capacidade_bateria_wh": capacidade_bateria_wh,
    }

    return {"trechos": trechos, "resumo": resumo}


# ---------------------------------------------------------------------------
# PDF report generation
# ---------------------------------------------------------------------------

# Corporate color palette (restrained: dark blue + light gray)
COR_AZUL_ESCURO = colors.HexColor("#1F3A5F")
COR_AZUL_MEDIO = colors.HexColor("#3F6E91")
COR_CINZA_CLARO = colors.HexColor("#F2F4F7")
COR_CINZA_MEDIO = colors.HexColor("#D9DEE4")
COR_TEXTO = colors.HexColor("#2B2B2B")
COR_ALERTA = colors.HexColor("#B3261E")
COR_OK = colors.HexColor("#1E7B45")


def _construir_estilos() -> Dict[str, ParagraphStyle]:
    """Creates and returns the paragraph styles used in the report.

    Returns:
        Dictionary {style_name: ParagraphStyle}.
    """
    base = getSampleStyleSheet()

    estilos: Dict[str, ParagraphStyle] = {}

    estilos["titulo"] = ParagraphStyle(
        "TituloRelatorio",
        parent=base["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        textColor=COR_AZUL_ESCURO,
        alignment=TA_LEFT,
        spaceAfter=4,
    )

    estilos["subtitulo"] = ParagraphStyle(
        "Subtitulo",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=9,
        textColor=COR_TEXTO,
        alignment=TA_LEFT,
        spaceAfter=2,
    )

    estilos["secao"] = ParagraphStyle(
        "Secao",
        parent=base["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        textColor=COR_AZUL_ESCURO,
        spaceBefore=14,
        spaceAfter=8,
    )

    estilos["corpo"] = ParagraphStyle(
        "Corpo",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=10,
        textColor=COR_TEXTO,
        leading=14,
    )

    estilos["kpi_label"] = ParagraphStyle(
        "KpiLabel",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        textColor=colors.white,
        alignment=TA_CENTER,
    )

    estilos["kpi_valor"] = ParagraphStyle(
        "KpiValue",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=14,
        textColor=colors.white,
        alignment=TA_CENTER,
        spaceBefore=2,
    )

    estilos["status_ok"] = ParagraphStyle(
        "StatusOk",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        textColor=COR_OK,
    )

    estilos["status_alerta"] = ParagraphStyle(
        "StatusAlerta",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        textColor=COR_ALERTA,
    )

    return estilos


def _rodape(canvas_obj, doc) -> None:
    """Draws the footer with automatic page numbering.

    Args:
        canvas_obj: Objeto canvas do reportlab, fornecido automaticamente
            pelo SimpleDocTemplate.
        doc: Documento sendo renderizado, fornecido automaticamente.
    """
    canvas_obj.saveState()
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.setFillColor(COR_AZUL_MEDIO)

    largura_pagina, _ = A4
    canvas_obj.drawCentredString(
        largura_pagina / 2.0, 1.2 * cm, f"Page {doc.page}"
    )

    canvas_obj.setStrokeColor(COR_CINZA_MEDIO)
    canvas_obj.line(1.5 * cm, 1.5 * cm, largura_pagina - 1.5 * cm, 1.5 * cm)
    canvas_obj.restoreState()


def _montar_dashboard_kpis(
    resumo: Dict[str, Any], estilos: Dict[str, ParagraphStyle]
) -> Table:
    """Monta a tabela visual do dashboard de KPIs (resumo executivo).

    Args:
        resumo: "resumo" dictionary returned by `calcular_telemetria_rota`.
        estilos: Paragraph style dictionary.

    Returns:
        Objeto Table do reportlab pronto para ser inserido no documento.
    """
    if resumo["aviso_bateria_baixa"]:
        cor_status = COR_ALERTA
    else:
        cor_status = COR_OK

    kpis = [
        ("Total Distance", f"{resumo['distancia_total_km']:.2f} km"),
        (
            "Total Flight Time",
            f"{resumo['tempo_total_min']:.1f} min",
        ),
        ("Total Mission Cost", f"R$ {resumo['custo_total']:.2f}"),
        (
            "Bateria Restante (SoC)",
            f"{resumo['soc_final_percentual']:.1f} %",
        ),
    ]

    linha_labels = []
    linha_valores = []

    for label, valor in kpis:
        linha_labels.append(Paragraph(label.upper(), estilos["kpi_label"]))
        linha_valores.append(Paragraph(valor, estilos["kpi_valor"]))

    largura_coluna = (A4[0] - 3 * cm) / 4.0

    tabela_kpis = Table(
        [linha_labels, linha_valores],
        colWidths=[largura_coluna] * 4,
        rowHeights=[0.6 * cm, 0.9 * cm],
    )

    tabela_kpis.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), COR_AZUL_ESCURO),
                ("BACKGROUND", (3, 1), (3, 1), cor_status),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LINEAFTER", (0, 0), (-2, -1), 1, colors.white),
            ]
        )
    )

    return tabela_kpis


def _montar_tabela_navegacao(
    trechos: List[Dict[str, Any]], estilos: Dict[str, ParagraphStyle]
) -> Table:
    """Builds the detailed leg-by-leg navigation table.

    Args:
        trechos: Lista de trechos retornada por `calcular_telemetria_rota`.
        estilos: Paragraph style dictionary.

    Returns:
        Objeto Table do reportlab pronto para ser inserido no documento.
    """
    cabecalho = [
        "Origem âž” Destino",
        "Dist. (km)",
        "Azimute (Â°)",
        "Vel. c/ Vento (km/h)",
        "Time (min)",
    ]

    dados_tabela: List[List[Any]] = [cabecalho]

    for trecho in trechos:
        rota_texto = f"{trecho['origem']}\nâž” {trecho['destino']}"
        dados_tabela.append(
            [
                Paragraph(rota_texto.replace("\n", "<br/>"), estilos["corpo"]),
                f"{trecho['distancia_km']:.3f}",
                f"{trecho['azimute_graus']:.1f}",
                f"{trecho['ground_speed_kmh']:.2f}",
                f"{trecho['tempo_min']:.2f}",
            ]
        )

    largura_total = A4[0] - 3 * cm
    larguras_colunas = [
        largura_total * 0.40,
        largura_total * 0.15,
        largura_total * 0.15,
        largura_total * 0.15,
        largura_total * 0.15,
    ]

    tabela = Table(dados_tabela, colWidths=larguras_colunas, repeatRows=1)

    estilo_tabela = [
        ("BACKGROUND", (0, 0), (-1, 0), COR_AZUL_ESCURO),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.5, COR_CINZA_MEDIO),
    ]

    for indice_linha in range(1, len(dados_tabela)):
        cor_fundo = COR_CINZA_CLARO if indice_linha % 2 == 0 else colors.white
        estilo_tabela.append(
            ("BACKGROUND", (0, indice_linha), (-1, indice_linha), cor_fundo)
        )

    tabela.setStyle(TableStyle(estilo_tabela))
    return tabela


def gerar_pdf(
    caminho_output: str,
    configuracoes: Dict[str, Any],
    pontos_rota: List[Dict[str, Any]],
    telemetria: Dict[str, Any],
    arquivo_settings: str,
    arquivo_coordenadas: str,
) -> None:
    """Generates the executive telemetry report as a PDF.

    Args:
        caminho_output: Path to the PDF file to be generated.
        configuracoes: Normalized settings dictionary.
        pontos_rota: List of route points.
        telemetria: Dictionary returned by `calcular_telemetria_rota`
            (contains "trechos" and "resumo").
        arquivo_settings: Name/path of the settings file used
            (only for display in the report header).
        arquivo_coordenadas: Name/path of the coordinate file
            used (only for display in the report header).
    """
    estilos = _construir_estilos()
    resumo = telemetria["resumo"]
    trechos = telemetria["trechos"]

    documento = SimpleDocTemplate(
        caminho_output,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.8 * cm,
        title="Executive Telemetry and Route Feasibility Report",
    )

    elementos: List[Any] = []

    # --- Header ---
    elementos.append(
        Paragraph(
            "Executive Telemetry and Route Feasibility Report",
            estilos["titulo"],
        )
    )

    data_geracao = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    elementos.append(
        Paragraph(f"Generation date and time: {data_geracao}", estilos["subtitulo"])
    )
    elementos.append(
        Paragraph(
            f"Settings file: <b>{os.path.basename(arquivo_settings)}</b> "
            f"&nbsp;|&nbsp; Route file: "
            f"<b>{os.path.basename(arquivo_coordenadas)}</b>",
            estilos["subtitulo"],
        )
    )
    elementos.append(Spacer(1, 6))
    elementos.append(
        HRFlowable(width="100%", thickness=1.2, color=COR_AZUL_ESCURO)
    )
    elementos.append(Spacer(1, 12))

    # --- KPI dashboard ---
    elementos.append(Paragraph("Executive Summary (KPIs)", estilos["secao"]))
    elementos.append(_montar_dashboard_kpis(resumo, estilos))
    elementos.append(Spacer(1, 4))

    estilo_status = (
        estilos["status_alerta"]
        if resumo["aviso_bateria_baixa"]
        else estilos["status_ok"]
    )
    elementos.append(Spacer(1, 6))
    elementos.append(
        Paragraph(f"Safety Status: {resumo['status_seguranca']}", estilo_status)
    )

    if resumo["aviso_bateria_baixa"]:
        elementos.append(
            Paragraph(
                "SAFETY WARNING: the estimated battery level at the end of the mission "
                "is below the recommended minimum threshold of 20%. "
                "Reviewing the route, reducing the number of stops, "
                "or planning intermediate charging points is recommended.",
                estilos["corpo"],
            )
        )

    elementos.append(Spacer(1, 10))

    # --- Additional metrics ---
    elementos.append(Paragraph("Additional Operational Metrics", estilos["secao"]))

    dados_metricas = [
        ["Indicator", "Value"],
        [
            "Energy Efficiency",
            f"{resumo['eficiencia_wh_km']:.2f} Wh/km",
        ],
        [
            "Effective Average Mission Speed",
            f"{resumo['velocidade_media_efetiva_kmh']:.2f} km/h",
        ],
        [
            "Total Energy Consumption",
            f"{resumo['consumo_total_wh']:.2f} Wh "
            f"({resumo['consumo_total_kwh']:.4f} kWh)",
        ],
        [
            "Energy Cost",
            f"R$ {resumo['custo_energia']:.2f}",
        ],
        [
            "Depreciation Rate per Flight",
            f"R$ {resumo['taxa_depreciacao_por_voo']:.2f}",
        ],
        [
            "Total Battery Capacity",
            f"{resumo['capacidade_bateria_wh']:.2f} Wh",
        ],
    ]

    largura_total = A4[0] - 3 * cm
    tabela_metricas = Table(
        dados_metricas,
        colWidths=[largura_total * 0.6, largura_total * 0.4],
    )
    tabela_metricas.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), COR_AZUL_ESCURO),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("GRID", (0, 0), (-1, -1), 0.5, COR_CINZA_MEDIO),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COR_CINZA_CLARO]),
            ]
        )
    )
    elementos.append(tabela_metricas)
    elementos.append(Spacer(1, 10))

    # --- Detailed navigation table ---
    elementos.append(
        Paragraph("Navigation Route Details", estilos["secao"])
    )
    elementos.append(_montar_tabela_navegacao(trechos, estilos))

    documento.build(elementos, onFirstPage=_rodape, onLaterPages=_rodape)


# ---------------------------------------------------------------------------
# Main execution
# ---------------------------------------------------------------------------

def main() -> None:
    """Main function: orchestrates loading, calculation, and PDF generation."""

    # 1. Find the directory where this .py script is saved
    diretorio_atual = os.path.dirname(os.path.abspath(__file__))

    # 2. Build paths dynamically in the same folder as the script
    caminho_settings = os.path.join(diretorio_atual, "settings.json")
    caminho_coordenadas = os.path.join(diretorio_atual, "coordinates.json")
    caminho_output_pdf = os.path.join(diretorio_atual, "route_telemetry_report.pdf")

    try:
        configuracoes, pontos_rota = carregar_dados(
            caminho_settings, caminho_coordenadas
        )
    except (FileNotFoundError, ValueError) as erro:
        print(f"Error loading data: {erro}")
        return

    telemetria = calcular_telemetria_rota(configuracoes, pontos_rota)

    # Create the output folder if it does not exist (it will not be strictly necessary
    # if the PDF is saved in the same folder as the script, but it is good practice)
    os.makedirs(os.path.dirname(caminho_output_pdf), exist_ok=True)

    try:
        gerar_pdf(
            caminho_output_pdf,
            configuracoes,
            pontos_rota,
            telemetria,
            caminho_settings,
            caminho_coordenadas,
        )
    except Exception as erro:  # noqa: BLE001 - friendly error report
        print(f"Error generating PDF: {erro}")
        return

    resumo = telemetria["resumo"]
    print("Report generated successfully at:", caminho_output_pdf)
    print(f"Total distance: {resumo['distancia_total_km']:.2f} km")
    print(f"Total time: {resumo['tempo_total_min']:.1f} min")
    print(f"Total cost: R$ {resumo['custo_total']:.2f}")
    print(f"Estimated final SoC: {resumo['soc_final_percentual']:.1f} %")
    if resumo["aviso_bateria_baixa"]:
        print("WARNING: final SoC below 20% - review route feasibility.")


if __name__ == "__main__":
    main()



