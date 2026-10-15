# ANÁLISE PROFUNDA: Sistema Ampliagro vs Visão Documentada
> Data: 11/10/2026 | Baseado em VISAO.md + 20 docs criados + código verificado

---

## 📊 RESUMO EXECUTIVO

| Métrica | Visão | Realidade Medida | Gap |
|---------|-------|------------------|-----|
| **Proveniência (`fonte_dado`)** | 100% das escritas | **Não medido** — `operario.py:68-112` escreve sem declarar | 🔴 Crítico |
| **Primeiro minuto (produtor)** | Ver algo seu sem digitar | **Não chega ao ecrã** — painel vazio sem material de origem | 🔴 Crítico |
| **Scanner determinístico** | Obrigatório antes de qualquer fase | **Nenhum rodou** — `sast`, `semgrep`, `astgrep` nunca executaram | 🔴 Crítico |
| **Fase 0 (parar de mentir)** | Completa antes de qualquer função nova | **Incompleta** — 2 bugs graves abertos + escrita sem `fonte_dado` | 🔴 Crítico |
| **Fase 1 (primeiro minuto)** | ZARC semeada + import Excel + `declarado` visível | ZARC endpoint existe mas **não semeada**; import não existe | 🟡 Parcial |
| **Fase 2 (proveniência paga)** | GlobalG.A.P. + custo/ha com `fonte_dado` | Custo/ha existe mas **sem `fonte_dado` por linha** | 🟡 Parcial |
| **Fase 3 (máquina/IoT)** | Sensor real com `device_eui` + `fonte_dado: medido` | IoT provisionamento **não existe** (`mqtt_listener.py` apagado) | 🔴 Crítico |

---

## 🔴 GAPS CRÍTICOS (Fase 0 — Bloqueiam tudo)

### 1. **Escrita sem `fonte_dado`** — Viola princípio central
**Local:** `app/views/operario.py:68-112`
**Problema:** Renderiza página de produtor sem tarefas → cria 6 `TarefaEstagio` falsas + 1 `RegistroProducao` "Demo" no banco
**Efeito:** Viola `null` vs `0` (s1/s2), escreve mentira no disco
**Fix:** Remover criação automática; retornar `sem_dado` no painel

### 2. **Revogação não propaga** — Segurança
**Local:** `app/views/servidor.py:196,239,275`, `app/views/operario.py:21`
**Problema:** 4 de 5 rotas `/servidor/` não checam `ativo_servidor`
**Efeito:** Servidor desativado continua lendo maquinário, tarefas, alertas
**Fix:** Middleware `ServidorRevogadoMiddleware` existe mas views não chamam `_exigir_ativo()`

### 3. **Falha aberta em `operario.py:38-41`**
```python
except Exception: is_servidor = True  # Falha ABERTA = concede privilégio
```
**Fix:** `except Exception: is_servidor = False` + redireccionar

### 4. **Scanner NUNCA rodou** — Risco invisível
**Problema:** `sast`, `semgrep`, `astgrep` **nunca executaram** no projeto
**Riscos:** IDOR, CSRF, XSS, injecção SQL — **não olhados**
**Ação:** Rodar `sast scan_all` + `semgrep` + `astgrep` ANTES de qualquer fase

---

## 🟡 GAPS FASE 1 (Primeiro Minuto)

| Item Visão | Status Real | Gap |
|------------|-------------|-----|
| **1.1 ZARC semeada com fonte Embrapa** | Endpoint `/api/zarc/para_minha_regiao/` existe (`ESTADO.md` §8) mas **não semeada** — banco vazio | 🟡 Falta seed |
| **1.2 "O que posso plantar?"** | Endpoint existe (§8) mas **sem ZARC semeada** retorna vazio | 🟡 Depende 1.1 |
| **1.3 Import Excel/máquina/memória** | **Não existe** — painel vazio sem import | 🔴 Falta feature |
| **1.4 `declarado` visível no painel** | Modelo suporta (`fonte_dado: declarado`) mas **painel não mostra** | 🟡 Frontend |

---

## 🟡 GAPS FASE 2 (Proveniência Paga)

| Item Visão | Status Real | Gap |
|------------|-------------|-----|
| **2.1 GlobalG.A.P. com `fonte_dado`/campo** | Export LCDPR existe (6/9 registos) mas **sem `fonte_dado` por campo** no documento | 🟡 Parcial |
| **2.2 Custo/ha por talhão/safra com `fonte_dado`/linha** | `custo_talhao.py` calcula mas **sem `fonte_dado` por linha** | 🟡 Parcial |
| **2.3 Comprador pede rasto → sistema responde com `fonte_dado`** | Rastreabilidade existe (`rastreabilidade.py`) mas **sem `fonte_dado` por campo** na resposta | 🟡 Parcial |

---

## 🔴 GAPS FASE 3 (Máquina/IoT — Base para futuro)

| Item Visão | Status Real | Gap |
|------------|-------------|-----|
| **3.1 ZARC do próprio talhão** | Endpoint existe mas **ZARC não semeada** | 🔴 Bloqueado |
| **3.2 NDVI/Sentinel-2** | View existe (`agronomia.py`) mas **sem fonte nomeada/datada** | 🔴 Sem fonte |
| **3.3 IoT/LoRa/sensores** | **Provisionamento NÃO EXISTE** — `mqtt_listener.py` + `sync_inmet.py` **apagados** (`MERGED.md` §3.2) | 🔴 Crítico |
| **3.4 Integração máquina (CAN/ISOBUS)** | Depende 3.3 | 🔴 Bloqueado |

---

## 📋 PLANO DE AÇÃO PRIORIZADO

