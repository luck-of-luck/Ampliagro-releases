# 0002 - IA-7 occupied s7, and there is 267 characters of corrupted encoding

```
IA-7 | 04/10 09:40 | s7 esta OCUPADO por mim, e ha 267 caracteres corrompidos que o PROMPT-IA.md nao menciona
```

## 1. `s7` ESTA OCUPADO. O `docs/PROMPT-IA.md` DIZ QUE ESTA LIVRE.

`PROMPT-IA.md` L59 diz `s7   LIVRE`. Fui eu que occupei, a 04/10 08:46, e a
minha conta esta no `console.md` a partir da linha 2385 (marcador `s7`, titulo
`# S7`).

**Se uma IA nova ler o prompt e ocupar o s7, repete-se a colisao que matou o
s3, o s4 e o s7-s11.** Nao escrevi no prompt para corrigir a linha: o prompt e'
de quem o fez (Space Bunny, Coordenador), e R1 diz um dono por ficheiro. Fica
o aviso, e a correccao da linha e' de quem o fez.

Slot ocupados agora: `s1 s2 s5 s6 s7`.

## 2. 267 CARACTERES CORROMPIDOS, E NAO E' O CJK DE COMENTARIOS

O registo inteiro documenta uma so doenca de codificacao: ideogramas CJK em
comentarios, apanhados por varrimento de bytes. **Essa nao e' a doenca grande.**

Esta e' **UTF-8 lido com o charset errado** (duplo encoding), e esta no produto,
em texto que o produtor le:

```
ficheiros afectados: 8
ocorrencias totais : 267
```

| ficheiro | ocorrencias |
|---|---|
| `app/api/serializers.py` | **184** |
| `docs/dashboard-reload-graph.md` | 47 |
| `scripts/amplia_mcp_sonda.py` | 16 |
| `app/static/css/theme.css` | 12 |
| `scripts/_fix_all.py` | 1 |
| `docs/SUPER-CORRECAO-AGENTE-LOCAL.md` | 1 |
| `app/static/js/ia-local/chamado-amplia.js` | 1 |

**53 destas ocorrencias sao TEXTO DE PRODUTO.** `serializers.py` tem 201
caracteres `U+00C3` e e' a camada de validacao do DRF. O produtor le:

```python
"Esta propriedade não pertence ao seu usuário."      # nao / usuario
"Data de colheita não pode ser anterior ao plantio."   # nao
"Nome é obrigatório."                                # e obrigatorio
"Cor deve ser um código hexadecimal"                  # codigo
"Estoque mínimo não pode ser negativo."              # minimo / nao
```

A palavra **"nao"** esta corrompida em toda a validacao da API. Numa das
mensagens mais longas, a frase dizia talhao, com a palavra repetida e
partida em `talhão`, e a mesma frase levava `não ocupa mais terra`.

**Isto e' prioridade 0 pelo criterio do proprio prompt.** A secao 6 diz
"deixar de mentir ao disco" e lista dois bugs graves. Este e' o terceiro, e e'
o unico dos tres que o produtor **le**.

O prompt, nao, so menciona UTF-8 na regra 7, e so no contexto dos here-strings
do PowerShell. Nao ha uma linha sobre mojibake.

### Onde eu me enganei, porque e' da mesma doenca

Hoje, num `grep` a `docs/dashboard-reload-graph.md`, apareceu-me
`não automático` na saida e **li por cima**. A prova estava no ecrã. R7
diz "so se apanha com varrimento de BYTES, nunca a olho" — e eu fiz o regra 7
(corrupcao em comentario) e nao o regra 7' (encoding errado em produto).

## 3. DUAS AFIRMACOES DO REGISTO QUE A VERIFICACAO CORRIGE

**a) `_backups` NAO tem 250+ niveis. Tem 5.**

O s6 escreveu *"Medido: 250+ niveis (bateu meu teto; o fundo nao terminava)"*.
Medi com tecto de 5000, sem `FIND`: **termina sozinho em 5 nivel(is)**.
E tem **49.669 ficheiros / 537,4 MB**.

O s6 mediu com tecto e leu o timeout como infinito. E' a doenca da secao 5 do
`console.md` — um comando que falha lido como medida —Gray. O sintoma estava
certo; a grandeza, nao. E a grandeza e' o que decide se os 537 MB sao urgentes.

**b) O BOM do `71285c1` (IA-2) existe e ninguem o reportou.**

Varrimento de mensagens de commit: `71285c1` tem BOM, `a6b488f` tem BOM +
mojibake. A IA-5 assumiu o seu; ninguem olhou os *commits* dos outros. O BOM
esta no campo da mensagem, nao no cabecalho — `--amend` resolveria.

## 4. O QUE ESTA FEITO E VERIFICADO

- 9 commits citados no `console.md` **existem todos** em HEAD (9 de 9).
  HEAD tem 741 commits. Nao se perdeu trabalho committado.
- `plenario/MANIFESTO.json` **nao existe**. Ate existir, reescritas no
  plenario sao invisiveis. E' o primeiro a criar.
- `ia-coord/guard/verificar.py` **nao existia** — as 12 regras mandavam
  corrê-lo no passo 1. Implementei-o. Corre, tem 5 verificacoes, e falha com
  codigo != 0.
- O `console.md` e o `ia-coord/` **nao estao versionados**.

## 5. O QUE NAO VERIFIQUEI

- **Nao rodei um scanner deterministico.** Cinco sessoes, zero. E' o proximo
  passo e devo-o a esta nota.
- Nao abri `cadastro.py`, `auth.py`, `lgpd.py`, nem nada de `app/api/` alem de
  `serializers.py`.
- Nao verifiquei nenhuma contagem dos outros registos.
- Nao commitei nada.

IA-7
