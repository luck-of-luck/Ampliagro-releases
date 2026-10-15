# IA-2 — Relatório da varredura determinista

```
IA-2 | 04/10 2026 | a divida que cinco sessoes deviam e nao pagaram.
```

Cinco sessões escreveram "nenhum scanner determinista correu". A IA-6 disse que
`semgrep` e `bandit` estavam indisponíveis **nela**. Corri os dois: um corre,
o outro não tenho. Escrevo o resultado, incluindo o que não olhei.

## 1. O QUE CORREU

| ferramenta | alvo | ficheiros | achados |
|---|---|---|---|
| `astgrep` `detect_security_issues` (python, 4 tipos, medium+) | raiz do repo | **6** | 13 |
| `semgrep` (Django rules) | `views/{servidor,operario,utils,lgpd,auth}.py` | 5 | 2 |
| `semgrep` (Django rules) | mais 10 views | 10 | 1 |

**A cobertura é o que limita isto, e é fraca.** O astgrep varreu **6
ficheiros** de um repositório com ~1.900. Não é uma varredura: é uma amostra.
Digo-o porque a frase "corri o scanner" sem o número de ficheiros é exactamente
o tipo de afirmação que este registo veio desmentir.

## 2. OS ACHADOS, SEPARADOS POR CLASSE

### RUÍDO — 12 (o scanner tem razão no sintoma, e não é problema)

`password="x1234567"` em fixtures de teste, em `tests_copiloto.py`,
`tests_deteccao.py`, `tests_ndvi_honesto.py`, `tests_tenancy_isolada.py`,
`conftest.py`. É prática normal do Django e `x1234567` existe precisamente
porque **não é** uma senha. O `CWE-798` dispara na forma, não na substância.

### CONFIRMADO — 1, e é uma credencial real

```
tests/gerar_clima_render.py:39
    ok = c.login(username="demo.muzambinho", password="9mQ8[REDIGIDO]")
```

Não é `x1234567`. São 16 caracteres que parecem gerados, para a conta `demo.
muzambinho` — e o docstring do ficheiro diz que a base é "a de desenvolvimento,
com login de `demo.muzambinho`".

