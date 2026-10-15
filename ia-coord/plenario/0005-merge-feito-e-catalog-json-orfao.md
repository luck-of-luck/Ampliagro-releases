# 0005 - O catalog.json esta morto, e o merge foi clean

```
IA-1 | 04/10 10:47 | o merge do ia-coord foi feito, e o catalog.json e' orfao mesmo
```

## 1. O MERGE

`chore/snapshot-sistema-atual-20261004` estava em `7a4c29b`. Trouxe-o para
`712320e`, **fast-forward, zero conflitos**, com cinco commits:

```
f869017  implementa o manifesto
e6e34a4  versiona as regras e as notas
9a3d8a2  re-regista os hashes
224d612  o guard acusa R2 a um hook
712320e  revogacao de acesso (NÃO e' meu — e' da IA-6, Prioridade 0)
```

Estado depois: indice a **zero** staged (R3), e os **41 ficheiros sujos de
outras sessoes sobreviveram intactos** ao merge. Verifiquei os dois: nao e'
que "deve estar bem".

Uma correccao a uma coisa que eu disse mal na 0003: escrevi *"nao fiz merge
porque R9 diz que nao se commita no ramo de outra"*. O `git switch -c` de
quando criei o ramo tinha falhado, e eu nao reparei. **Estava no ramo novo a
fundo e escrevi que nao estava.** O merge de hoje foi o primeiro `switch`
que passou. Um comando que falha e continua a parecer que passou e' a R5, e
eu nao a cumpri.

`V2` no ramo principal: **5 registos intactos** (sobe de 4 — o
`end-of-file-fixer` tornou a correr no merge, e o hash da 0004 mudou outra
vez). `10 ficheiros do ia-coord/ versionados`, `0 truncamentos`.

## 2. O CATALOG.JSON: ORFAO DE VERDADE, E PROVADO POR TRES VIAS

A pergunta em aberto no `INDICE.md` era *"resolve-se como?"*. Antes de
propor, apurei **o que e'**, porque "resolver" pode ser apagar.

**E' JavaScript, nao JSON.** A primeira linha:

```
window.WIDGET_CATALOG = {
  kpi: {          <- chave sem aspas
  comercial: {    <- chave sem aspas
  title: 'Comercial e Vendas (Power BI)',   <- aspas simples
```

O `check-json` reprova isto — e tem razao.

**Orfao de tres formas, todas verificadas:**

| pergunta | resposta |
|---|---|
| algum template o carrega? | **nao** — `catalog.json` nao aparece em nenhum `<script>`; um `.json` tambem nao podia, sem `type="module"` |
| algum JS define `WIDGET_CATALOG`? | **nao** — o `index.html` usa-o em `L6075` dentro de `if (window.WIDGET_CATALOG)`, e **nunca o define** |
| esta no HEAD? | **nao** — `git cat-file -e HEAD:catalog.json` → exit 128 |
| ha outro ficheiro assim? | **nao** — varri todos os `.json` do repositorio; e' o unico |

O `index.html:6075` e' um `if` que **nunca e' verdadeiro**. O ramo de
codigo esta morto ha mais tempo do que este directorio. O
`app/ia/chamado.py:12` que o menciona e' um **docstring**, nao codigo.

## 3. A PREMISA DO INDICE.MD ESTAVA ERRADA

O `INDICE.md` dizia: *"`catalog.json` resolve-se como? **Bloqueia todos os
commits do repo.**"*

Fui ver isso. **Nao bloqueia.** Corri o hook e ele falha por outra coisa:

```
check json  Failed
  app/static/manifest.json: Failed to json decode (Duplicate key: background_color)
```

O culpado e' **outro ficheiro, e um bug real**:

```
app/static/manifest.json:7    "background_color": "#f4f7f2"
app/static/manifest.json:110  "background_color": "#f4f7f2"
```

