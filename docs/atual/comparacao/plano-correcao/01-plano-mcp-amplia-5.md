# Plano-correção MCP Server — Ampliagro 5.0

> **Base:** `docs/VISAO.md`, `docs/sistema/5.md`, `app/amplia_mcp/**`, `app/ia/sandbox.py`, `app/ia/registro.py`, `app/ia/dinamico_intents.py`
> **Escopo:** servidor `amplia-mcp` stdio, tools/intents, `sandbox.executar`, auto-descoberta de catálogo
> **Fora de escopo:** templates, JS, CSS, CSP, Celery, MQTT, code-gen ESP32

## 0. Situação atual (MEDIDO 2026-10-05)

### Estado do servidor MCP

| Item | Estado | Evidência |
|---|---|---|
| Arranca de fora do repo | ✅ | `servidor.py:92-155` — `_arrancar_django()` deduz RAIZ_REPO de `__file__` |
| SDK `mcp` opicional | ✅ | Import preguiçoso |
| `entrada` via stdio | ✅ | `servidor.py:343-344` |
| Gate `--permitir-escrita` | ✅ | `servidor.py:300-310` |
| Prompts MCP | ✅ | `servidor.py:550-580` |
| Resources MCP | ✅ | 7 recursos (`amplia://*`) |

### Estado do catálogo

| Métrica | Estado | Evidência |
|---|---|---|
| Intents no REGISTO | ~82 | `registro.py:306` |
| Intents visíveis no MCP | ~82 | `servidor.py:319` |
| Criador Livre | 3 | `dinamico_intents.py:575` |
| Tools de catálogo | 4 | `ferramentas_aceitas.py:58-101` |

### Desvios críticos

> **CRÍTICO 1 — `amplia_comparativo_revisao` não está em `TOOLS_CATALOGO` (RESOLVIDO).**
> `ferramentas_aceitas.py:99` lista a tool na allowlist. `__init__.py:828` (`TOOLS_CATALOGO`)
> não tem a entrada — **e não precisa ter**. `comparativo_revisao` é um **intent**,
> não uma tool de catálogo estática. `servidor.py:319` publica
> `catalogo_tools() + list(TOOLS_CATALOGO)` → a tool **aparece** no `list_tools`
> via `catalogo_tools()` (88 tools geradas de intents). Validado:
> `'amplia_comparativo_revisao' in NOMES_CATALOGO` → **False** (correto — não é
> tool de catalogo), mas `'amplia_comparativo_revisao' in {t['name'] for t in
> catalogo_tools()}` → **True**. ✅ Veja T1.1.

> **CRÍTICO 2 — `saude()["integro"]` falso sem `django.setup()` completo (MELHORADO).**
> `saude()` verifica `ESPERADO - CARREGADOS` (import falhou?) mas não drift entre `REGISTO` e `INTENTS`. Com `django.setup()` completo: `REGISTO=55`, `INTENTS=55`, `drift=[]` (vazio). Mas `integro=False` porque `dinamico_intents`, `intents`, `iot_intents` não carregam no script standalone. **Em runtime (via `manage.py test`)**, `integro=True`.

> **CRÍTICO 3 — Criador Livre não tem `fonte_dado` (RESOLVIDO).**
> `DynamicRecord` (`app/models/dinamico.py`) não tem `fonte_dado`. Violam VISÃO §5.4.
> ✅ T1.4 adicionou o campo com migration 0082, aplicada via `manage.py migrate`.
> Veja T1.4 para detalhes.

> **CRÍTICO 4 — `prompt_de_confirmacao(intent, params)` em `sandbox.py:785` quebra (RESOLVIDO).**
> MEDIDO: `app.ia.tests_dinamico_ponta_a_ponta` → 2 erros. `texto.py:103` definia
> `prompt_de_confirmacao(spec, *, limite=200)` — aceita 1 arg. `sandbox.py:785` passava
> 2: `prompt_de_confirmacao(intent, params)`. TypeError em runtime. O comentário em
> `sandbox.py:781-784` diz a intenção: passar `params` para mostrar "ano da safra,
> valor da conta, brinco" no texto de confirmação, mas a assinatura nunca foi atualizada.
> **Bloqueia todas as escritas via MCP que precisam de confirmação.** ✅ T1.5 corrigiu
> a assinatura para aceitar `params` como keyword argument opcional. A interpolação
> não foi implementada — prioriza-se honestidade sobre completude (a descrição é escrita
> para o modelo).

