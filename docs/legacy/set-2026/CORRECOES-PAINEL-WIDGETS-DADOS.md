# Correções do painel — widgets e dados zerados

> **Data:** 2026-09-29 · **Âmbito:** dashboard (`app/templates/index.html`),
> registo de widgets (`app/static/js/tabs/dashboard-desktop.js`), payload do
> painel (`app/api/views/user.py`), cache (`app/cache_painel.py`).
>
> Este documento explica **o que estava quebrado, porquê doía, e o que mudou**.
> As decisões que ainda não foram tomadas estão listadas no fim, em
> [O que NÃO foi feito](#o-que-não-foi-feito).

---

## Resumo

Três defeitos independentes, todos com a mesma forma: **o sistema parecia
responder, e a resposta era falsa.**

| # | Sintoma que o produtor via | Causa real | Onde |
|---|---|---|---|
| 1 | Clica num widget, nada acontece | 22 widgets no catálogo sem ficha em `WIDGET_TYPES` → `addWidget` devolvia `'desconhecido'` | `dashboard-desktop.js` |
| 2 | Painel cheio de zeros com dados na base de dados | `null` do backend convertido em `0` no front-end; e o cache de 30 s nunca invalidado | `index.html`, `app/cache_painel.py` |
| 3 | `npm test` falhava sem correr um único teste | `include` do Vitest só aceitava `.tsx`; os testes são `.js` | `vitest.config.ts` |

Resultado: **801 testes Python + 17 testes JS a passar**, com 9 testes novos escritos para travar estas três regressões.

---

## 1. O clique que não acontecia

### O sintoma

O modal de "adicionar widget" mostrava 60 widgets. Clicar em 22 deles não
fazia absolutamente nada — aparecia um toast a dizer "Widget desconhecido" e o
widget nunca era colocado no painel.

### A causa

Existem **duas listas de widgets** em sítios diferentes:

- `WIDGET_CATALOG` — em `app/templates/index.html`, o que o modal **oferece**;
- `WIDGET_TYPES` — em `dashboard-desktop.js`, o que o sistema **sabe colocar**.

O `addWidget` faz:

```js
window.addWidget = function (widgetId, chartType) {
    var type = WIDGET_TYPES[widgetId];
    if (!type) return 'desconhecido';   // <-- aqui morriam os 22
```

As listas tinham crescido em ritmos diferentes. O catálogo ganhou widgets —
18 deles com renderizador próprio em `top-globais-widgets.js` e API
`/api/top-globais/<id>/` — e a ficha em `WIDGET_TYPES` não acompanhou.

**O conteúdo sempre existiu.** Faltava a ficha. Os 22 órfãos eram:

| Grupo | IDs |
|---|---|
| Ligados a `/api/top-globais/` (18) | `kpi-vra-ndvi`, `kpi-can-bus`, `kpi-guidance-ab`, `kpi-ai-cultura`, `kpi-chuva-1km`, `kpi-as-applied`, `kpi-praga-ai`, `kpi-rota-otimizada`, `kpi-weigh-scale`, `kpi-hedge-b3`, `kpi-benchmark-fbn`, `kpi-seguro-chuva`, `kpi-lcdpr-sped`, `kpi-carbono`, `kpi-voz`, `kpi-copilot-hedge` |
| Construídos por `getWidgetSpecificContent` (6) | `kpi-margem-bruta`, `kpi-melhor-cliente`, `kpi-novidades`, `kpi-pedidos`, `kpi-vendas-totais`, `table-vendas-regiao` |

### Havia um segundo defeito, logo a seguir

Mesmo que a guarda fosse removida, `generateWidgetContent` devolvia **string
vazia** para qualquer id sem ficha registada:

```js
if (!WIDGET_TYPES[id] && ...) {
    return '';      // contentor criado, sem nada dentro
}
```

O bloco aparecia na matriz como um **buraco**. Um widget que não mostra nada
é pior do que um widget que não aparece: o produtor vê um espaço reservado e
conclui que há um problema no ecrã dele.

### As correções

**a) As 22 fichas, registadas** (`dashboard-desktop.js`).

