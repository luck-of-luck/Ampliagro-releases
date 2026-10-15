# API Views — Estado 2026-10-11

> Fonte: `app/api/views/user.py`, `app/api/views/*.py`, `app/api/urls.py`

---

## 1. User Views (`app/api/views/user.py`)

### ViewSets

| ViewSet | Modelo | Scope Lookup |
|---------|--------|--------------|
| `PerfilUsuarioViewSet` | `PerfilUsuario` | `user=self.request.user` |
| `WidgetUsuarioViewSet` | `WidgetUsuario` | `user=self.request.user` |

---

## 2. Dashboard State (`app/api/views/user.py:70-117`)

### `GET /api/dashboard/state/`
Retorna estado completo do dashboard do usuário (layout, preset ativo, presets custom).

**Limpeza de presets fantasma** (`limpar_presets_bloqueados`):
- Remove presets que não existem mais no catálogo
- Loga removidos

### `POST /api/dashboard/state/`
Salva estado do dashboard com validação de `fonte_dado`.

**Validação de `presets_fonte_dado`:**
```python
FONTES = {"declarado", "sem_dado", "simulado", "suspect"}
# NÃO aceita "medido" — nada aqui mede, seria mentira
estado_final = {k: ("declarado" if v not in FONTES else v) for k, v in fde.items()}
```

**Regra:** Um preset montado pelo usuário é `declarado`. O vocabulário é o de `app/validators.py`: `medido | declarado | sem_dado | suspect | simulado`.

---

## 3. Perfil & Propriedade (`app/api/views/user.py:120-145`)

### `GET /api/perfil/`
```json
{
  "usuario": {"username", "email", "idioma", "tema"},
  "propriedade": {"nome", "area_total", "uf", "cidade", "bioma"}
}
```

---

## 4. Widget Data (`app/api/views/user.py:600+`)

### `GET /api/widget-data/?full=1`
Endpoint unificado: dados agregados para todos os widgets. Cache 30s por usuário.

**Retorna:**
```json
{
  "safras": [...],
  "financeiro": {...},
  "estoque": [...],
  "animais": [...],
  "maquinarios": [...],
  "talhoes": [...],
  "insumos": [...],
  "apiario": [...],
  "funcionarios": [...],
  "producao_animal": [...],
  "aplicacoes": [...]
}
```

**Cache key:** `widget_data:{user_id}:{1|0}`

---

## 5. Faltantes Views (`app/api/views/faltantes.py`)

**Padrão:** `make_scoped_viewset(model, scope_lookup, filters, search)`

Gera `ModelViewSet` com:
- `IsAuthenticated`
- `get_queryset` filtrado por `scope_lookup` (ex: `plano__safra__propriedade__user`)
- `perform_create` valida escopo pós-save (apaga + 403 se fugir)
- `_exigir_ativo()` — revogação dentro da view (defence in depth)

### ViewSets Gerados
| ViewSet | Modelo | Scope Lookup |
|---------|--------|--------------|
| `AtividadePlanejadaViewSet` | `AtividadePlanejada` | `plano__safra__propriedade__user` |
| `AnimalIndividualViewSet` | `AnimalIndividual` | `propriedade__user` |
| `EventoSanitarioViewSet` | `EventoSanitario` | `animal__propriedade__user` |
| `InventarioViewSet` | `Inventario` | `propriedade__user` |
| `OrdemCompraViewSet` | `OrdemCompra` | `propriedade__user` |
| `PiqueteViewSet` | `Piquete` | `propriedade__user` |
| `PlanoSafraViewSet` | `PlanoSafra` | `safra__propriedade__user` |
| ... | ... | ... |

---

## 6. Production Views (`app/api/views/production.py`)

### `TarefaEstagioViewSet` (`app/api/views/production.py:253-`)
**Scope complexo para servidores:**
```python
def get_queryset(self):
    user = self.request.user
    try:
        perfil = user.perfil
        if perfil.tipo_usuario != "produtor":
            prop = perfil.propriedade_vinculada
            if prop:
                return TarefaEstagio.objects.filter(
                    Q(propriedade=prop)
                    | Q(estagio__registro__user=prop.user)
                    | Q(funcionario__user=user)
                    | Q(cargo_alvo__iexact=perfil.area_servidor)
                ).distinct().select_related("estagio", "funcionario", "propriedade")
            return TarefaEstagio.objects.filter(funcionario__user=user).select_related(...)
    except Exception:
        logger.error(...)
        raise  # Fail-closed: não retorna queryset vazio
    return TarefaEstagio.objects.filter(estagio__registro__user=user).select_related(...)
```

