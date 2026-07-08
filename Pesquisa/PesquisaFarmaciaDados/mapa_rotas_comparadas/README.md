# Mapa comparativo: drone x rota urbana

Esta pasta concentra uma versao comparativa sem apagar os scripts anteriores.

## Arquivos principais

- `gerar_mapa_comparativo.py`: gera um unico mapa HTML com as duas rotas.
- `dados_entrada/coordenadas_drone.json`: copia dos dados da rota de drone.
- `dados_entrada/relatorio_rota_urbana.json`: copia do relatorio da rota urbana.
- `dados_entrada/rota_urbana.geojson`: copia da geometria urbana.
- `codigos_reaproveitados/`: copias dos scripts usados como referencia.

## Como gerar o mapa

Execute a partir da raiz do projeto:

```powershell
.\venv\Scripts\python.exe .\PesquisaFarmaciaDados\mapa_rotas_comparadas\gerar_mapa_comparativo.py
```

## Saidas

- `saida/mapa_drone_urbano.html`: mapa interativo com rota urbana em azul e rota drone em vermelho tracejado.
- `saida/rotas_drone_urbano.geojson`: arquivo GeoJSON com as duas rotas e os pontos.
- `saida/resumo_comparativo.json`: resumo numerico da comparacao.

