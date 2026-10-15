# Mapa de Integração de Tecnologias — Estado 2026-10-11

> Fonte: `docs/sistema/11-integracao-tecnologias.md`, `config/settings/base.py`, `requirements*.txt`, `docker-compose*.yml`

---

## 1. Tabela de Estado de Verificação

| Etiqueta | Significado | Como pode ser usada |
|----------|-------------|---------------------|
| **M** | **MEDIDO** nesta sessão, com `ficheiro:linha` | Decisão |
| **V** | **VERIFICADO** hoje por fonte externa | Decisão, com data |
| **C** | **CONHECIMENTO** meu, não verificado nesta sessão | Hipótese |
| **N** | **NÃO VERIFICADO** | Não decidir |

---

## 2. Estado das Dependências Críticas

| O que a arquitetura precisa | Estado | Evidência |
|----------------------------|--------|-----------|
| `django-csp` — defesa principal contra XSS | **Instalada, NÃO declarada** | `csp` 4.0 na máquina; 0 hits em `requirements*.txt` |
| `paho-mqtt` — telemetria MQTT | **Ausente** | 0 hits em `requirements*.txt` |
| `psycopg` — isolamento forte (PostgreSQL + RLS) | **Ausente** | Base é SQLite (`base.py:173`) |
| `hypothesis` — prova do ficheiro LCDPR | **Ausente** | Validador RFB nunca rodou |
| `jsonschema` — fonte única proveniência | **Ausente** | Divergência 5 vs 6 estados |
| `cryptography` — telemetria cifrada | **Instalada, usada por outro caminho** | `Gateway.api_key` com Fernet + hash cego |

> **Padrão:** Dependências de **development/prova** não estão declaradas. O que corre em produção está instalado; o que **provaria** as afirmações, não está.

---

## 3. CSP / django-csp — Crítico

| Fato | Estado |
|-------|--------|
| Middleware no `MIDDLEWARE` | ✅ `base.py:120` |
| Pacote instalado | ✅ `csp` 4.0 |
| Em `requirements.txt` | ❌ 0 hits (163 linhas) |
| Em `requirements-mcp.txt` | ❌ 0 hits |
| Em `setup.py` | ❌ 0 hits |

**Consequência:** `pip install -r requirements.txt` + `manage.py runserver` em máquina limpa **não arranca** (`ImportError` no `MIDDLEWARE`).

**Correção de uma linha:**
```
django-csp>=4.0,<5.0
```

### Migração dos 560 Handlers Inline
| Etapa | Ferramenta | Ordem |
|-------|------------|-------|
| 1 | `django-csp` no `requirements.txt` | **Hoje** |
| 2 | `htmx` nos templates densos (`index.html`: 131 handlers) | Eliminação, não migração |
| 3 | `jscodeshift` (AST) no resto | `--dry-run` + revisão por template |
| 4 | `script-src 'nonce-...'` estrito | Remover `'unsafe-inline'` |

---

## 4. MQTT / Telemetria

| Item | Estado |
|-------|--------|
| `paho-mqtt` em `requirements*.txt` | ❌ Ausente |
| `mosquitto` / `1883` em `docker-compose.yml` | ❌ Zero |
| `docker-compose.telemetry.yml` | ✅ Tem broker (overlay opt-in) |
| `mqtt_listener.py` | ❌ **Apagado** (`D` no git status) |
| `mosquitto/` | Só `mosquitto.conf` |

**Escolha:** Mosquitto no compose principal + `paho-mqtt` + `depends_on: condition: service_healthy`. **Não EMQX** (operação desnecessária aos 500 utilizadores).

---

## 5. Tenancy / Row Level Security

**Medido:** Base é **SQLite** (`base.py:173`). SQLite **não tem RLS**.

| Opção | Garantia | Custo | Recomendação |
|-------|----------|-------|--------------|
| A. PostgreSQL + RLS | **Única que fecha fora de HTTP** | Alto (todas migrations) | Decisão de arquitetura com data |
| B. Chokepoint único no ORM | Fecha Celery/commands se tudo passar | Médio | Convenção, não opção |
| C. `ativo_servidor` na view + middleware | Fecha HTTP+Celery que passam pela view | Baixo | **Implementado agora** (P1-6) |

> **Enquanto for SQLite, "isolamento absoluto" fora de HTTP não tem como ser verdadeiro.**

---

## 6. LCDPR — Não Existe Biblioteca

| Projeto | Estado | Tem LCDPR? |
|---------|--------|------------|
| `sped-br/python-sped` | **ARQUIVADO** | ❌ |
| `PySPED` (PyPI v1.0.2) | LGPL-v2.1, "Production/Stable" | ❌ (só `nfe`, `nfse`, `cte`, `ecd`) |
| `spedpy` (v1.2.3) | MIT, fork | ❌ |