**b) Auto-registo no `addWidget`** — a correção da **causa**, não do sintoma:

```js
if (!type) {
    // procura o id em WIDGET_CATALOG e cria a ficha com o rótulo do catálogo
    type = { title: rotulo || widgetId, icon: ..., defaultSize: {w:6,h:6} };
    WIDGET_TYPES[widgetId] = type;
}
```

Um widget anunciado no catálogo passa a ser instalável mesmo que a ficha se
perca. Isto não é adivinhação: o utilizador escolheu explicitamente um widget
que o sistema lhe ofereceu. **O que não fazemos é inventar conteúdo** — só
garantimos que o contentor nasce, e o renderizador decide se mostra dados ou
escreve "sem dado".

**c) `generateWidgetContent` deixou de devolver string vazia** — passou a
mostrar "selecione os registros no painel de edição". Um rótulo é um estado
legível; um retângulo em branco não é.

### A regra que impede a recaída

`tests/unit/widgets_registro.test.js` falha se qualquer widget do catálogo
voltar a ficar sem ficha, sem `defaultSize`, ou se o `addWidget` perder o
auto-registo. Como as duas listas crescem em ficheiros diferentes, o teste é a
única coisa que fecha essa porta.

---

## 2. Os dados zerados

Este era o ponto central do pedido, e tinha **três causas independentes**. Uma
correcção não chega — foi preciso atacar as três.

### 2.1 O front-end deitava fora o contrato do backend

O `dashboard_data` (`app/api/views/user.py`) já tinha sido corrigido para não
inventar números: devolve `roi: null` quando não há despesa registada,
`custo_ha: null` quando a área não está medida, e expõe `area_medida` para
distinguir "não medido" de "zero".

O front-end recebia essa resposta e **transformava-a em zero**. `area_medida`
tinha **zero ocorrências** em `index.html` — o campo existia para esta pergunta
e nunca foi lido.

| Widget | Antes | O que afirmava | Agora |
|---|---|---|---|
| `kpi-custo` | `parseFloat(prop.area_total \|\| talhoes.area_total \|\| 1)` | R$ 15.000,00/ha numa fazenda que ninguém mediu | "sem dado" |
| `kpi-roi` | `if (roiVal == null) roiVal = 0;` | "+0,0%" — com o sinal `+`, lê-se como empate medido | "sem dado" |
| `kpi-manutencoes` | `num = ... : 0` e legenda `num === 0 ? 'OK'` | "OK" quando o que existe é "não há campo" | "sem dado" |
| `kpi-area` | `var areaVal = 0;` a subir só de fontes verdadeiras | "0,0 ha" para uma fazenda não medida | "sem dado" |

O `kpi-custo` é o caso mais grave, porque **reintroduziu em JavaScript o
defeito exacto que o backend já tinha removido**: o `|| 1` punha 1 hectare no
lugar de uma área desconhecida e dividia a despesa real por esse 1.

> **A regra:** se a fonte diz "não sei", o painel diz "sem dado".
> `0` é uma afirmação — "isto foi medido e deu zero". R$ 0,00/ha e
> R$ 12,00/ha são frases igualmente falsas para quem lê, e só uma delas parece
> um erro.

Foi introduzido `window.SEM_DADO` como marcador partilhado, para o estado
"sem dado" ser visualmente consistente entre widgets.

### 2.2 O cache de 30 segundos que ninguém apagava

`dashboard_data` guarda o payload agregado em `cache["dash:<user_id>"]` durante
30 segundos, para não refazer ~20 agregações a cada abertura.

**Essa chave nunca era apagada.** Um `grep -r "cache.delete"` no repositório
inteiro devolvia **zero ocorrências**. Não havia um único sinal a tocar naquilo.

