# Culture Config (cultures-config.json v2.0.0) — Estado 2026-10-11

> Fonte: `app/api/culture_config.py` (755 linhas), `app/static/data/cultures-config.json`

---

## 1. Estrutura do JSON

```json
{
  "version": "2.0.0",
  "groups": [
    {
      "name": "Grãos",
      "cultures": [
        {"name": "Soja", "slug": "soja", "planting_window_start": 9, "planting_window_end": 12, ...}
      ],
      "subgroups": [
        {
          "name": "Milho",
          "cultures": [
            {"name": "Milho 1ª Safra", "slug": "milho-1a-safra", ...}
          ]
        }
      ]
    }
  ]
}
```

**Estrutura real:** `groups[]` → cada grupo tem `cultures[]` e/ou `subgroups[]` → cada subgroup tem `cultures[]`.

**Bug V1:** Python lia `config.get("culturas", {})` → `{}` SEMPRE. JSON não tem chave `culturas` — tem `groups` + `subgroups`.

---

## 2. CultureBusinessEngine (`app/api/culture_config.py:436-755`)

### Singleton por Cultura
```python
class CultureBusinessEngine:
    def __init__(self, cultura_slug):
        self.cultura_slug = cultura_slug
        self.config = self._load_config()
        self.rules = self.config.get("business_rules", {})
        self.task_templates = self.config.get("task_templates", {})
        self.automations = self.config.get("automations", {})
```

### Métodos Principais

| Método | Descrição |
|--------|-----------|
| `get_culture_business_rules(cultura_slug)` | Retorna regras de negócio (dict) |
| `get_culture_metrics(cultura_slug)` | Retorna métricas alvo (dict) |
| `get_culture_fields(cultura_slug)` | Retorna campos de cadastro (dict) |
| `is_planting_season(cultura_slug, uf=None)` | **True/False/None** — janela de plantio |
| `get_planting_window(cultura_slug, uf=None)` | `(inicio, fim)` em mês (1-12) |
| `get_harvest_window(cultura_slug, uf=None)` | `(inicio, fim)` em mês |
| `evaluate_culture_alerts(cultura_slug, readings, uf=None)` | Lista de alertas baseada em thresholds |
| `get_tasks_for_stage(stage_name)` | Templates de tarefas para estágio |
| `create_tasks_from_template(registro, stage_name, user)` | Cria `TarefaEstagio` reais |
| `_run_automation(trigger, context, user)` | Executa automações configuradas |

### `is_planting_season()` — Regra Crítica
```python
def is_planting_season(self, uf=None):
    window = self.get_planting_window(uf)
    if not window: return None  # Sem regra = NÃO SABE
    hoje = date.today().month
    inicio, fim = window
    if inicio <= fim:
        return inicio <= hoje <= fim
    return hoje >= inicio or hoje <= fim  # janela cruza ano
```

**Regra:** Sem regra → `None` (não sabe). **NUNCA `True` por default.**
> Bug original: `self.rules == {}` → linha 412 dizia `"sem regra = sempre permitido"`.

---

## 3. Normalização de Slugs (`_preguicosos` / `cultura_slug`)

### Problema Medido
43/488 culturas (9%) não normalizáveis com `.replace()` antigo:
- `Algodão` (ã), `Cana-de-açúcar` (ç, ú), maiúsculas acentuadas

### Solução (`_preguicosos`)
```python
def _preguicosos(texto):
    texto = str(texto or "").lower().replace(" ", "-")
    for de, para in _ACENTOS.items():
        saida = saida.replace(de, para)
    return saida

_ACENTOS = {
    "á": "a", "à": "a", "â": "a", "ã": "a",
    "é": "e", "ê": "e",
    "í": "i",
    "ó": "o", "ô": "o", "õ": "o",
    "ú": "u",
    "ç": "c",
    "ñ": "n",
}
```

**Por que não `unicodedata.normalize`:** Decompõe `ç` em `c` + cedilha combinante → resultado não é o slug que o resto do sistema já usa.

**Duas funções normalizando o mesmo nome** (`cultura_slug` + `alert_engine.py`) → origem do defeito.

---

## 4. Índice de Culturas (`_indice_culturas`)

```python
def _indice_culturas() -> dict:
    """{django_nome: cultura} a partir de `groups`."""
    indice = cache.get(CACHE_KEY_INDICE)
    if indice is not None: return indice
    
    indice = {}
    for grupo in load_cultures_config().get("groups", []):
        for cultura in grupo.get("cultures", []) or []:
            _guarda(indice, cultura, grupo)
        for sub in grupo.get("subgroups", []) or []:
            for cultura in sub.get("cultures", []) or []:
                _guarda(indice, cultura, grupo)
    
    cache.set(CACHE_KEY_INDICE, indice, CACHE_TIMEOUT)
    return indice
```

**Cache separado do config:** Mesmo TTL (1h) mas invalidação diferente — muda quando arquivo muda, não quando `load_cultures_config` chamado.

---

## 5. Regras de Negócio (JSON)

