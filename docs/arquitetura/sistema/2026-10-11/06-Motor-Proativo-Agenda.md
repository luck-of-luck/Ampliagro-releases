# Motor Proativo / Agenda Agrícola e Pecuária — Estado 2026-10-11

> Fontes: `app/ia/proativo.py`, `app/ia/proativo_tasks.py`, `app/ia/proativo_intents.py`, `PLANO-EXECUCAO.md` §2.7, `MERGED.md` §2.7, `11-integracao-tecnologias.md` §4.4

---

## 1. O que Existe (Motor Determinístico)

### `avaliar_usuario()` (`app/ia/proativo.py:580`)
- **Corre sem LLM, sem tokens, sem painel aberto**
- Governança de cada número justificada
- Regras determinísticas: clima, contas a pagar, desvio orçado, tarefas com prazo
- Deduplicação por fingerprint + teto diário/semanal
- Frota: `MAX_USUARIOS_POR_VARRAGURA`, `MAX_ALERTAS_FROTA_POR_VARRAGURA`
- Timeout por usuário: `TIMEOUT_POR_USUARIO_S` (orçamento de I/O externo)

### Intents Proativos (`app/ia/proativo_intents.py`)
| Intent | Descrição |
|--------|-----------|
| `avaliar_cenario` | Roda AGORA o que o motor faria; retorna quantos alertas saíram e quantos a governança suprimiu |
| `ligar_proatividade` | Liga/desliga motor de uma propriedade (default: DESLIGADO) |

---

## 2. Dois Agendadores — Perigo de Ambiguidade

| Agendador | Arquivo | Status |
|-----------|---------|--------|
| **Celery Beat** | `app/ia/proativo_tasks.py:274` | `BEAT_SCHEDULE` só arma se `AMPLIA_CELERY_BEAT=1` |
| **Windows Task Scheduler** | `tools/bat/setup_tarefa_proativa.bat` | Instalado, aponta para mesmas horas (7h12 e 17h12) |

**Perigo:** Armados os dois → varredura corre **duas vezes** → dedup segura alerta duplicado → **defeito PERIGOSO, não visível: parece funcionar**.

> `MERGED.md` §2.7: *"o custo aparece, e o custo é o que mais demora a notar numa fazenda"*

### Guarda Implementada
- `tests/test_agendador_unico.py` (3 testes) — falha **só em conflito real**
- `AMPLIA_CELERY_BEAT` documentado com aviso

---

## 3. Celery — Motor Instalado, Task Visível é Placeholder

| Pacote | Status |
|--------|--------|
| `celery`, `django-celery-beat`, `django-celery-results`, `redis`, `channels`, `channels-redis` | **Todos instalados** |
| `app/tasks.py` | **13 linhas**, `return True`, comentado *"Placeholder for actual report generation logic"* |

### Tecnologias Recomendadas (`11-integracao-tecnologias.md` §4.4)

| Lacuna | Ferramenta | Porque |
|--------|------------|--------|
| Saber o que corre | **Celery canvas** (`chain`, `group`, `chord`) | Dependências entre tarefas **visíveis no código**, não em `if`s |
| Visibilidade | **`django-celery-results`** (já instalado) | Resultados vão para BD. `Task.objects.filter(...)` responde *"esta task correu?"* |
| Varrer alertas | Manter `amplia.proativo.varrer`, **com revogação dentro** | Middleware não chega ao worker. Revogação tem de estar no corpo da task |

**Regra:** Não adoptar Taskiq / Dramatiq / Huey. Celery já instalado e integrado.

---

## 4. Agenda Agrícola e Pecuária

### Views Existentes

| View | Arquivo | Filtro |
|------|---------|--------|
| `agenda_agricola_view` | `app/views/campo.py:97` | `Safra.objects.filter(propriedade__user=request.user)` |
| `agenda_pecuaria_view` | `app/views/pecuaria.py:19` | `Animal.objects.filter(propriedade__user=request.user)` |
| `servidor_agenda_view` | `app/views/servidor.py:265` | `tarefas_da_propriedade(propriedade)` + filtro por `area_servidor` |
| `equipe_agenda_view` | `app/views/equipe.py:20` | `AtividadePlanejada` + `TarefaEstagio` |

### Modelos de Tarefas

| Modelo | App | Relacionamento |
|--------|-----|----------------|
| `AtividadePlanejada` | `app/models/safra.py:158` | `plano__safra__propriedade__user` |
| `TarefaEstagio` | `app/models/producao.py:100` | `estagio__registro__user` + `propriedade` denormalizado |

### Criação Automática de Tarefas
- `CultureBusinessEngine.create_tasks_from_template()` (`app/api/culture_config.py:620`)
- Templates em `cultures-config.json` → `task_templates` por estágio
- Associa `funcionario` por `cargo_alvo` na propriedade

---

## 3. Guardas de Regressão

| Teste | O que impede |
|-------|--------------|
| `tests/test_agendador_unico.py` | Celery Beat armado **e** tarefas do Windows instaladas |
| `tests/test_placeholder_zero.py` | Task que devolve `True` sem fazer nada |
| `app/tests_proativo.py` | `AgendadorUnicoTest` |

---

## 5. Checklist de Operação

- [ ] **Escolher UM agendador** (Celery Beat OU Windows Task, não ambos)
- [ ] Se Celery: `AMPLIA_CELERY_BEAT=1` + `celery -A config beat` rodando
- [ ] Se Windows: `tools/bat/setup_tarefa_proativa.bat` instalado, Celery desarmado
- [ ] `tests/test_agendador_unico.py` passa
- [ ] `grep ativo_servidor app/api/` → zero (revogação só no middleware + view)
- [ ] `tasks.py` implementado ou apagado (não placeholder)