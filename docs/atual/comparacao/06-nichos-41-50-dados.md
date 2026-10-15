# Nichos 41–50 — Dados, IoT, clima e pecuária digital

## G-35 comparativo safra × safra (41) — ⚠️ só front

- Tela: linhas=safras; colunas=[produtividade, custo/ha, receita/ha, margem, chuva_mm]. Dados existem; sem model novo.

## G-36 instalação sensor + mapa (42) — ⚠️

- Estender `Device`: profundidade_cm, calibracao_data/proxima, bateria_pct, lat/lon + mapa por talhão (GeoJSON existente). Telemetria (~40 métricas, MQTT/LoRaWAN) existe.

## G-37 linha AB GNSS (43) — ❌ Gap

- `LinhaGuia` {talhao FK, ponto_A/B lat-lon, largura_implemento_m, sobreposicao_pct}. Sinal RTK é hardware (fora); linha AB é dado aberto.

## G-38 graus-dia + alerta (44) — ⚠️ código

- `GrausDia` {cultura, temp_base, acumulado da estacao} + `AlertaClimaTalhao` {tipo [geada, granizo], severidade}. Fontes INMET/NASA/Open-Meteo + proativo existem.

## G-39 NDVI + zonas (45) — ⚠️

- `SerieNDVI` {talhao, data, ndvi_medio, thumbnail, fonte} + `ZonaManejo` {geometria, classe [alta, media, baixa]} → alimenta `PrescricaoVRA`. Sentinel-2 é aberto (Copernicus).

## G-40 jornada máquina (46) — ⚠️

- `JornadaMaquina` {maquina FK, operador FK, inicio/fim, area_ha, consumo_l, l_ha, talhao, operacao}. Horímetro + GPS/RPM existem. JDLink é marca (fora).

## G-41 setor pivô (47) — ❌ Gap

- `SetorPivo` {equipamento, angulo_ini/fim, lamina_mm, horario [ponta, fora_ponta]} + comando via `ComandoDevice` existente. Painel fabricante é marca (fora).

## G-42 pecuária digital (48) — ⚠️

AgriWebb: reprodução, GMD, lotação, tarefas.

- `EventoReproducao` {femea FK, tipo [cobertura, IA, DG, parto], data, macho, resultado}
- GMD: cálculo sobre `Pesagem` + curva (só código+tela)
- `GiroPasto` {piquete FK, entrada/saida, descanso_dias, UA_ha}. Brinco/leitor é hardware (fora).

## G-43 cadeia custódia (50) — ⚠️ código

- `EloCadeia` {lote FK RastroItem, etapa, responsavel, data, hash_anterior+atual SHA-256 encadeado}. Blockchain permissionada é marca (fora); hash local cobre forense.