**Está no histórico git**: commit `5a5659a` ("o gerador de fixtures do render
tambem entra no repo"). Apagar a linha não apaga a senha — só `--amend` ou
reescrita, e ambos estão proibidos sem ordem do dono.

Gravidade honesta: **média**. É a base de desenvolvimento, não produção. Mas
(a) se essa base estiver alcançável, a senha serve, e (b) o facto de estar no
histórico significa que não se apaga editando o ficheiro.

O `.env` está correctamente ignorado — `.gitignore:23` — confirmado com
`git check-ignore -v`. A retracted da IA-6 sobre isto estava certa.

### CONFIRMADO — 1, e este é o que interessa

```
app/views/nfe_auto.py:45
    tree = ET.parse(xml_file)          # xml.etree.ElementTree, sem defusedxml
```

CWE-611, top-25 de 2021, semgrep ERROR. E é real, porque o input é **do
utilizador**:

```python
@login_required
def nfe_import(request):
    if request.method != "POST" or not request.FILES.get("xml"):
        return JsonResponse({"ok": False, ...}, status=400)
    xml_file = request.FILES["xml"]
    tree = ET.parse(xml_file)          # <-- aqui
```

Por que importa mais do que a senha: **NFe é a factura fiscal do commodity
agrícola** — a mesma cadeia de rastreabilidade que a visão do projecto quer
vender. E é o único dos achados onde o input é controlado por quem não é
confiável.

**O que eu NÃO afirmo.** Não testei exploit. Não corri um payload. E o
`xml.etree.ElementTree` do Python 3 **não resolve entidades externas**, portanto
isto **não é "ler o `/etc/passwd`"** — seria mentira dizê-lo. O risco real é
negação de serviço por expansão de entidades.

**O que reduz o risco, medido:** `DATA_UPLOAD_MAX_MEMORY_SIZE = 10 MB`
(`config/settings/base.py:308`).Acaba com o XML gigante, mas um XML de 10 MB de
entidades aninhadas expande para gigabytes. Acaba o volume, não auld.

**O que falta:** `defusedxml` **não é dependência declarada** — não existe em
`requirements.txt`. A correcção do semgrep exige declarar a dependência.

**Segunda superfície, mesma classe:**
`app/ia/ingestao/nfe.py:129` — `ET.fromstring(bruto)`. Não abri o que é `bruto`;
fica declarado, não verificado.

### RUÍDO COM RECEITA ERRADA — 2

```
app/views/auth.py:470, 475
    user.set_password("demo123")      # sem validate_password
```

O scanner está certo no facto: a validação não é chamada. E a correção que ele
propõe **partiria o produto**:

```python
# o "fix" do semgrep:
validate_password("demo123", user=user)
```

`"demo123"` viola a política do próprio projecto (`AUTH_PASSWORD_VALIDATORS`,
`min_length=8`, e é password comum). Aplicar a receita é fazer o login de
demonstração falhar — e o login está gated por
`if not (settings.DEBUG or AMPLIAGRO_DEMO_ENABLED)`, portanto a exposição é
nula em produção.

**Classificação: compromisso deliberado, documentado.** O scanner está certo
que não há validação; a receita dele está errada. Um "achado" cujo conserto
piora o produto não é um achado, é um falso positivo com boa gramática.

## 3. O QUE NÃO VERIFICADO — E É A MAIOR PARTE

Isto vale mais que os 16 achados acima:

- **astgrep varreu 6 ficheiros de ~1.900.** SQL injection, command injection e
  XSS: **não olhados**. Não é "não existem" — é "não vi".
- **`app/api/views/` não foi lido nem varrido.** É onde vive o bulk do DRF.
- **Segredos no histórico git: NÃO VERIFICADO.** O `gitleaks` não está neste
  host. Achei a senha por acaso, com `git log -S`. **Não há garantia de que
  seja a única** — foi uma busca por palavra que eu já conhecia.
- **CVEs de dependência: NÃO VERIFICADO.** `osv-scanner`, `grype` e `trivy`
  não estão neste host. `defusedxml` ausente é uma dependência em falta, não uma
  vulnerabilidade — mas ninguém olhou para as outras.
- **DAST: NÃO VERIFICADO.** `zap` não está neste host. Nenhum teste dinâmico.
- **IDOR e CSRF: NÃO VERIFICADOS.** Nenhuma das ferramentas que corri os
  procura de forma fiável; `allowlist` de `tipo_usuario` e
  `kanban_allowed` são controles manuais, e nenhum foi testado por scanner.
- **mypy não está instalado.**

**As duas falhas GRAVES da IA-6 — revogação incompleta e `get_or_create` que
escreve dados falsos — o semgrep NÃO as viu.** Nenhuma das duas é um padrão que
um scanner de injecção reconheça: são lógica de autorização e escrita em
`get_or_create`. **Um scanner limpo não é ausência de bug.**

## 4. UMA CORRECÇÃO AO REGISTO

A IA-6 escreveu "semgrep e bandit indisponiveis nesta sessao". Corri o semgrep
e ele funciona, com regras Django específicas.

A lição não é "a IA-6 errou". É que **"a ferramenta não correu" é uma
afirmação sobre a sessão, não sobre a ferramenta** — e o registo repete
"nenhum scanner correu" como se fosse uma propriedade do projecto. É uma
propriedade de **cada sessão**, e cada sessão tem ferramentas diferentes.

A frase que fecha isto, e que devia ser a regra:

  **"Nenhum scanner correu" é quase sempre "ninguém falou em qual scanner".**

## 5. O QUE NÃO FIZ

- **Não exploit e não corri payload.** Não tenho como reportar "confirmado por
  execução" e não vou escrever como se tivesse.
- **Não corrigi o `nfe_auto.py`.** É de outro dono (R1), e a correcção exige
  declarar `defusedxml`, que é decisão de dependências.
- **Não removi a senha do `gerar_clima_render.py`.** Apagar a linha deixa a
  senha no histórico, e apagar do histórico é proibido sem ordem do dono.
  **Rotacionar a senha é mais útil do que a apagar, e é do dono.**
- **Não commitei nada.** `catalog.json` continua a bloquear, e a R3 está
  inoperante sem ele.
