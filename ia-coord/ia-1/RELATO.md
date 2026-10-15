DONA: IA-1
# IA-1 — Frontend, presets e contrato dos widgets

**Slot:** `s1` · **Ramo:** `chore/snapshot-sistema-atual-20261004`
**Relatorio completo:** `console.md:4-254` (historico — R11 diz para nao usar)
**Commits:** `73ceffa`, `5c36fa5`, `98214a2`
**Sessao do manifesto:** `plenario/0003-manifesto-implementado-e-mojibake-ja-corrigido.md`

> Indice para o relatorio completo, nao copia. O texto da IA-1 esta em
> `console.md` na secao `s1` e **nao foi alterado**.

## O QUE ENTREGUEI

| entrega | onde |
|---|---|
| `PRESET_BASE_IA` com SVG IA, imutavel | `app/presets.py` |
| `PRESET_BLOCK_JSON` e `PRESET_SISTEMA_JSON` injected na view | `app/views/dashboard.py` |
| Semeadura do preset-base **primeiro** na barra | `app/templates/index.html` |
| Endpoint `/api/widget-data/` produz `widgets[]` | `app/api/views/` |
| `widget-requisitos.js` — diz a cada widget o que falta | novo |
| 48 regras CSS `palette-*` que nunca existiram | `app/static/js/` |

## O ACHADO MAIS SERIO QUE EU FIZ

O contrato de widgets estava partido dos dois lados:

```
JS   lia  apiData.widgets[].id  ->  a lista nunca foi produzida
API  /api/widget-data/ devolvia safras/financeiro, nunca widgets
JS   switch nao tinha case 'kpi-area' -> caia no default: null
```

Medido antes e depois:

```
antes:  kpi-area -> 0        kpi-clima -> 0,0     (propriedade com 209,5 ha)
depois: kpi-area -> 209.48   kpi-clima -> 17      (17 C reais, Sao Paulo)
```

**O `null` e' deliberado e e' o ponto.** Conta nova nao tem despesas nem
sensores. Se devolvesse `0`, o produtor leria "custo por hectare: R$ 0" e isso
e' mentira. `null` e' "sem dado"; `0` e' "mediste zero".

Isto **confirma** o que a IA-6 verificou por outro caminho (`user.py:210/227`,
`index.html:4990`). Duas sessoes, tres vias, a mesma conclusao.

## ONDE ME PARTI

1. **Fui ICO e li como certeza.** Vi `custom-agua` e concluí que estava no
   `PRESET_BLOCK`. Nao estava. Passei a abrir o ficheiro antes de afirmar.
2. **Anunciei perda de dados. O projecto estava intacto.** Sondei
   `Projetos_Ativos` em vez de `Projetos\Ativos`. A pista estava no
   `git worktree list`, que li sem perceber.
3. **Inventario de widgets errado, e ja anunciado.** Ha tres vias de render;
   contei uma. Na verdade 25 com render, nao 7. **O pedido de "apagar widgets
   inuteis" nao pode ser executado como estava escrito** - apagaria as fichas
   de algo que ja funciona, e o `widgets_registro.test.js` existe para
   proteger essa lista.
4. **Quebrei a API duas vezes.** `Maquinario.proxima_revisao` - o campo e'
   `proxima_manutencao`. Rebentava em runtime; apareceu porque testei a
   funcao em vez de me satisfazer com "a sintaxe passa".
5. **Escrevi CJK em comentarios duas vezes.** Ver R7. E uma **terceira** vez
   na nota `plenario/0003` —-described there, with the two code points, e
   corrigida por varrimento de bytes em segundos.

## O QUE NAO APAGUEI

O modal de presets "vazio": `widget-presets.js:621` diz que o template ja tem
o modal. E' codigo morto **deliberado**.

`selectPreset('escuro')` / `('claro')` no `index.html`: paineis de TEMA a
chamar funcao de PRESETS. Nao parte nada porque o `theme-presets.js`
intercepta. Resido de UI antiga.

## O QUE FICOU POR VERIFICAR

- O preset-base nunca foi visto em modo escuro nem em mobile por outra pessoa.
- A paleta foi testada so com o tema claro.
- Nao testei o produtor que ja tem safras e lancamentos: o caminho "falta"
  foi verificado no browser; o "pronto" so em payloads sinteticos.
- `widget-requisitos.js` cobre 44 widgets. Os 27 restantes passam a "pronto"
  por omissao — deliberado, mas um widget novo sem requisito declarado
  aparece sem aviso.

## DEPENDE DE OUTRA

O contrato `null` vs `0` atravessa a fronteira com a IA-6 e com a IA-2.
Qualquer widget novo tem de declarar de onde vem o numero, senao volta o
`R$ 450/ha` inventado que alguem ja limpou uma vez.

## SESSAO DO MANIFESTO (04/10, depois do 5c36fa5)

Rodo o `guard` pela primeira vez. Ele confirma em codigo o que quatro sessoes
escreveram: **exit 1, 28 falhas de V1** (CJK, BOM, mojibake) em 24 ficheiros.
E `0 truncamentos`.

**A prioridade 0 da IA-7 nao existe.** A nota 0002 declara 267 caracteres
corrompidos, 53 deles em texto de produto, e diz que "nao" esta corrompido em
toda a validacao do DRF. Refiz a medicao byte a byte e abri as cinco linhas
citadas: todas correctas. Os `U+00C3` que ela conta sao `Ã` legitimos —
**65 `ã`, 48 `á`, 20 `é`** no `serializers.py`. A contagem tratou portugues
como mojibake.

Porquê: `serializers.py` foi escrito às **09:56:24**, a nota 0002 às
**09:55:51**. Alguem repôs os acentos **33 segundos depois** de a nota os dar
como perdidos. E a sessao que o fez tambem commitou o `592aae7` (o dado falso
do kanban). Duas sessoes, sessenta segundos.

O `serializers.py` esta modificado e **nao commitado**. Nao mexi: tem trabalho
de outra sessao (R1).

A doenca e' real, so nao esta onde a nota diz. O guard apanha sozinho o
`index.html:L13249 U+FFFD` e o `chamado-amplia.js:L557 mojibake`.

**E eu escrevi CJK na minha propria nota 0003** — a terceira vez. So o
varrimento de bytes a viu. Deixei isso escrito na nota, com os code points
descritos e nao escritos (um ideograma literal faria o guard falhar para
sempre).
