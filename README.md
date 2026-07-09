# DronePharm Research

Research repository for the **DronePharm** project, prepared to accompany a paper on route planning for medication deliveries by **drone** and **urban transport** in Belo Horizonte, MG (Brazil).

The repository includes:

- Pharmacy data registered from the Brazilian Federal Government website
- Geocoding with OpenStreetMap/Nominatim
- Ground routes computed with OpenStreetMap data via OSRM
- Drone route defined by geographic waypoints
- HTML maps, GeoJSON files, JSON reports, and PDF reports

---

## Table of Contents

1. [Main Result](#main-result)
2. [Data Sources](#data-sources)
3. [Route Scripts](#route-scripts)
4. [Generated Files](#generated-files)
   - [Pharmacy-to-Order Routes](#pharmacy-to-order-routes)
   - [Urban Transport](#urban-transport)
   - [Drone Route](#drone-route)
   - [Comparative Map](#comparative-map)
5. [Delivery Points](#delivery-points)

---

## Main Result

| Mode | Distance | Travel Time | Total Time | Notes |
| --- | ---: | ---: | ---: | --- |
| Urban transport | 65.603 km | 108.82 min | 168.81 min | includes 60 min of service time |
| Drone | 34.6513 km | 67.75 min | 67.75 min | feasible route, 4.82 kg payload |

### Comparative Summary

| Indicator | Value |
| --- | ---: |
| Distance reduction | 30.9517 km |
| Percentage reduction | 47.18% |
| Estimated drone energy | 895.56 Wh |
| Estimated urban fuel consumption | 6.56 L |
| Estimated urban fuel cost | R$ 40.67 |
| Estimated urban emissions | 15.154 kg CO2 |

Summary source: [`resumo_comparativo.json`](experimental_setup/output/resumo_comparativo.json)

---

## Data Sources

Pharmacies were registered from data obtained on the Brazilian Federal Government website. The spreadsheets downloaded per municipality are located at:
[`downloads_farmacias/`](data/scripts/downloads_farmacias/)

### Files Derived from Pharmacy Data

| File | Content |
| --- | --- |
| [`consolidado_farmacias.xlsx`](data/scripts/consolidado_farmacias.xlsx) | Consolidated spreadsheet of pharmacies by municipality |
| [`farmacias_com_coordenadas.xlsx`](data/scripts/farmacias_com_coordenadas.xlsx) | Pharmacies with latitude and longitude |
| [`dados_com_coordenadas.csv`](data/dados_com_coordenadas.csv) | CSV base used in the route scripts |
| [`farmacias_processadas.csv`](data/scripts/saida_rotas/farmacias_processadas.csv) | Pharmacies filtered for the experiment |

Orders used in the scenario: [`pedidos_belo_horizonte.csv`](data/pedidos_belo_horizonte.csv)

> **OpenStreetMap** was used to geocode addresses, display base maps, and trace ground routes over the road network. Ground route queries were performed via **OSRM**.

---

## Route Scripts

| File | Function |
| --- | --- |
| [`pharms.py`](data/scripts/pharms.py) | Consolidates pharmacy spreadsheets downloaded per municipality |
| [`cords.py`](data/scripts/cords.py) | Geocodes pharmacies using Nominatim/OpenStreetMap |
| [`gerar_rotas_farmacias.py`](data/scripts/gerar_rotas_farmacias.py) | Generates routes between pharmacies and orders, exporting JSON, GeoJSON, and HTML |
| [`gerar_transporte_urbano.py`](maps/scripts/gerar_transporte_urbano.py) | Calculates the urban route with the OSRM Trip API and generates maps/reports |
| [`plot_rota.py`](experimental_setup/scripts/plot_rota.py) | Generates drone route maps in different layers |
| [`relatorio_telemetria.py`](experimental_setup/scripts/relatorio_telemetria.py) | Generates a PDF telemetry report for the drone route |
| [`gerar_mapa_comparativo.py`](maps/scripts/gerar_mapa_comparativo.py) | Generates a map and GeoJSON comparing the urban route and the drone route |
| [`maps/`](maps/) | Comparative maps, drone flight paths, ground vehicle maps, and order maps |

---

## Generated Files

### Pharmacy-to-Order Routes

Folder: [`data/scripts/saida_rotas/`](data/scripts/saida_rotas/)

| File | Content |
| --- | --- |
| [`rotas_farmacias.json`](data/scripts/saida_rotas/rotas_farmacias.json) | Complete data of routes between pharmacies and orders |
| [`rotas_farmacias.geojson`](data/scripts/saida_rotas/rotas_farmacias.geojson) | Geometries in GIS format |
| [`rotas_farmacias_mapa.html`](data/scripts/saida_rotas/rotas_farmacias_mapa.html) | Interactive map |
| [`farmacias_processadas.csv`](data/scripts/saida_rotas/farmacias_processadas.csv) | Pharmacies used in the generation |

**Summary of the 5 selected pharmacies**

| Pharmacy | Latitude | Longitude | Routes | Total Distance | Total Time |
| --- | ---: | ---: | ---: | ---: | ---: |
| AG FARMA LTDA - ME | -19.9162884 | -43.9378304 | 20 | 65.602 km | 108.83 min |
| ALFENAS E OLIVEIRA DROGARIA E PERFUMARIA LTDA | -19.8861502 | -43.9002370 | 20 | 181.952 km | 278.06 min |
| AMC DROGARIA LTDA - ME | -19.9186817 | -43.8785493 | 20 | 195.353 km | 291.45 min |
| APOLITANA FERNANDA GONCALVES | -19.9569769 | -43.9541110 | 20 | 118.094 km | 190.40 min |
| AVANTE FORMULA LTDA - ME | -19.8736074 | -43.9197268 | 20 | 178.513 km | 264.69 min |

---

### Urban Transport

Folder: [`experimental_setup/input/`](experimental_setup/input/)

| File | Content |
| --- | --- |
| [`relatorio_rota_urbana.json`](experimental_setup/input/relatorio_rota_urbana.json) | Metrics, stops, legs, and geometry of the urban route |
| [`rota_urbana.geojson`](experimental_setup/input/rota_urbana.geojson) | Urban route geometry |
| [`relatorio_transporte_urbano.md`](experimental_setup/reports/relatorio_transporte_urbano.md) | Executive report |
| [`mapa_terrestre_osm.html`](maps/ground_vehicle_route/mapa_terrestre_osm.html) | Map with OpenStreetMap layer |
| [`mapa_terrestre_claro.html`](maps/ground_vehicle_route/mapa_terrestre_claro.html) | Map with light layer |
| [`mapa_terrestre_ruas.html`](maps/ground_vehicle_route/mapa_terrestre_ruas.html) | Map with street layer |
| [`mapa_terrestre_satelite.html`](maps/ground_vehicle_route/mapa_terrestre_satelite.html) | Map with satellite layer |

**Urban Base**

| Field | Value |
| --- | --- |
| Pharmacy | AG FARMA LTDA - ME |
| Street | RIO DE JANEIRO |
| Latitude | -19.9162884 |
| Longitude | -43.9378304 |

**Urban Metrics**

| Metric | Value |
| --- | ---: |
| Deliveries | 20 |
| Distance | 65.603 km |
| Driving time | 108.82 min |
| Service time | 60.00 min |
| Total time | 168.81 min |
| Average speed | 36.17 km/h |
| Estimated fuel | 6.56 L |
| Estimated cost | R$ 40.67 |
| Estimated CO2 | 15.154 kg |

**Legs Recorded in the Urban Report**

| Seq. | Destination | Street | Distance | Time |
| ---: | --- | --- | ---: | ---: |
| 1 | pedido_1 | Avenida Afonso Pena | 1.448 km | 2.61 min |
| 2 | pedido_2 | Rua da Bahia | 1.278 km | 2.19 min |
| 3 | pedido_3 | Avenida do Contorno | 3.038 km | 5.71 min |
| 4 | pedido_4 | Rua Rio de Janeiro | 1.060 km | 1.93 min |
| 5 | pedido_5 | Avenida Amazonas | 2.529 km | 4.78 min |
| 6 | pedido_6 | Rua dos Tupis | 1.298 km | 2.18 min |
| 7 | pedido_7 | Rua Curitiba | 1.000 km | 1.69 min |
| 8 | pedido_8 | Avenida Cristovao Colombo | 2.730 km | 4.40 min |
| 9 | pedido_9 | Rua dos Goitacazes | 2.051 km | 3.49 min |
| 10 | pedido_10 | Avenida Prudente de Morais | 3.775 km | 6.46 min |
| 11 | pedido_11 | Rua Padre Eustaquio | 5.216 km | 8.16 min |
| 12 | pedido_12 | Avenida Silva Lobo | 5.934 km | 9.84 min |
| 13 | pedido_13 | Rua Platina | 4.676 km | 6.74 min |
| 14 | pedido_14 | Avenida Nossa Senhora do Carmo | 4.582 km | 7.04 min |
| 15 | pedido_15 | Rua Itajuba | 3.062 km | 5.25 min |
| 16 | pedido_16 | Avenida Antonio Carlos | 8.031 km | 12.78 min |
| 17 | pedido_17 | Rua Jacui | 4.630 km | 6.67 min |
| 18 | pedido_18 | Avenida Raja Gabaglia | 6.811 km | 11.94 min |
| 19 | pedido_19 | Rua Carijos | 0.962 km | 2.26 min |
| 20 | pedido_20 | Avenida Bias Fortes | 1.491 km | 2.71 min |

---

### Drone Route

**Main Files**

| File | Content |
| --- | --- |
| [`coordenadas.json`](experimental_setup/input/coordenadas.json) | Waypoints, payload, energy, cost, and feasibility |
| [`relatorio_telemetria_rota.md`](experimental_setup/reports/relatorio_telemetria_rota.md) | Telemetry report |
| [`rota_drone_openstreetmap.html`](maps/drone_flight_path/rota_drone_openstreetmap.html) | Map with OpenStreetMap |
| [`rota_drone_satelite_esri.html`](maps/drone_flight_path/rota_drone_satelite_esri.html) | Map with satellite view |
| [`rota_drone_cartodb_positron.html`](maps/drone_flight_path/rota_drone_cartodb_positron.html) | Map with CartoDB Positron |
| [`rota_drone_cartodb_voyager.html`](maps/drone_flight_path/rota_drone_cartodb_voyager.html) | Map with CartoDB Voyager |
| [`rota_drone_mapas.pdf`](experimental_setup/scripts/rota_drone_mapas.pdf) | Route maps in PDF |
| [`maps/drone_flight_path/`](maps/drone_flight_path/) | Copies of the drone route maps |

**Drone Route Metrics**

| Metric | Value |
| --- | ---: |
| Drone | DP-067 |
| Orders | 20 |
| Distance | 34.6513 km |
| Time | 67.75 min |
| Energy | 895.56 Wh |
| Payload | 4.82 kg |
| Calculated cost | 7.4373488303617235 |
| Feasible | true |
| Status | calculated |

**Drone Route Waypoints**

| Seq. | Point | Latitude | Longitude |
| ---: | --- | ---: | ---: |
| 0 | Farmacia Popular Central - BH | -19.927800000000000 | -43.941600000000000 |
| 1 | Order #40 | -19.919483726154883 | -43.938615270418350 |
| 2 | Order #57 | -19.917620483165702 | -43.939528170462815 |
| 3 | Order #42 | -19.918264538170295 | -43.940782614835920 |
| 4 | Order #45 | -19.920578416382906 | -43.941286374158210 |
| 5 | Order #43 | -19.916835274609184 | -43.947361825190450 |
| 6 | Order #47 | -19.914862507361940 | -43.944905172638140 |
| 7 | Order #44 | -19.913427681540828 | -43.942713508214695 |
| 8 | Order #55 | -19.886731540286174 | -43.928164730518420 |
| 9 | Order #54 | -19.869284615730482 | -43.963817250481940 |
| 10 | Order #49 | -19.907451836204714 | -43.970618452930180 |
| 11 | Order #51 | -19.922738154607280 | -43.967140285719640 |
| 12 | Order #37 | -19.924546633388367 | -43.991457695771370 |
| 13 | Order #50 | -19.936170452819365 | -43.977283615024860 |
| 14 | Order #56 | -19.957183604715830 | -43.965372840615930 |
| 15 | Order #52 | -19.952641380274915 | -43.938174620583716 |
| 16 | Order #48 | -19.941386205718462 | -43.951274608315730 |
| 17 | Order #41 | -19.932874165308743 | -43.944128536709215 |
| 18 | Order #46 | -19.935682174509317 | -43.927514836205470 |
| 19 | Order #53 | -19.930482715603947 | -43.921735184620570 |
| 20 | Order #39 | -19.924057381245670 | -43.935237184562915 |
| 21 | Farmacia Popular Central - BH | -19.927800000000000 | -43.941600000000000 |

---

### Comparative Map

Folder: [`maps/comparative/`](maps/comparative/)

| File | Content |
| --- | --- |
| [`mapa_drone_urbano.html`](maps/comparative/mapa_drone_urbano.html) | Single map comparing the urban route and the drone route |
| [`rotas_drone_urbano.geojson`](experimental_setup/output/rotas_drone_urbano.geojson) | Geometries of both routes and points |
| [`resumo_comparativo.json`](experimental_setup/output/resumo_comparativo.json) | Final comparison metrics |
| [`relatorio_rota_urbana.json`](experimental_setup/input/relatorio_rota_urbana.json) | Urban input used in the comparison |
| [`rota_urbana.geojson`](experimental_setup/input/rota_urbana.geojson) | Urban geometry used in the comparison |
| [`coordenadas.json`](experimental_setup/input/coordenadas.json) | Drone route input used in the comparison |

---

## Delivery Points

| Order | Street | Latitude | Longitude |
| --- | --- | ---: | ---: |
| pedido_1 | Avenida Afonso Pena | -19.924057381245670 | -43.935237184562915 |
| pedido_2 | Rua da Bahia | -19.919483726154883 | -43.938615270418350 |
| pedido_3 | Avenida do Contorno | -19.932874165308743 | -43.944128536709215 |
| pedido_4 | Rua Rio de Janeiro | -19.918264538170295 | -43.940782614835920 |
| pedido_5 | Avenida Amazonas | -19.916835274609184 | -43.947361825190450 |
| pedido_6 | Rua dos Tupis | -19.913427681540828 | -43.942713508214695 |
| pedido_7 | Rua Curitiba | -19.920578416382906 | -43.941286374158210 |
| pedido_8 | Avenida Cristovao Colombo | -19.935682174509317 | -43.927514836205470 |
| pedido_9 | Rua dos Goitacazes | -19.914862507361940 | -43.944905172638140 |
| pedido_10 | Avenida Prudente de Morais | -19.941386205718462 | -43.951274608315730 |
| pedido_11 | Rua Padre Eustaquio | -19.907451836204714 | -43.970618452930180 |
| pedido_12 | Avenida Silva Lobo | -19.936170452819365 | -43.977283615024860 |
| pedido_13 | Rua Platina | -19.922738154607280 | -43.967140285719640 |
| pedido_14 | Avenida Nossa Senhora do Carmo | -19.952641380274915 | -43.938174620583716 |
| pedido_15 | Rua Itajuba | -19.930482715603947 | -43.921735184620570 |
| pedido_16 | Avenida Antonio Carlos | -19.869284615730482 | -43.963817250481940 |
| pedido_17 | Rua Jacui | -19.886731540286174 | -43.928164730518420 |
| pedido_18 | Avenida Raja Gabaglia | -19.957183604715830 | -43.965372840615930 |
| pedido_19 | Rua Carijos | -19.917620483165702 | -43.939528170462815 |
| pedido_20 | Avenida Bias Fortes | -19.926174350284620 | -43.937184205731945 |