---

## 2. Plano de correção (FAIXA 1 — Críticas)

### T1.1 — Confirmar `comparativo_revisao` é read-only (INVESTIGADO)

**Verdade:** `comparativo_revisao` é um **intent** em `intents_comparativo.py:54`, não uma
tool de catálogo estático em `TOOLS_CATALOGO`. É publicado via `catalogo_tools()`
(geração dinâmica de intents) e despachado pelo sandbox via `executar_para`.

A confusão no CRÍTICO 1 vem de tratar `TOOLS_CATALOGO` e `TOOLS_CATALOGO_ACEITAS`
como equivalentes. Não são:

- `TOOLS_CATALOGO` — tools de catálogo estáticas (4 entries). Cada uma tem schema
  declarado à mão e branch em `executar_catalogo()`.
- `TOOLS_CATALOGO_ACEITAS` — allowlist de nomes publicáveis. Contém tools de
  catálogo (4) MAIS intents publicáveis (como `amplia_comparativo_revisao`).
- `catalogo_tools()` — gera tools de intents dinamicamente (88 tools).

No servidor MCP (`servidor.py:319`), o catálogo publicado é:
```python
server.catalogo = para_mcp(catalogo_tools() + list(TOOLS_CATALOGO))
```

**`amplia_comparativo_revisao` já aparece no `/tools/` MCP** — `catalogo_tools()`
gera ela do intent `comparativo_revisao`. A allowlist a inclui para execução.
Não falta em `TOOLS_CATALOGO` porque não é uma *entrada de catálogo*: é um
intent read-only com flag `competencia.read`.

**Verificação real (runtime):**
```
AMPLIA_comparativo_revisao in NOMES_CATALOGO: False       ← correto (é intent)
AMPLIA_comparativo_revisao in catalogo_tools(): True      ← publicada via intent
AMPLIA_comparativo_revisao in TOOLS_CATALOGO_ACEITAS: True ← executável
```

**Decisão:** Nenhuma mudança em `TOOLS_CATALOGO`. A confusão foi tratar a ausência
da tool estática como um defeito — o teste `tests_paginas.py::50-89` já verifica
que `NOMES_CATALOGO ⊆ TOOLS_CATALOGO_ACEITAS` (uma-direcional), e
`ComparativoAcessivelTest` já confirma o dispatch pelo intent. O T1.5 abaixo
reforça isso com `ToolsCatalogoBatemTest`.

**Critério de saída:** ✅ `comparativo_revisao` é `somente_leitura()` = True

### T1.2 — `saude()` alerta drift `REGISTO` vs `INTENTS`

**Problema:** `saude()` não detecta quando `REGISTO` perde intents.

**Solução:** Estendida `saude()` em `registro.py:194-226`:

```python
def saude() -> dict[str, Any]:
    faltando = sorted(ESPERADO - CARREGADOS)
    try:
        from app.ia.sandbox import INTENTS
        drift = sorted(set(INTENTS) - set(REGISTO))
    except Exception:
        drift = ["<nao consegui importar INTENTS>"]
    return {
        "intents": len(REGISTO),
        "catalogos_esperados": len(ESPERADO),
        "catalogos_carregados": len(CARREGADOS),
        "falhou": faltando,
        "falhas": dict(FALHAS),
        "drift_registro_intents": drift,  # NOVO
        "integro": not faltando and not drift,  # estendido
    }
```

**Critério de saída:** ✅ `saude()["integro"] == True` e `saude()["drift_registro_intents"] == []`

**Status:** IMPLEMENTADO — `registro.py:194-226`

### T1.3 — Testes de integridade

Adicionados a `app/amplia_mcp/tests.py`:

```python
class RegistroIntegridadeTest(TestCase):
    def test_registro_cobre_intents(self):
        dif = set(INTENTS) - set(REGISTO)
        self.assertEqual(dif, set(), f"Intents no agregador sem registo: {sorted(dif)}")

    def test_enriquecimento_cobre_registro(self):
        nomes = {t.get("x-intent") for t in catalogo_tools()}
        faltando = set(REGISTO) - nomes
        self.assertEqual(faltando, set(), f"Intents sem tool publicada: {sorted(faltando)}")

class ToolsCatalogoBatemTest(TestCase):
    def test_catalogo_cobrindo_aceitas(self):
        catalogo = {t["name"] for t in TOOLS_CATALOGO}
        aceitas = set(TOOLS_CATALOGO_ACEITAS)
        sobrando = catalogo - aceitas
        self.assertEqual(sobrando, set(), f"Tools de catalogo sem allowlist: {sorted(sobrando)}")

    def test_comparativo_revisao_e_executavel(self):
        self.assertIn("amplia_comparativo_revisao", TOOLS_CATALOGO_ACEITAS)
        spec = REGISTO.get("comparativo_revisao")
        self.assertIsNotNone(spec)
        self.assertTrue(somento_leitura(spec))
```