**Conclusão:** LCDPR escrito à mão **não é preguiça — é ausência de alternativa**.

### O que fazer
| Lacuna | Ferramenta | Estado |
|--------|------------|--------|
| Conformidade | **Validador oficial da Receita** | [N] Nunca executado |
| Deriva do leiaute | `jsonschema` + `lcdpr.schema.json` | `jsonschema` ausente |
| Regressão arredondamento | **`hypothesis`** (property-based testing) | Ausente |
| Um gerador só | **JÁ RESOLVIDO** (2026-10-04) | `lcdpr_export.py` delega em `_formatar_valor` |

---

## 7. NF-e / MDF-e — Biblioteca Existe

**Verificado (V):** **PyNFe** — LGPL-3.0, ativo, cobre **NF-e 4.00**, NFC-e, NFS-e, **MDF-e**, contingência, consulta status, protocolo, cancelamento, carta correção, manifestação destinatário.

**Custo real:** PyNFe fala **SOAP/XML** → exige **certificado digital ICP-Brasil** por produtor.
- `ICP_Brasil` = **0 ficheiros** no código
- **Não é bug — é o que torna offline necessário:** Ampliagro = **reconciliação** (lê nota), **não emissão**. Emissão = Aegro com certificado dele.

**Prioridade: BAIXA** (só depois do LCDPR).

---

## 8. Offline / Caderno — Dexie.js

| Opção | Quando |
|-------|--------|
| **`Dexie.js`** | **Escolha.** 30 KB, tipada, IndexedDB sem indexes documentados. Caderno = objetos simples com consultas por `[propriedade+tipo]` |
| `RxDB` | Quando precisar **replicação** embutida. Pesa mais. |
| `idb` | Lib mínima. Suficiente, mas reescrever índices à mão. |

**Blocker atual:** `test_sync_offline.py` falha por dump ausente. **Fixar o dump primeiro.**

---

## 9. Lint / Formatação — ESLint + Prettier + Plugin (brigam)

**Problema:** `eslint-config-prettier` existe **para desligar regras de formatação do ESLint** — mas `eslint-plugin-prettier` volta a ligá-las. `--max-warnings 0` falha em dívida pré-existente.

| Opção | Nota |
|-------|------|
| Manter as três | Funciona. Não mexer sem ganho. |
| **`Biome`** | **Rust, 10-100x mais rápido**, linter+formatter num binário, **suporta HTML**. Acelera migração dos 560 handlers. |
| `oxlint` | Rust, só linter. Corre em fase com ESLint. |

**Escolha: `Biome`**, se for mexer. **Condição:** só depois da CSP estrita (§3), porque o formatter mexe nos 560 handlers e a ordem importa.

---

## 10. Segredos / Chaves

| Onde | Falta | Ferramenta |
|------|-------|------------|
| `AMPLIAGRO_DATA_KEY` | **Não existe em produção** (`base.py`, `dev.py`, `prod.py` não têm) | `age` ou `SOPS`: chave encriptada em ficheiro versionado, valor em variável de ambiente |
| Segredos de deploy | Nenhuma revisão de "esta chave é de teste?" | `detect-secrets` / `gitleaks` em pre-commit |

**Precedente do projeto:** `base.py:184-187` tem `IA_LOCAL_KEY = env.str(...)` com comentário *"a chave só pode agir pelos user IDs listados aqui"*. **Padrão existe. Falta aplicar a `AMPLIAGRO_DATA_KEY`.**

---

## 11. Os 3 Itens da Primeira Semana (P0)

| # | Ação | Esforço | Referência |
|---|------|---------|------------|
| **P0-1** | `django-csp` no `requirements.txt` | **1 linha. Hoje.** | §3 |
| **P0-2** | `paho-mqtt` + Mosquitto no compose principal | **2 ficheiros** | §4 |
| **P0-3** | `hypothesis` + validador da RFB | **Único item que fecha pergunta com prova** | §6 |

---

## 12. O que NÃO Verifiquei (limitações honestas)

- ❌ Não executei o validador da Receita. Todo §6 é raciocínio sobre formato, **não** prova de aceitação.
- ❌ Não medi `psycopg` na base além da ausência. Opção A do §5 é plano, não estimativa.
- ❌ Não medi latência de `jscodeshift` nos 560 handlers.
- ❌ Não abri conta em nenhum sistema. Nenhum preço neste documento.
- ❌ Não medi taxa de classificação NCM.
- ❌ Não compilei/testei nenhuma recomendação. **Isto é um mapa, não um patch.**
- ❌ Não medi se CI está presently broken por causa do §2.1 (django-csp ausente).
- ⚠️ **Já medi errado uma vez** (chave Fernet em `test.py`). **Re-verificar antes de decidir.**