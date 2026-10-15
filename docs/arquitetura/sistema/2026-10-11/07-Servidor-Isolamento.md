# Isolamento de Servidor (ServidorRevogadoMiddleware) — Estado 2026-10-11

> Fontes: `app/middleware.py:42-134`, `app/views/servidor.py`, `app/hierarquia.py`, `MERGED.md` §3.3, `PLANO-EXECUCAO.md` §2.8, `app/tests_servidor.py`

---

## 1. O Problema Original

**Medido:** 23 URLs / 20 endpoints devolviam HTTP 200 com dados da fazenda a servidores com `ativo_servidor=False` e sessão viva — incluindo escrita (`estoque`, `agenda`, `maquinarios`, `perfil`).

**Causa raiz:** `IsAuthenticated` prova que há **sessão**, não que a sessão ainda é válida. Cada view declara `permission_classes` explicitamente, sobrepondo qualquer default do DRF.

---

## 2. Solução: ServidorRevogadoMiddleware

### Posição no Stack (`config/settings/base.py:164`)
```python
# AuthenticationMiddleware (cria request.user)
# ↓
"app.bot.BotDeteccaoMiddleware",
# ↓
"allauth.account.middleware.AccountMiddleware",
# ↓
"app.middleware.ServidorRevogadoMiddleware",  # ANTES do TenantIsolation
# ↓
"app.middleware.TenantIsolationMiddleware",
```

**Por que middleware e não Permission Class?**
- `DEFAULT_PERMISSION_CLASSES` não chega: views declaram `permission_classes` explicitamente → sobrepõe default
- Para cobrir superfície toda com **uma** alteração, ponto tem de ser **antes do DRF**
- Middleware roda antes de todas as views

---

## 3. Lógica (`app/middleware.py:42-134`)

```python
PREFIXO = "/api/"

def __call__(self, request):
    if request.path.startswith(self.PREFIXO):
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            try:
                from app.services.revogacao import MENSAGEM, servidor_ativo
                if not servidor_ativo(user):
                    return self._recusar(request, MENSAGEM)  # 403
            except Exception as exc:
                # Fail-closed: se não consegue ler perfil → 403
                logger.error(...)
                return self._recusar(request, "Revogacao nao verificavel.", status=403)
    return self.get_response(request)
```

### `servidor_ativo(user)` (`app/services/revogacao.py`)
- Lê `user.perfil.ativo_servidor` (default=True)
- Trata `PerfilUsuario.DoesNotExist` → `False`
- **Fail-closed**: exceção ao ler → `False` (um guarda que assume "ativo" quando não sabe transforma revogação num acesso)

---

## 4. Escopo

| Caminho | Coberto? | Observação |
|---------|----------|------------|
| `/api/` | ✅ Sim | JSON 403 |
| 4 páginas HTML do servidor | ✅ Sim (próprio) | `app/views/servidor.py` lê flag e faz `logout` |
| `/admin/`, login, onboarding | ❌ Não | Não são `/api/` |

---

## 5. Revogação Dentro da View (Defence in Depth)

**Medido:** `grep ativo_servidor app/api/` → **zero**. A defesa do middleware não chega a Celery, management commands, nem views que não passam pelo middleware.

### Padrão nas Views (`app/api/views/faltantes.py:52-63`)
```python
def _exigir_ativo(self):
    from app.services.revogacao import exigir_servidor_ativo
    exigir_servidor_ativo(self.request.user)  # Levanta PermissionDenied
```

**Chamado em:** `get_queryset`, `perform_create`, `perform_update`, `perform_destroy`

---

## 6. Hierarquia / Permissões de Servidor

### `PerfilUsuario` campos relevantes
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `tipo_usuario` | `CharField` | `produtor`, `servidor`, `operario`, `mecanico`, `agronomo`, `administrativo` |
| `area_servidor` | `CharField` | `MECANICA`, `CAMPO`, `AGRONOMIA`, `PECUARIA`, `ESTOQUE`, `ADMIN`, `GERAL` |
| `propriedade_vinculada` | `ForeignKey` | Propriedade que o servidor acessa |
| `ativo_servidor` | `BooleanField` | Default=True; produtor desliga em `lgpd.py` |
| `funcionario` | `ForeignKey` | Link para `Funcionario` (opcional) |
| `permissoes` | `JSONField` | Config granular por página/ação |

### `propriedades_visiveis(user)` (`app/hierarquia.py`)
```python
def propriedades_visiveis(user):
    if user.perfil.tipo_usuario == "produtor":
        return Propriedade.objects.filter(user=user)
    elif user.perfil.tipo_usuario == "servidor":
        prop = user.perfil.propriedade_vinculada
        return Propriedade.objects.filter(pk=prop.pk) if prop else Propriedade.objects.none()
    # operario/mecanico/agronomo → via funcionario.propriedade
```

---

## 7. Guardas de Regressão

| Teste | O que impede |
|-------|--------------|
| `app/tests_servidor.py` (22 testes) | Servidor revogado não acessa `/api/`; revogação propaga a HTML |
| `app/tests_permissoes_servidor.py` (4 testes) | Permissões por área (MECANICA, CAMPO, etc.) |
| `tests/test_revocacao_servidor.py` | 23 URLs testadas; revogado = 403, ativo = 200 |
| `tests/test_superficie_servidor.py` | Superfície completa `/api/` coberta |

---

## 8. Checklist de Operação

- [ ] `ServidorRevogadoMiddleware` **antes** do `TenantIsolationMiddleware`
- [ ] `grep ativo_servidor app/api/views/` → views sensíveis chamam `_exigir_ativo()` ou `exigir_servidor_ativo()`
- [ ] Produtor desliga em `/lgpd/` → `perfil.ativo_servidor = False` → logout automático
- [ ] `tests/test_revocacao_servidor.py` passa
- [ ] `AMPLIA_CELERY_BEAT` documentado: revogação tem de estar **dentro da task** Celery