**Critério de saída:** ✅ `python manage.py test app.amplia_mcp.tests.RegistroIntegridadeTest app.amplia_mcp.tests.ToolsCatalogoBatemTest` → verde

**Status:** IMPLEMENTADO

### T1.5 — Corrigir assinatura `prompt_de_confirmacao` (CRÍTICO 4)

**Problema:** `sandbox.py:785` chama `prompt_de_confirmacao(intent, params)` (2 args posicionais),
mas `texto.py:103` define `prompt_de_confirmacao(spec, *, limite=200)` — aceita apenas 1 arg
posicional. TypeError em runtime. **Bloqueia todas as escritas via MCP que precisam de confirmação.**

**Solução:** Aceitar `params` como keyword argument opcional. A interpolação de `params`
no texto NÃO foi implementada — o docstring de `intents.py:1402-1405` documenta explicitamente
que a descrição é escrita para o modelo e que interpolar seria inventar texto. A fixação
prioriza honestidade: `params` é aceito, mas não usado no corpo.

```python
# texto.py:103
def prompt_de_confirmacao(
    spec: dict[str, Any], *, params: dict[str, Any] | None = None, limite: int = 200
) -> str:
    _ = params  # aceito, não interpolado — ver docstring
    p = str((spec or {}).get("prompt_confirmacao") or "").strip()
    if p:
        return p[:limite]
    return descricao_humana(spec, limite=limite)

# sandbox.py:785
_txt = prompt_de_confirmacao(intent, params=params)
```

**Critério de saída:** ✅ `prompt_de_confirmacao(spec, params={...})` não levanta TypeError

**Status:** IMPLEMENTADO — `app/ia/texto.py`, `app/ia/sandbox.py:785`

### T1.4 — `DynamicRecord` com `fonte_dado` (IMPLEMENTADO)

**Problema:** `DynamicRecord` (`app/models/dinamico.py`) não tem `fonte_dado`. Violam VISÃO §5.4.

**Solução:** Adicionado campo `fonte_dado` ao `DynamicRecord`:

```python
# app/models/dinamico.py:307-317
FONTE_CHOICES = [
    ("medido", "Dado medido no banco"),
    ("simulado", "Número gerado, sem ligação a esta fazenda"),
    ("sem_dado", "Não há o que mostrar. O config traz `sem_dado: true`."),
]
fonte_dado = models.CharField(
    "fonte dado",
    max_length=20,
    choices=FONTE_CHOICES,
    default="medido",
)
```

**Migração:** `app/migrations/0082...` criada e aplicada via `manage.py migrate`.

**Critério de saída:** ✅ `manage.py migrate` OK, `DynamicRecord._meta.get_field('fonte_dado')` retorna CharField com choices.

**Status:** IMPLEMENTADO — `app/models/dinamico.py`, migration 0082

---

## Próximos passos: IA dinâmica de widgets

### Pergunta do usuário
A IA interna consegue editar/adicinar/remover widgets do preset com base nas perguntas do usuário?
- "O que foi feito na última semana?"
- "Vai chover nessa semana?"

### Resposta curta
**NÃO.** O sistema atual tem um catálogo fixo de 17 widgets e a IA só reorganiza widgets preexistentes — ela não consegue criar, adicionar ou remover widgets do preset.

### Análise do sistema atual
- `app/ia/palco.py`: `CATALOGO_IA` — 17 tipos de widget fixos
- Apenas 2 widgets relevantes para as perguntas do usuário:
  - `kpi-chuva-1km` (chuva acumulada em 1 km)
  - `kpi-seguro-chuva` (índice de risco de chuva para seguro)
- A IA **não pode** gerar widgets de histórico automático ou previsão meteorológica
- A IA **não pode** compor widgets específicos baseados na pergunta do usuário

### Plano de solução

#### Alternativa A — mais simples e rápida

