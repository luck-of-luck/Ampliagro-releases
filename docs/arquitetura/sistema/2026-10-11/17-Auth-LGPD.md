# Autenticação, LGPD & Revogação — Estado 2026-10-11

> Fontes: `app/views/auth.py`, `app/views/lgpd.py`, `app/middleware.py`, `app/services/revogacao.py`, `app/hierarquia.py`

---

## 1. Autenticação & Onboarding

### `onboarding_save` (`app/api/views/user.py:496-595`)
Cria `Propriedade` + `PerfilUsuario` no primeiro acesso.

**Validações:**
| Campo | Regra |
|-------|-------|
| `nome_fazenda` | Obrigatório |
| `area` | > 0, ≤ 500.000 ha (teto sanidade) |
| `cpf_cnpj` | 11 dígitos (CPF) ou 14 (CNPJ) |
| `lat/lon` | -90≤lat≤90, -180≤lon≤180 |
| `geometria` | GeoJSON Polygon/MultiPolygon |

**Teto sanidade:** `AREA_MAX_HA = 500000` — maior fazenda do mundo (~0). Sem teto, desenho no zoom 4 dava 162M ha.

**Senha:** `password_validation.validate_password()` — executa `AUTH_PASSWORD_VALIDATORS` (config/settings/base.py). `create_user` NÃO executa validadores por default.

**Transação atômica:** `create_user` + `PerfilUsuario.get_or_create` + `login()` em `transaction.atomic()`. Se `login()` falha, usuário não fica órfão.

---

## 2. LGPD — Revogação de Servidor

### Fluxo
1. Produtor acessa `/lgpd/` → desativa `perfil.ativo_servidor = False`
2. Próximo acesso do servidor:
   - **Middleware** `ServidorRevogadoMiddleware` intercepta `/api/` → 403
   - **HTML views** (`servidor_dashboard_view`, `_perfil_e_propriedade`) fazem `logout()`

### `ServidorRevogadoMiddleware` (`app/middleware.py:42-134`)
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
            except Exception:
                # Fail-closed: não consegue ler perfil → 403
                logger.error(...)
                return self._recusar(request, "Revogacao nao verificavel.", status=403)
    return self.get_response(request)
```

**Posição no stack** (`config/settings/base.py:164`):
```
AuthenticationMiddleware
→ BotDeteccaoMiddleware
→ AccountMiddleware
→ ServidorRevogadoMiddleware      # ANTES do TenantIsolation
→ TenantIsolationMiddleware
```

**Por que middleware e não Permission Class?**
- `DEFAULT_PERMISSION_CLASSES` não chega: views declaram `permission_classes` explicitamente → sobrepõe default
- Para cobrir superfície toda com UMA alteração, ponto tem de ser **antes do DRF**

---

## 3. `servidor_ativo()` (`app/services/revogacao.py`)

```python
def servidor_ativo(user):
    try:
        perfil = user.perfil
    except PerfilUsuario.DoesNotExist:
        return False  # Sem perfil = não ativo
    return getattr(perfil, "ativo_servidor", True)
```

**Fail-closed:** Exceção ao ler → `False`. Um guarda que assume "ativo" quando não sabe transforma revogação num acesso.

**`ativo_servidor` default=True** — afeta só servidores (operários, agrônomos, mecânicos, administrativos não têm esse campo relevante).

---

## 4. Revogação Dentro da View (Defence in Depth)

**Medido:** `grep ativo_servidor app/api/` → **zero**. Middleware não chega a Celery, management commands.

### Padrão nas Views (`app/api/views/faltantes.py:52-63`)
```python
def _exigir_ativo(self):
    from app.services.revogacao import exigir_servidor_ativo
    exigir_servidor_ativo(self.request.user)  # Levanta PermissionDenied

def get_queryset(self):
    self._exigir_ativo()
    return Modelo.objects.filter(**{scope_lookup: self.request.user})

def perform_create(self, serializer):
    self._exigir_ativo()
    obj = serializer.save()
    if not Modelo.objects.filter(pk=obj.pk).filter(**{scope_lookup: self.request.user}).exists():
        obj.delete()
        raise PermissionDenied("Fora do escopo do seu usuário")
```

**Chamado em:** `get_queryset`, `perform_create`, `perform_update`, `perform_destroy`.

---

## 5. Hierarquia & Permissões (`app/hierarquia.py`)

### `propriedades_visiveis(user)`
```python
def propriedades_visiveis(user):
    if user.perfil.tipo_usuario == "produtor":
        return Propriedade.objects.filter(user=user)
    elif user.perfil.tipo_usuario == "servidor":
        prop = user.perfil.propriedade_vinculada
        return Propriedade.objects.filter(pk=prop.pk) if prop else Propriedade.objects.none()
    # operario/mecanico/agronomo → via funcionario.propriedade
```

### `pode_ver_financeiro(user)`
```python
def pode_ver_financeiro(user):
    if not user.is_authenticated: return False
    perfil = _perfil_ou_negado(user)
    if perfil is None: return False  # Dado sensível = default NÃO ver
    if perfil.tipo_usuario == "produtor": return True
    return bool(perfil.get_dashboard_config().get("pode_ver_financeiro", False))
```

### `propriedades_financeiras(user)`
Propriedades com financeiro visível: próprias, ou vinculada se permitido.

---

## 6. `PerfilUsuario` — Campos de Permissão

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `tipo_usuario` | CharField | `produtor`, `servidor`, `operario`, `mecanico`, `agronomo`, `administrativo` |
| `area_servidor` | CharField | `MECANICA`, `CAMPO`, `AGRONOMIA`, `PECUARIA`, `ESTOQUE`, `ADMIN`, `GERAL` |
| `propriedade_vinculada` | FK(Propriedade) | Para servidores |
| `funcionario` | FK(Funcionario) | Link opcional |
| `ativo_servidor` | BooleanField | Default True; produtor desliga em LGPD |
| `permissoes` | JSONField | Config granular por página/ação |

### `get_dashboard_config()` (servidores)
```python
{
    "titulo": "Mecânica",
    "icone": "bi-tools",
    "paginas": ["estoque_mecanico", "agenda_revisao", "lista_tarefas", "maquinario"],
    "pode_criar": True,
    "pode_editar": True,
    "pode_ver_financeiro": False
}
```

---

## 7. Signal: `garantir_perfil_usuario` (`app/signals.py:14-32`)

```python
@receiver(post_save, sender=User)
def garantir_perfil_usuario(sender, instance, created, **kwargs):
    if not created: return
    PerfilUsuario.objects.get_or_create(
        user=instance, defaults={"tipo_usuario": "produtor"}
    )
```

**Por que existe:** Contas criadas fora de `auth.py` (SSO Google/django-allauth, admin Django) ficavam **SEM perfil**. `app/hierarquia.py` tratava "sem perfil" como produtor de acesso total (`except: return True`). `get_or_create` mantém perfil já definido (ex.: servidor com área).

---

## 8. Checklist de Operação

- [ ] Produtor revoga servidor em `/lgpd/` → `ativo_servidor=False`
- [ ] `ServidorRevogadoMiddleware` bloqueia `/api/` com 403
- [ ] Views sensíveis chamam `_exigir_ativo()` ou `exigir_servidor_ativo()`
- [ ] `garantir_perfil_usuario` signal ativo (contas SSO/admin)
- [ ] `tipo_usuario` + `area_servidor` preenchidos para servidores
- [ ] `pode_ver_financeiro` respeitado em views financeiras
- [ ] `propriedades_visiveis` usado em todos os scopes