### Estrutura `business_rules`
```json
{
  "business_rules": {
    "planting_window": {"start_month": 9, "end_month": 12, "uf_overrides": {"MT": [10, 1], "GO": [10, 1]}},
    "harvest_window": {"start_month": 2, "end_month": 5},
    "thresholds": {
      "soil_moisture_min": {"value": 30, "unit": "%", "alert": "Irrigar"},
      "temperature_max": {"value": 35, "unit": "°C", "alert": "Estresse térmico"}
    },
    "task_templates": {
      "preparo": [{"titulo": "Descompactação", "cargo_alvo": "TRATORISTA", "ordem": 1}],
      "plantio": [{"titulo": "Plantio direto", "cargo_alvo": "TRATORISTA", "ordem": 1}]
    },
    "automations": {
      "irrigation_alert": {"trigger": "soil_moisture_min", "action": "create_task", "params": {"titulo": "Irrigar talhão"}}
    }
  }
}
```

### Override por UF
```json
"uf_overrides": {
  "MT": {"planting_window_start": 10, "planting_window_end": 1},
  "GO": {"planting_window_start": 10, "planting_window_end": 1},
  "RS": {"planting_window_start": 10, "planting_window_end": 12}
}
```

---

## 6. Templates de Tarefas

```json
"task_templates": {
  "preparo": [
    {"titulo": "Descompactação", "cargo_alvo": "TRATORISTA", "ordem": 1, "setor": "MECANICA"},
    {"titulo": "Gradeamento", "cargo_alvo": "TRATORISTA", "ordem": 2}
  ],
  "plantio": [
    {"titulo": "Plantio direto", "cargo_alvo": "TRATORISTA", "ordem": 1}
  ]
}
```

**Criação automática:**
```python
def create_tasks_from_template(self, registro, stage_name, user=None):
    templates = self.get_tasks_for_stage(stage_name)
    for tpl in templates:
        funcionario = Funcionario.objects.filter(
            propriedade__user=registro.user, cargo=tpl.get("cargo_alvo"), ativo=True
        ).first() if tpl.get("cargo_alvo") and registro.user else None
        
        tarefa = TarefaEstagio.objects.create(
            estagio=estagio,
            descricao=tpl.get("descricao", tpl.get("titulo", "Tarefa")),
            funcionario=funcionario,
            cargo_alvo=tpl.get("cargo_alvo", ""),
            setor=tpl.get("setor", ""),
            concluida=False,
            ordem=tpl.get("ordem", 0),
        )
```

---

## 7. Automações

```json
"automations": {
  "irrigation_alert": {
    "trigger": "soil_moisture_min",
    "action": "create_task",
    "params": {"titulo": "Irrigar talhão", "cargo_alvo": "IRRIGADOR"}
  },
  "pest_alert": {
    "trigger": "pest_pressure_high",
    "action": "send_notification",
    "params": {"title": "Alerta praga", "message": "Pressão alta detectada"}
  }
}
```

### Execução (`_run_automation`)
```python
def _run_automation(self, trigger, context, user=None):
    for name, config in self.automations.items():
        if config.get("trigger") == trigger:
            condition = config.get("condition")
            if condition and not self._eval_condition(condition, context):
                continue
            action = config.get("action")
            params = config.get("params", {})
            self._execute_action(action, params, context, user)
```

### Actions Suportadas
| Action | Descrição |
|--------|-----------|
| `create_task` | Cria tarefas do template |
| `send_notification` | Push/email via `Notificacao` |
| `update_field` | Atualiza `RegistroProducao.fields_json` |
| `auto_advance_stage` | Avança estágio se condições atendidas |
| `webhook` | Placeholder para webhook externo |

---

## 8. Cache

| Cache Key | TTL | Conteúdo |
|-----------|-----|----------|
| `cultures_config_v2` | 1h | JSON completo |
| `cultures_indice_v1` | 1h | Índice `slug -> cultura` |

---

## 8. Guardas de Regressão

| Teste | O que impede |
|-------|--------------|
| `tests/test_regras_cultura_motor.py` | "Ou admite-se que não existe e tira-se a promessa do ecrã" |
| `tests/test_cultivar_g01.py` | Cultivar G01 |
| `tests/test_ensaio_cultivar_g03.py` | Ensaios cultivar G03 |
| `tests/test_lote_semente_g02.py` | Lote semente G02 |

---

## 9. Checklist de Operação

- [ ] `cultures-config.json` válido (version 2.0.0)
- [ ] Cache `cultures_config_v2` + `cultures_indice_v1` funcionando
- [ ] 15 culturas principais com `business_rules` + `task_templates`
- [ ] `is_planting_season()` retorna `None` (não `True`) sem regra
- [ ] Override por UF funcionando (MT, GO, RS, etc.)
- [ ] `_preguicosos` normaliza todas as 488 culturas
- [ ] Templates de tarefas criam `TarefaEstagio` com `cargo_alvo`/`setor`
- [ ] Automações disparam `create_task`/`send_notification`