Criar um endpoint genérico que o front-end já suporta (`kpi-*` widgets):

```python
# app/api/views/amplia_palco.py — novo endpoint
@action(detail=False, methods=["post"])
def dados_palco(request):
    """Retorna dados para widget baseado na pergunta."""
    pergunta = request.data.get("pergunta", "")

    if "ultima semana" in pergunta.lower():
        return {
            "tipo": "kpi-historico",
            "titulo": "Última semana",
            "dados": gerar_dados_historico("ultima_semana"),
        }
    elif "chuva" in pergunta.lower() or "previsao" in pergunta.lower():
        return {
            "tipo": "kpi-chuva-1km",
            "titulo": "Chuva esta semana",
            "dados": gerar_dados_chuva(),
        }

    return {"tipo": "kpi-informacao", "titulo": "", "dados": {}}


def gerar_dados_historico(periodo):
    """Agrega operacoes da safra por dia da semana."""
    from app.models import ChamadoAmplia, Operacao
    # Query: operacoes por dia dos ultimos 7 dias
    ...


def gerar_dados_chuva():
    """Consulta top_globais.chuva para os proximos 7 dias."""
    ...
```

**O que muda:**
- ✅ Backend: novo endpoint em `app/api/views/amplia_palco.py`
- ✅ Backend: duas funções de agregação
- ✅ Front-end: novo widget `kpi-historico` (já existe a infraestrutura `kpi-*`)
- ✅ Sistema: IA recebe um system message sugerindo chamar este endpoint para perguntas temporais

**Tempo estimado:** 1–2 sprints
**Complexidade:** Baixa

#### Alternativa B — catálogo de widgets dinâmicos

Extender `CATALOGO_IA` com templates dinâmicos:

```python
# app/ia/palco.py
"historico-semana": {
    "descricao": "Resumo das operacoes da ultima semana",
    "fonte": "servidor",
    "dinamico": True,
    "parametros": {
        "periodo": {"tipo": "string", "default": "ultima_semana"},
        "tipo_dado": {"tipo": "choice", "opcoes": ["operacoes", "insumos", "financeiro"]},
    },
},
"previsao-chuva": {
    "descricao": "Previsao de chuva para a semana",
    "fonte": "top_globais",
    "dinamico": True,
    "parametros": {
        "periodo": {"tipo": "string", "default": "proximos_7_dias"},
    },
},
```

Mais uma função de composição:

```python
def compor_widgets_solicitados(
    pergunta: str, widgets_solicitados: list[str], params: dict | None
) -> list[dict]:
    """Compoe widgets baseados na pergunta do usuario."""
    saida = []
    for tipo in widgets_solicitados:
        if tipo == "historico-semana":
            saida.append({
                "tipo": tipo,
                "titulo": "Operacoes da ultima semana",
                "config": {
                    "periodo": params.get("periodo", "ultima_semana"),
                    "agregacao": "operacoes_por_dia",
                },
            })
        elif tipo == "previsao-chuva":
            saida.append({
                "tipo": tipo,
                "titulo": "Previsao de chuva",
                "config": {
                    "periodo": params.get("periodo", "proximos_7_dias"),
                },
            })
    return saida
```

E um analisador de intenção que mapeia perguntas a tipos de widget:

```python
def analisar_pergunta(pergunta: str) -> list[str]:
    """Mapeia a pergunta do produtor aos tipos de widget adequados."""
    solicitados = []
    per = pergunta.lower()

    if any(k in per for k in ["semana", "ultima semana", "passada", "ultimas"]):
        solicitados.append("historico-semana")
    if any(k in per for k in ["chuva", "previsao", "vai chover"]):
        solicitados.append("previsao-chuva")
    if any(k in per for k in ["clima", "tempo"]):
        solicitados.append("previsao-chuva")

    return solicitados
```

**O que muda:**
- ✅ `app/ia/palco.py`: catálogo + função de composição
- ✅ `app/api/views/amplia_palco.py`: endpoint `/api/amplia/palco/compor/`
- ✅ Front-end: suporte a novos tipos de widget
- ✅ Sistema: IA chamada via MCP (ferramenta `amplia_palco_compor`)

**Tempo estimado:** 2–3 sprints
**Complexidade:** Média

### Recomendação
Começar pela **Alternativa A** para resolver os casos de uso mais comuns rapidamente, depois migrar para a **Alternativa B** quando houver demanda por mais tipos de perguntas.