### `mover` action (Kanban drag&drop)
```python
@action(detail=True, methods=["post"], url_path="mover")
def mover(self, request, pk=None):
    # POST {status: 'pendente'|'andamento'|'concluido'}
    # Servidor só move se for da sua fazenda/área
    # Fail-closed: exceção ao verificar permissão → 503
```

---

## 7. Amplia Palco Views (`app/api/views/amplia_palco.py`)

| View | Método | Descrição |
|------|--------|-----------|
| `palco_render` | POST | Valida widgets da IA, devolve mesa normalizada (não grava) |
| `palco_avaliar` | POST | Like/Dislike + consolidação assinatura (dataset ML) |
| `palco_clonar` | POST | "Salvar como meu Dashboard" → cria `PresetPalco` |
| `palco_chamado` | GET | Lê `ChamadoAmplia` do usuário com `fonte_dado` por bloco |
| `palco_info` | GET | Config pública + meus presets + zona de escrita |

---

## 8. Kanban Views (`app/api/views/kanban.py`)

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/api/agenda/` | GET | Funcionários + safras próximas |
| `/api/agenda/producao/` | GET | Safras |
| `/api/agenda/analises/` | GET | Talhões + laudos |

---

## 9. Culture Config Views (`app/api/culture_config.py`)

### `CultureBusinessEngine`
- Carrega `cultures-config.json` v2.0.0 (cache 1h)
- Índice `slug -> cultura` derivado de `groups` + `subgroups`
- **Bug fix V1:** JSON não tem chave `culturas` — tem `groups` + `subgroups`

### Normalização de slugs (`_preguicosos`)
```python
def _preguicosos(texto):  # cultura_slug
    texto.lower().replace(" ", "-")
    for de, para in _ACENTOS.items(): saida = saida.replace(de, para)
    # _ACENTOS cobre: á,à,â,ã, é,ê, í, ó,ô,õ, ú, ç, ñ
```

**Bug medido:** 43/488 culturas (9%) não normalizáveis com `.replace()` antigo.

---

## 10. Auth Views (`app/api/views/auth.py`)

### `onboarding_save` (`app/api/views/user.py:496-595`)
Cria `Propriedade` + `PerfilUsuario` no onboarding.
- Valida CPF/CNPJ, área, coordenadas
- Teto sanidade: `AREA_MAX_HA = 500000` (maior fazenda mundo)
- `PerfilUsuario.objects.get_or_create(user, defaults={"tipo_usuario": "produtor"})`

---

## 11. LGPD Views (`app/views/lgpd.py`)

### Revogação de Servidor
- Produtor desativa `perfil.ativo_servidor = False`
- Próximo login bloqueia + logout
- **Middleware** `ServidorRevogadoMiddleware` propaga a `/api/`

---

## 12. Roteamento de URLs (`app/api/urls.py`)

### Principais Rotas
| Prefixo | ViewSet | Basename |
|---------|---------|----------|
| `/api/culturas/` | `CulturaViewSet` | `cultura` |
| `/api/propriedades/` | `PropriedadeViewSet` | `propriedade` |
| `/api/talhoes/` | `TalhaoViewSet` | `talhao` |
| `/api/safras/` | `SafraViewSet` | `safra` |
| `/api/insumos/` | `InsumoViewSet` | `insumo` |
| `/api/atividades/` | `AtividadePlanejadaViewSet` | `atividade` |
| `/api/tarefas-estagio/` | `TarefaEstagioViewSet` | `tarefa-estagio` |
| `/api/lotes-aquaticos/` | `LoteAquaticoViewSet` | `lote-aquatico` |
| `/api/despescas/` | `DespescaViewSet` | `despesca` |
| `/api/maquinarios/` | `MaquinarioViewSet` | `maquinario` |
| `/api/lancamentos/` | `LancamentoFinanceiroViewSet` | `lancamento` |
| `/api/dashboard/state/` | `dashboard_state` | — |
| `/api/perfil/` | `perfil_data` | — |
| `/api/widget-data/` | `widget_data` | — |

---

## 13. Padrão de Segurança (Todas Views)

```python
# 1. Permission
permission_classes = [IsAuthenticated]

# 2. Revogação (defence in depth)
def _exigir_ativo(self):
    from app.services.revogacao import exigir_servidor_ativo
    exigir_servidor_ativo(self.request.user)

# 3. Scope por usuário
def get_queryset(self):
    return Modelo.objects.filter(**{scope_lookup: self.request.user})

# 4. Validação pós-save
def perform_create(self, serializer):
    obj = serializer.save()
    if not Modelo.objects.filter(pk=obj.pk).filter(**{scope_lookup: self.request.user}).exists():
        obj.delete()
        raise PermissionDenied("Fora do escopo do seu usuário")
```