### SEMANA 1 — FASE 0 (Bloqueadores)
| Prioridade | Ação | Critério de Saída | Arquivo |
|------------|------|-------------------|---------|
| 1 | **Rodar scanners** `sast scan_all` + `semgrep` + `astgrep` | Resultados no `console.md` | — |
| 2 | **Corrigir `operario.py:68-112`** — parar de criar dados falsos | Teste: abre BD, conta antes/depois = 0 | `operario.py:68-112` |
| 3 | **Propagar revogação** — chamar `_exigir_ativo()` em 4 rotas `/servidor/` | `tests/test_servidor.py:286` itera todas rotas | `servidor.py` |
| 4 | **Falha fechada** `operario.py:38-41` → `is_servidor=False` | Exceção → `is_servidor=False` + redirect | `operario.py:38-41` |
| 5 | **Regra de escrita:** toda escrita declara `fonte_dado` | Sem `fonte_dado` → escrita rejeitada | Middleware/Serializer |

---

### SEMANA 2 — FASE 1 (Primeiro Minuto)

| Prioridade | Ação | Critério de Saída |
|------------|------|-------------------|
| 1 | **Seed ZARC** — semear tabela com dados Embrapa (município + janela) | `python tests/test_zarc_regiao.py` passa; teste varre JSON à procura de ISO date com ZARC vazia |
| 2 | **Import Excel/máquina/memória** — produtor com 5 safras chega a painel < 2 min | Produtor com 5 safras em papel → painel < 2 min sem digitar 40 campos |
| 3 | **`declarado` visível no painel** — frontend mostra `fonte_dado: declarado` | Produtor reconhece próprio número e vê marcado como declared |

---

### SEMANA 3 — FASE 2 (Proveniência Paga)

| Prioridade | Ação | Critério de Saída |
|------------|------|-------------------|
| 1 | **LCDPR 9/9 registos** + guarda `pode_exportar()` | 9/9 registos; `pode_exportar()` recusa se faltar CPF/0045 |
| 2 | **GlobalG.A.P. export** — `fonte_dado` + `fonte` por campo no PDF | Inspetor distingue medido/importado sem perguntar |
| 3 | **Custo/ha por talhão/safra** com `fonte_dado` por linha | `custo_ha` = `None` quando não há despesa (continua `None`) |
| 4 | **Comprador pede rasto** → API responde com `fonte_dado` por campo | API responde com `fonte_dado` por campo |

---

### SEMANA 4+ — FASE 3 (Máquina/IoT)

| Prioridade | Ação | Pré-condição |
|------------|------|--------------|
| 1 | **Restaurar IoT provisionamento** — `mqtt_listener.py` + `sync_inmet.py` | `git checkout HEAD -- app/iot/management/` |
| 2 | **Provisionamento device** — `amplia_provision_iot_endpoint` gera credencial + tópico MQTT | Broker no compose principal |
| 3 | **NDVI com fonte nomeada/datada** | Fonte nomeada + datada; nunca interpolação sem `fonte` |
| 4 | **IoT real** — `Device` + `TelemetryData` com `fonte_dado: medido` + `device_eui` | Sensor sem `device_eui` = número sem dono |

---

## 🎯 MÉTRICAS QUE MANDAM (Visão §6)

| Métrica | Hoje | Meta | Como Medir |
|---------|------|------|------------|
| **Primeiro minuto** | Não chega ao ecrã | < 60s ver algo seu | Tempo até produtor ver algo seu sem digitar |
| **Taxa `fonte_dado` nas escritas** | Não medido (~0%) | 100% | Query: escritas com `fonte_dado` / total escritas |

> **Tudo o resto — widgets, culturas, rotas, linhas de documentação — é métrica de vaidade.**

---

## 🚫 O QUE NÃO FAZER (Visão §5.2)

1. **Não gerar conteúdo para cumprir metas** — §0.3
2. **Não tocar `base.py` sem ler comentário** — `CACHES` é `DatabaseCache` (não `LocMemCache`)
3. **Não `git add -A`** — caminhos explícitos
4. **Não `edit` acima de ~50 KB** — reescreve ficheiro
4. **Não decidir §3.1 nem §3.2** — dono decide visão computacional/2GB RAM
5. **Não aceitar baseline de volume** (`tests/estudo_volume.py --aceitar`)

---

## 📋 CHECKLIST DE VERIFICAÇÃO SEMANAL

```
[ ] Scanners rodaram esta semana? (sast + semgrep + astgrep)
[ ] Escrita sem fonte_dado detectada? (query semanal)
[ ] Revogação propagou a todas rotas /servidor/?
[ ] ZARC semeada + teste test_zarc_regiao.py passa?
[ ] Import Excel funcional (< 2 min para 5 safras)?
[ ] declarado visível no painel do produtor?
[ ] LCDPR 9/9 + guarda pode_exportar()?
[ ] GlobalG.A.P. export com fonte_dado/campo?
[ ] Custo/ha com fonte_dado/linha?
[ ] IoT provisionamento restaurado + broker no compose?
[ ] NDVI com fonte nomeada/datada?
```

---

## 🎯 CONCLUSÃO

**O sistema tem arquitetura sólida (Django+DRF, tenancy, proveniência no modelo) mas:**

1. **Fase 0 incompleta** — 2 bugs graves + escrita sem `fonte_dado` + scanner nunca rodou
2. **Fase 1 vazia** — ZARC não semeada, import não existe, painel vazio
3. **Fase 2 parcial** — proveniência existe no modelo mas não no documento/export
4. **Fase 3 inexistente** — IoT provisionamento apagado, sensor sem `device_eui`

**Prioridade absoluta:** Completar Fase 0 (semana 1) antes de qualquer feature nova. A regra é clara: **"Sem `fonte_dado`, a escrita não entra."** Qualquer fase que escreva na BD passa a ter de declarar `fonte_dado` na mesma passagem.