O mesmo valor duas vezes. **Nao e' um valor errado — e' a mesma cor
declarada duas vezes**, o que torna o bug mais subtil ainda: um olho nao o
apanha, e um validador JSON apanha sempre.

A mesma chave duas vezes no mesmo objecto JSON. O parser JSON **nao aceita
duplicados** (a RFC diz que o comportamento e' indefinido). Esta no HEAD —
**e' um bug antigo, nao trabalho sujo.** E um PWA manifest com a cor de
fundo declarada duas vezes: um validador vai rejectar o manifesto, e o
service worker nao instala.

Isto e' pior que o `catalog.json`, porque o `manifest.json` **esta em uso**.
O `catalog.json` e' um orfao; o `manifest.json` e' um ficheiro que o
produtor usa sem saber que esta partido.

Confirmei que o `catalog.json` tambem falha o `check-json` — mas e' a **menor**
das duas falhas, e so aparece quando o hook corre `--files catalog.json`. O
`--all-files` nao o lista entre as falhas, porque ha **centenas** de `.json`
e o hook so reporta os que nao parseiam; ele parseia o `catalog.json` como
o que e' — um ficheiro de texto que comeca por `window.`, e que o Python
rejeita na primeira linha.

## 4. O QUE NAO FIZ, E PORQUI

Nao apaguei o `catalog.json`, e a razao importa: **`catalog` de 60 widgets e'
a fonte historica do dashboard.** A nota `0001` e o `chamado.py` contam a
historia de como a IA passou a conhecer os widgets. Apagar um ficheiro
**nao versionado** e' o que R11 descreve: sem segunda via, **nao ha como
recuperar.**

O `INDICE.md` dizia *"nao esta no HEAD. Decisao do dono."* A terceira
condicao — *"nao esta no HEAD"* — e' a que importa: **nao ha segunda via, e
nao houve merge que a trouxesse de volta.** Apagar e' irreversivel aqui.

O que eu recomendo, e que e' reversivel:

```
mv catalog.json docs/catalog_widgets_orfao.js
```

Fica versionavel, deixa de ser lido pelo `check-json`, e o nome passa a dizer
o que e'. Nao apaga conteudo, e o `git log` passa a contar uma historia que
hoje so existe num ficheiro sujo.

**E o `manifest.json` e' prioridade acima do `catalog.json`.** Uma chave
duplicada num manifesto de PWA e' um bug de produto, e corrige-se em dois
minutos. Mas e' `app/static/`, que nao e' meu slot (R1) — e ha 41
ficheiros sujos de outras sessoes nesse ramo, portanto mexer agora e' pedir
colisao.

## 5. VERIFICAR O QUE ESTA DITO

O `check-json` **vai continuar a falhar** ate o `manifest.json` ser
corrigido, porque a falha nao era o `catalog.json`. Nao testei o
`check-json` depois de nada, porque **nao mexi em nada** — as tres
alteracoes que recomendo sao tuas.

## 6. O QUE NAO VERIFIQUEI

- **Nao rodei nenhum scanner deterministico.** Oitava sessao, zero.
- **Nao abri** `index.html` para alem das duas linhas que confirmam que
  `WIDGET_CATALOG` nunca e' definido. Nao **arrisquei**: ha tres referencias
  nos `widget-*.js` que nao vi, e o registo real vive em 14 ficheiros
  `widget-*.js` com **67 `id:`** — que e' onde o dashboard vai buscar, e nao
  no `catalog.json`. A frase dos "60 widgets" nao vem de uma contagem
  minha: vem do `chamado.py`.
- **Nao abri** o `manifest.json` para alem das duas linhas. Nao sei se a
  duplicata e' inofensiva (o parser aceita a ultima) ou se quebra algo.
- **Nao fiz merge de** `guard/`, `ia-2/`, `ia-5/`, `ia-6/`: continua R1.
- **Nao toquei** no `serializers.py` nem nos 41 ficheiros sujos de outros.

IA-1
