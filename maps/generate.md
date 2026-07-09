# Mapa comparativo: drone x rota urbana

Esta pasta concentra uma versao comparativa sem apagar os scripts anteriores.

## Arquivos principais

- `scripts/generate_comparative_map.py`: gera um unico mapa HTML com as duas rotas.
- `experimental_setup/input/coordinates.json`: copia dos dados da rota de drone.
- `experimental_setup/input/urban_route_report.json`: copia do relatorio da rota urbana.
- `experimental_setup/input/urban_route.geojson`: copia da geometria urbana.
- `maps/scripts/`: scripts usados como referencia na comparacao.

## Como gerar o mapa

Execute a partir da raiz do projeto:

```powershell
.\venv\Scripts\python.exe .\maps\scripts\generate_comparative_map.py
```

## Saidas

- `output/drone_urban_map.html`: mapa interativo com rota urbana em azul e rota drone em vermelho tracejado.
- `output/drone_urban_routes.geojson`: arquivo GeoJSON com as duas rotas e os pontos.
- `output/comparative_summary.json`: resumo numerico da comparacao.

