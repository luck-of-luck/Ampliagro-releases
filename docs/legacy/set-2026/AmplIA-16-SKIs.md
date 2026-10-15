# AmplIA — 16 SKIs no chat (TOP Globais clonados)

> **Status:** 16/16 widgets com `heatmap`/`chart`/`barra` direto na bolha do chat — `ff96e9c` — check 0 — 64 intents + 60 RegraAuto

| # | Widget ID | Trigger no chat | O que injeta no chat | Fonte |
|---|---|---|---|---|
| 1 | `kpi-vra-ndvi` | `VRA NDVI talhao 1` | `heatmap SVG 300×180` NDVI 0.71 + `VRA 180kg/ha` se <0.6 | `NDVIService` + `VRAISOXMLService` |
| 2 | `kpi-can-bus` | `CAN bus device 1` | `chart 6h RPM laranja + L/h verde` + `DTC P0420` badge | `top_globais.py` hash determinístico |
| 3 | `kpi-guidance-ab` | `guidance talhao 3` | `A-B 3` `Precisão 2.5cm — Auto-section ON` | `guidance_ab` |
| 4 | `kpi-ai-cultura` | `ai cultura -15 -47` | `soja 94% Sentinel-2 AI` | `ai_detecta_cultura` |
| 5 | `kpi-chuva-1km` | `chuva 1km` | `2.3mm 15min ⚠️` / `1h` | `chuva_1km` |
| 6 | `kpi-as-applied` | `as-applied gap` | `Gap 12.3%` barra `vermelho>10%` | `as_applied_gap` |
| 7 | `kpi-praga-ai` | `praga foto demo` | `ferrugem 94% Pulverizar` `vermelho/verde` | `praga_ai_foto` |
| 8 | `kpi-rota-otimizada` | `rota 70` | `142km em 5.6h — 70 colheitadeiras` barra teal | `rota_70` |
| 9 | `kpi-weigh-scale` | `weigh scale talhao 1` | `56.8 sc/ha NDVI 0.71 tempo real` | `weigh_scale` |
| 10 | `kpi-hedge-b3` | `hedge 65sc` | `Hedge B3 162500 R$ (1000 sc @ 85)` | `hedge_b3_real` |
| 11 | `kpi-benchmark-fbn` | `benchmark` | `Seu 52 vs média 50` barra `vermelho +4%` | `benchmark_fbn` |
| 12 | `kpi-seguro-chuva` | `seguro chuva` | `180mm 60d PAGA R$5000` (limite 200) | `seguro_chuva_param` |
| 13 | `kpi-lcdpr-sped` | `LCDPR` | `LCDPR_2025.txt ✓ SPED Auditável` | `lcdpr_sped` |
| 14 | `kpi-carbono` | `carbono 10000` | `125000 tCO2e 10000ha × 12.5 Mombak +33%` | `carbono_mombak` |
| 15 | `kpi-voz` | `voz` | `🎤 quanto choveu... TTS/STT pt-BR` | `voz_assistente` |
| 16 | `kpi-copilot-hedge` | `copilot hedge 65sc` | `Simulo hedge 65sc se Chicago -5%: 162500` | `copilot_hedge` |

**Como funciona:**
- `app/static/ia/skills/amplia-*.md` (3 SKIs) → `loadAmpliaSKI(t)` fetch sob demanda (`/static/ia/skills/`)
- `app/static/js/ia-local/ia-local.js` `renderAmpliaChartInChat(container, widgetId, params)` → `fetch('/api/top-globais/<id>/?'+params)` → injeta `heatmap`/`chart`/`barra` na `div` da mensagem do chat
- `app/services/top_globais.py` `WIDGET_HANDLERS` 16 determinísticos (hash, sem HTTP externo) + `app/api/views/top_globais.py` `GET /api/top-globais/<id>/`
- `app/api/views/agronomia.py` `ndvi_heatmap` SVG 300×180 para `kpi-vra-ndvi`

**Teste:** `AmplIA → "VRA NDVI talhao 1"` → heatmap no chat. `AmplIA → "benchmark"` → barra no chat.
