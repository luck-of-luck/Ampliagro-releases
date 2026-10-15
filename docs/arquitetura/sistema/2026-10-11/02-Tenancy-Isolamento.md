# Tenancy / Isolamento Multi-Tenant — Estado 2026-10-11

> Fontes: `app/middleware.py` (TenantIsolationMiddleware), `docs/sistema/9.md` §5, `MERGED.md` §2.1, `PLANO-EXECUCAO.md` §2.4, `11-integracao-tecnologias.md` §4.2

---

## 1. Arquitetura Atual

### TenantIsolationMiddleware (app/middleware.py:137)
**Único caminho de verificação** — roda em **todo request HTTP** antes das views.

```python
TABELAS_VERIFICADAS = {
    "propriedade_id": ("Propriedade", "user"),
    "fazenda_id": ("Propriedade", "user"),
    "talhao_id": ("Talhao", "propriedade__user"),
    "device_id": ("Device", "propriedade__user"),
    "safra_id": ("Safra", "propriedade__user"),
    "conta_bancaria_id": ("ContaBancaria", "propriedade__user"),
    # + 30+ IDs adicionados 2026-10-11:
    "atividade_id", "tarefa_id", "plano_id", "preset_id",
    "maquinario_id", "insumo_id", "animal_id", "funcionario_id",
    "estoque_id", "lancamento_id", "aplicacao_id", "receituario_id",
    "piquete_id", "ordem_compra_id", "pesagem_id", "raca_id",
    "lote_aquatico_id", "despesca_id", "colmeia_id", "producao_apiario_id",
    "alerta_id", "regra_alerta_id", "centro_custo_id", "custo_producao_id",
    "lancamento_detalhado_id", "rastro_item_id", "rastreabilidade_safra_id",
    "experimento_id", "medicao_experimental_id", "prescricao_vra_id",
    "zarc_id", "cultura_id", "talhao_geometria_id"
}
```

### Fluxo
1. Lê IDs do `request.GET`, `request.POST` ou `request.corpo_json`
2. Para cada ID: `Model.objects.filter(id=valor).filter(**{caminho_dono: user})`
3. Se não existe → anula o ID (handler vê "sem dado")
4. Se existe mas não pertence ao user → **403** (`_Rejeitado`)
5. Se erro na verificação → **503** (fail-closed, não fail-open)

---

## 2. O que NÃO é coberto (limitações conhecidas)

| Caminho | Passa pelo middleware? | Risco |
|---------|------------------------|-------|
| HTTP / DRF | ✅ Sim | — |
| **Tarefa Celery** (`amplia.proativo.varrer`) | ❌ **Não** | Worker não passa por HTTP |
| **Management command** | ❌ **Não** | `manage.py` não tem request |
| **Nova middleware mal ordenada** (acima de `AuthenticationMiddleware`) | ❌ **Não** | `request.user` não existe |
| Canal WebSocket / consumer | Depende da ordem | — |

> **Verificado:** `grep ativo_servidor app/api/` → **zero**. A defesa de revogação só existe no middleware.

---

## 3. ServidorRevogadoMiddleware

- Roda **antes** do `TenantIsolationMiddleware` (`base.py:164`)
- Verifica `user.perfil.ativo_servidor` (default=True)
- **Fail-closed**: se não consegue ler perfil → **403** (não deixa passar)
- Diferente do TenantIsolation: exceção aqui = 403, não 503

---

## 4. Row Level Security (RLS) — PostgreSQL

**Medido:** Base é **SQLite** (`config/settings/base.py:173`). SQLite **não tem RLS**.

| Opção | Garantia | Custo | Status |
|-------|----------|-------|--------|
| A. Migrar para PostgreSQL + RLS | **Única que fecha fora de HTTP** | Alto (todas migrations) | Decisão de arquitetura |
| B. Chokepoint único no ORM | Fecha Celery/commands se tudo passar por ele | Médio | Convenção, não opção |
| C. `ativo_servidor` na view + middleware | Fecha HTTP+Celery que passam pela view | Baixo | **Implementado** (P1-6 do 9.md) |

**Leitura recomendada:** `11-integracao-tecnologias.md` §4.2

---

## 5. Guardas de regressão

| Teste | O que impede |
|-------|--------------|
| `tests/test_tenancy_isolamento.py` | Cross-tenant via `talhao_id`, `device_id`, `fazenda_id`, `propriedade_id` |
| `tests/test_tenancy_fail_closed.py` | `except Exception: pass` engolindo 403 |
| `tests/test_tenancy_da_503_real.py` | Erro de migração não vira 200 cross-tenant |
| `tests/test_tenancy_corpo_json.py` | JSON body contorna GET/POST |
| `tests/test_recusa_nao_reflete_html.py` | `_rejeitar` escapa HTML fora de `/api/` |

---

## 6. Padrão de uso nas views

```python
# ViewSet genérico (app/api/views/faltantes.py:43)
def make_scoped_viewset(model, scope_lookup, ...):
    def get_queryset(self):
        return model.objects.filter(**{scope_lookup: self.request.user})
    def perform_create(self, serializer):
        obj = serializer.save()
        if not model.objects.filter(pk=obj.pk).filter(**{scope_lookup: self.request.user}).exists():
            obj.delete()
            raise PermissionDenied("Fora do escopo")
```

**Regra:** Escopo por lookup reverso até `user`. Nunca `filter(id=...)` sem filtro de usuário.

---

## 7. Como testar isolamento

```bash
python -m pytest tests/test_tenancy_isolamento.py -v
python -m pytest tests/test_tenancy_fail_closed.py -v
python -m pytest tests/test_tenancy_da_503_real.py -v
python -m pytest tests/test_tenancy_corpo_json.py -v
```