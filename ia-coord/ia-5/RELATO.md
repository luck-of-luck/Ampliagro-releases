DONA: IA-5
# IA-5 — Coordenador: medicao, git e corpus

**Slot:** `s5` · **Ramo:** `chore/snapshot-sistema-atual-20261004`
**Relatorio completo:** `console.md:620-828`
**Commits:** `a6b488f`, `854e3f7`, `d53c463` · **Fator:** construcao

## A RESPOSTA A PERGUNTA DO DONO

*"Porque e' que o Ampliagro bate de frente com os maiores do mundo...?"*

**Nao bate.** E a razao pela qual a pergunta parecia verdadeira e' que foi
CONSTRUIDA para parecer. A evidencia esta em `docs/super-estudo-globo-rural/`.
**Medido, nao opinado:**

| ficheiro | linhas | unicidade |
|---|---|---|
| `MANIFEST-REAL.json` | 9 | 100,0% |
| `SUPER-REVISAO-2400-CORRECOES.md` | 36 | 100,0% |
| `00-ARQUITETURA-TOP1.md` | 93 | 94,6% |
| `ANALISE-1001-2400-PROXIMO.md` | 25.203 | **12,0%** |
| `CONJUNTO` | 31.484 | 14,3% |

Isto corrige o enquadramento **a favor** do projecto: os documentos de analise
estao entre 88% e 100% unicos. O trabalho a serio existe.

## O FICHEIRO DE PADDING E' COMPROVADO QUE MENTE

1.400 capitulos, 1.400 URLs **distintas** — parece limpo. Mas sao
`episodio/2300, 2301, ... 3699`: sequenciais, sem uma unica lacuna.
Comprovado por **fetch**, com controlo positivo no mesmo host:

```
.../globo-rural/episodio/2300  -> 404
.../globo-rural/episodio/3699  -> 404
.../pecuaria/aves/noticia/2024/01/conheca-o-aviario-... -> 200, artigo
```

E' o caso mais perigoso: as URLs **parecem** reais, so que quem verifica cinco
passa. **So um fetch as separa.**

## O QUE E' REAL E DEFENSAVEL

O `fonte_dado: medido | declarado | sem_dado | suspect | simulado`. Ganha dos
gigantes **numa coisa so**: nunca mente sobre um numero.

E' uma **filosofia**, nao uma funcionalidade. So paga se alguem pagar por
proveniencia. E tem o paradoxo que o `ESTADO.md` §7 ja escreveu: **um painel
honesto comeca vazio, e e' isso que faz o produtor desistir.**

## ENTREGUE

| entrega | detalhe |
|---|---|
| `a6b488f` | 158 ficheiros versionados, todos os hooks verdes |
| `DatabaseCache` -> `LocMemCache` | 3 catracas morriam antes da asercao |
| 3x F841 | uma **era armadilha de perda de dados** |
| 6 erros mecanicos | um **fortalece** (B017 estreitado) |
| `854e3f7` | cabecalhos honestos, com a medicao |

### `vra.py:75` — CONFIRMADO PELA IA-6

`save_xml_file(prescricao)` **grava na BD**. Descartar o retorno e' seguro;
apagar a chamada para de gravar.

## O QUE EU QUEBREI

1. **CJK num ficheiro Python, duas vezes.** Nao me dei conta durante dois turnos.
2. **21.008 linhas em branco** — o `edit` reescreveu 2,1 MB. Texto intacto,
   medicao distorcida. Ver R6.
3. **Um BOM no commit `a6b488f`** (`Set-Content -Encoding UTF8`). No historico.
4. **Dois falsos positivos que declarei em vez de esconder** — um `ruff` que
   **nao correu** imprimiu "LIMPE". Ver R4 e R5.

## O QUE NAO APAGUEI

Os 273 MB (§3.2). `catalog.json`. Nao usei `--no-verify`. Nao regenei a
baseline (§3.1). **Decisao do dono.**

## O ACHADO QUE FICA

As 12 catracas estavam fora do git por centenas de commits. **A infra-estrutura
para travar isto ja existia** (`tests/estudo_volume.py`). O problema nunca foi
falta de mecanismo — foi que **commitar era perigoso**: os hooks reescrevem
~35 ficheiros e as duas sessoes dispararam o hook no mesmo minuto.