A consequência é a que o produtor mais sente: lança uma despesa, guarda, volta
ao painel — e vê o número de antes. Se o payload ainda fosse o primeiro, vê
**zeros** com o dado já na base de dados. Até 30 segundos de uma mentira, num
ecrã que parece autoritativo.

O `LocMemCache` agrava: a janela vale **por processo**, logo "30 s" deixa de
ser um limite com mais do que um worker.

#### A correção

`app/cache_painel.py` — um único ponto de invalidação, ligado por sinais
`post_save`/`post_delete` aos 7 modelos que o painel lê (`Propriedade`,
`LancamentoFinanceiro`, `Safra`, `Talhao`, `Maquinario`, `Funcionario`, `Animal`).

**Porquê sinais e não `cache.delete()` em cada viewset?** Porque sete viewsets
escrevem estes dados. Se a invalidação mora em cada viewset, o próximo
viewset novo volta a esquecer-se dela e o bug regressa em silêncio. Um sinal
cobre toda a escrita — API, admin do Django, management commands, IA — sem
ninguém ter de se lembrar. É a diferença entre "isto foi corrigido" e "isto não
volta a partir de agora".

O sinal **não** apaga o cache de outro produtor: só o do dono do registo que
mudou. Um `cache.clear()` global resolveria o bug original — e trocaria-o por
um painel que pisca o do vizinho a cada importação. Está protegido por teste.

### 2.3 `{}` com HTTP 200 quando não há propriedade

`dashboard_data` respondia `{}` quando o utilizador não tinha propriedade. O
front-end não distingue "sem propriedade" de "todos os campos a null" — e cada
KPI caía no seu `|| 0`. Era esta a origem de um painel **inteiro** de zeros
para um produtor que ainda não tinha cadastrado a fazenda.

Agora responde `{"sem_propriedade": true}`: o front-end pode dizer
"cadastre a sua propriedade" em vez de mostrar zeros.

---

## 3. A suite de testes que não testava nada

Descoberto pelo caminho: `npm test` devolvia
`No test files found` e saía com código 1.

`vitest.config.ts` tinha `include: ['tests/unit/**/*.test.tsx']` e **não existe
um único ficheiro `.tsx` em `tests/unit`** — os testes são todos `.js`. A
configuração da build (`vite.config.ts`) tinha um bloco `test:` duplicado que
ainda por cima fazia o Vitest ignorar o `vitest.config.ts`.

Resultado: **a suite JavaScript do projeto não corria há já muito tempo, sem
qualquer sinal.** Passou a correr com `include: ['tests/unit/**/*.test.{js,ts,tsx}']`
e o bloco `test` removido de `vite.config.ts`.

Um include que não casa com nenhum ficheiro é um teste que não existe com a
forma de teste.

### Bug de testes descoberto pelo caminho

`tests/conftest.py` criava um `PerfilUsuario` com `create()`. Mas
`app/signals.py::garantir_perfil_usuario` **já o cria** no `post_save` de
`auth.User` — existe para apanhar utilizadores que nascem fora de
`app/views/auth.py` (SSO Google, admin do Django).

O `create` a seguir era um segundo perfil para o mesmo `user_id`:

```
IntegrityError: UNIQUE constraint failed: app_perfilusuario.user_id
```

**Doze testes nunca chegaram a correr.** Passaram a `get_or_create` /
`update_or_create`. O `user_servidor` precisou de `update_or_create` (e não
`get_or_create`) porque o perfil já existia com o default `produtor` — os
defaults nunca eram aplicados, e o "servidor" ficava de facto com um perfil de
produtor. Por isso `test_dashboard_config_mecanica` via `['tarefas','agenda']`
em vez da configuração de MECÂNICA.

**A correção foi no fixture, não no sinal.** O sinal está correcto e tem de
continuar a correr.

---

## Testes escritos

