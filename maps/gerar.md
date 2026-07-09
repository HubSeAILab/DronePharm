# Mapa comparativo: drone x rota urbana

Esta pasta concentra uma versao comparativa sem apagar os scripts anteriores.

## Arquivos principais

- `scripts/gerar_mapa_comparativo.py`: gera um unico mapa HTML com as duas rotas.
- `experimental_setup/input/coordenadas.json`: copia dos dados da rota de drone.
- `experimental_setup/input/relatorio_rota_urbana.json`: copia do relatorio da rota urbana.
- `experimental_setup/input/rota_urbana.geojson`: copia da geometria urbana.
- `maps/scripts/`: scripts usados como referencia na comparacao.

## Como gerar o mapa

Execute a partir da raiz do projeto:

```powershell
.\venv\Scripts\python.exe .\maps\scripts\gerar_mapa_comparativo.py
```

## Saidas

- `saida/mapa_drone_urbano.html`: mapa interativo com rota urbana em azul e rota drone em vermelho tracejado.
- `saida/rotas_drone_urbano.geojson`: arquivo GeoJSON com as duas rotas e os pontos.
- `saida/resumo_comparativo.json`: resumo numerico da comparacao.

