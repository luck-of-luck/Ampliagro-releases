# IA — Plano de Expansão (resposta ao pedido de "1000 funcionalidades")

> 1000 intents copiadas = catálogo injogável, detecção degradada e manutenção impossível.
> Estratégia: **lotes curados de intents reais**, cada um com handler + testes + exemplos
> de detecção. Este arquivo registra o que já foi e o backlog priorizado.

## ✅ Lote 2 — 18 intents de leitura (entregue, 21 testes)
`app/ia/intents2.py` — só banco local (herméticas), escopo `propriedade__user`:

| Intent | Domínio |
|:---|:---|
| `listar_maquinas`, `revisao_maquinas` | maquinário |
| `listar_insumos`, `estoque_baixo` | insumos/estoque |
| `monitorar_pragas` | MIP |
| `calendario_sanitario` | sanidade animal |
| `producao_leite`, `piquetes`, `racao_estoque` | pecuária |
| `apiario_resumo` | apicultura |
| `contas_a_pagar`, `saldo_contas` | financeiro |
| `fretes_abertos` | logística |
| `ordens_compra` | compras |
| `analise_solo`, `ultimas_aplicacoes` | campo |
| `alertas_telemetria`, `listar_devices` | IoT |

## ✅ Lote 3 — 12 intents físico-financeiros (entregue 2026-09-21, 13 testes)
`app/ia/intents3.py` — cálculos puros + `app/services/` (sem HTTP), escopo usuário:

| Intent | Domínio | Handler |
|:---|:---|:---|
| `simular_hedge`, `recomendar_hedge` | hedge Chicago/soja | `hedge.py` `hedge_recomendado(80,85,1000,65)=162500` |
| `simular_ruminante`, `risco_acidose` | pecuária rumen | `ruminante.py` `ph_rumen(35,30)=6.0` ALTO/MÉDIO |
| `simular_avicultura`, `prever_lotes` | avicultura 42d | `avicultura.py` `lotes_por_ano 6.4` +R$150k |
| `lucro_tilapia_pele`, `tilapia_mormaco` | suíno/tilápia | `suino_tilapia.py` +566% R$800k vs R$120k |
| `rainforest_cafe`, `cafe_premium` | café especial | `cafe.py` 60vs30sc +100% |
| `mombak_restauracao`, `biomassa_eucalipto` | agrofloresta | `agrofloresta.py` +33% R$1bi |
| `solo_spd`, `agua_bme280` | solo/água | `solo_agua.py` SPD 7t +0.28%MO/ano 2%→3.4% |

Total: **55 intents** (25 + 18 + 12). Detecção automática via `exemplos`
(genérico ≥ 0.60, sem mudar JS). Cache TTL por intent em `sandbox.py`. `POST /api/simulacao/` `tipo` hedge/ruminante/avicultura + `POST /api/ia/executar` intents 3.

## 📋 Como adicionar o próximo lote (receita, 15 min/intent) — ATUALIZADO

## 📋 Como adicionar o próximo lote (receita, 15 min/intent)
1. Handler em `app/ia/intents2.py` (ou `intents3.py` + `INTENTS.update`): escopo por
   user, resposta ≤ 3 linhas, `dados` + `artefato`; leitura = hermética (sem HTTP).
2. Entrada em `INTENTS2` com `descricao` (INSTRUÇÃO IA), 4 `exemplos`, `flags` do
   domínio + handler.
3. TTL em `CACHE_TTL` (`sandbox.py`); flag nova em `validas` (`test_flags_conhecidas`).
4. Teste em `Lote2IntentsTest` (positivo + vazio quando fizer sentido).
5. Escrita nova? Só com `required_fields` + `requires_confirmation` (padrão `cadastrar_talhao`).

## 🗂️ Backlog priorizado — Reorganizado 22/09/2026
- **Lote 4 (escritas guiadas)**: cadastrar_maquina, registrar_aplicacao, registrar_pesagem,
  anotar_manejo, criar_ordem_compra — todas no padrão state-machine + confirmação.
- **Lote 5 (memória)**: resolução ordinal ("o segundo") sobre último artefato de lista;
  `IAContextoConversa` já existe como base.
- **Lote 6 (proativo)**: varredura diária (estoque baixo, revisões vencidas, doses a vencer)
  via `IAEvento` + painel; sem Celery no caminho da IA (síncrono).
- **Não fazer**: detectores por entidade duplicada, intents de delete via chat,
  qualquer coisa que exija LLM/RAG/audio (fora da arquitetura atual).