| Ficheiro | Testes | O que trava |
|---|---|---|
| `tests/unit/widgets_registro.test.js` | 10 | Catálogo sem ficha; ficha sem `defaultSize`; perda do auto-registo; `generateWidgetContent` a devolver `""`; KPIs a fabricar zero |
| `app/tests_cache_painel.py` | 7 | Escrita não reflectida no painel; invalidação a limpar o cache do vizinho; `{}` sem propriedade; divisão por área não medida |
| `tests/conftest.py` | (fixture) | `IntegrityError` de perfil duplicado que matava 12 testes |

### Como correr

```powershell
# Painel e widgets (rápido)
pytest app\tests_cache_painel.py --no-cov
npm test

# Tudo
$env:AMPLIAGRO_DATA_KEY="<chave Fernet>"; pytest tests app --no-cov
```

> **Nota de ambiente:** dois testes (`test_push_telemetry`,
> `test_lancamento_aceita_participante`) falham com
> `AMPLIAGRO_DATA_KEY não configurada` quando a variável não está definida.
> **É anterior a estas correcções** — confirmado por execução com as
> alterações em `stash`. Com a chave definida, a suite inteira passa.

---

## Como confirmar que está resolvido

1. Abrir o painel → "Adicionar widget" → escolher **VRA NDVI**, **CAN Bus**,
   **Hedge B3** ou **Produção Total (ton)**. Antes: toast de erro e nada
   acontecia. Agora: o widget entra na matriz, com conteúdo.
2. Sem cadastrar área na fazenda, olhar para **Custo/Ha** e **Área Total**.
   Antes: `R$ 0,00/ha` e `0,0 ha`. Agora: "sem dado".
3. Sem registar nenhuma despesa, olhar para **ROI Operacional**. Antes:
   `+0,0%`. Agora: "sem dado".
4. Lançar uma despesa e recarregar o painel **imediatamente**. Antes: o número
   antigo durante até 30 s. Agora: o número novo à primeira.
5. `npm test` — antes: `No test files found`, código de saída 1. Agora: 17 testes.

---

## O que NÃO foi feito

Decisões deixadas de fora, deliberadamente, com o motivo.

**Multi-propriedade.** `get_propriedade_optimizada()` (`app/hierarquia.py:333`)
devolve **uma** propriedade (`.first()`). Um produtor com duas fazendas vê só os
números de uma, sem aviso. É um bug real de correção, mas mudá-lo altera o que
todo o painel mostra e é uma decisão de produto (propriedade activa? somar
todas?), não um conserto. **Vale a pena ser decidido à parte.**

**`LocMemCache` partilhado.** A invalidação resolve a verdade do dado. O
`LocMemCache` continua a ser por processo, que num deploy multi-worker é uma
inconsistência real. A correcção é Redis/Memcached — decisão de
infraestrutura, fora do âmbito.

**Os restantes `|| 0` em `index.html`.** Existem cerca de 90 ocorrências no
ficheiro. Foram auditadas as que estão no caminho dos valores dos widgets (as
que estão na tabela da secção 2.1). As restantes não foram todas individualmente
avaliadas e podem ter o mesmo defeito.

**O bloco `audit_ia_erros_v2.md` e os outros `.md` na raiz** não foram
tocados — são documentos de auditoria anteriores, não documentação do produto.

---

## Ficheiros tocados

```
app/static/js/tabs/dashboard-desktop.js   +22 fichas de widget
app/templates/index.html                  auto-registo, generateWidgetContent,
                                         4 KPIs, window.SEM_DADO
app/cache_painel.py                       NOVO — invalidação por sinais
app/apps.py                               liga os sinais no ready()
app/api/views/user.py                     resposta sem_propriedade
tests/conftest.py                         get_or_create / update_or_create
vitest.config.ts                          include .js
vite.config.ts                            bloco test: removido
tests/unit/widgets_registro.test.js       NOVO — 10 testes
app/tests_cache_painel.py                 NOVO — 7 testes
```

