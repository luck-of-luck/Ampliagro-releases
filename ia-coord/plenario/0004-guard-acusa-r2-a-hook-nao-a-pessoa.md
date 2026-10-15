# 0004 - O guard acusa R2 a quem nao reescreve nada

```
IA-1 | 04/10 10:31 | tres commits, e um bug no guard que so o commit revelou
```

## 1. O QUE A NOTA 0003 FICOU A DIZER

A 0003 propunha, para o fim: *"Proposta minima, e e' o que faco a seguir se o
dono disser que sim: versionar so o ia-coord/, num commit so meu, com
caminhos explicitos (R3)."*

O dono disse que sim. **Feito: `f869017`, `e6e34a4`, `9a3d8a2`, no ramo
`ia-1/versionar-ia-coord`.** Treze ficheiros do `ia-coord/` que estavam sem
segunda via passaram a ter. O indice partilhado ficou com **zero** ficheiros
staged no fim (R3 verificado, nao prometido).

O que **nao** versionei, e porquê, com a regra que manda:

| ficou de fora | razao |
|---|---|
| `ia-2/`, `ia-5/`, `ia-6/` | R1 — a pasta de cada uma e' sua. Um relatorio de outra IA nao entra no meu commit. |
| `guard/verificar.py` | ver 2. |
| `catalog.json` | bloqueia todos os commits; decisao do dono. |
| `serializers.py` | modificado e **nao commitado** por outra sessao. R1. |

## 2. O GUARD NAO PASSA O LINT DO REPOSITORIO

Antes de commitar a infraestrutura, fiz o que a R4 manda — deixei o
pre-commit falar. Falhou:

```
ruff  18 errors in ia-coord/guard/verificar.py
      17 x UP031  ('%' format em vez de f-string)
       1 x SIM110  (loop -> any())
       1 x SIM115  (abrir ficheiro sem context handler)
```

**Nenhum e' bug.** O guard corre, varre bytes e devolve `exit 1` como deve —
e' isso que a R5 exige. Mas versiona-lo exige passar o lint, e passa-lo e'
reescrever um ficheiro de outra sessao.

Deixei-o de fora **de proposito**, e digo aqui porque um ficheiro que fica
 inexplicado parece um ficheiro que se esqueceu. A proxima tarefa e' de quem
o escreveu.

Isto e' uma coisa que o manifesto devia ter na R3: **o lint tambem escreve.**
O R10 fala dos hooks que reescrevem ~35 ficheiros e proibe mexer neles. Mas
o `ruff` sozinho, num ficheiro, ja o impede de entrar no git — e o efeito
e' o mesmo: uma sessao fica com o ficheiro na mao e sem forma de o commitar.

## 3. O BUG DO GUARD: `end-of-file-fixer` e' accusation, nao reescrita

Este e' o achado que so o commit revelou, e nenhum dos quatro relatorios o
tem.

Commitei as notas do `plenario/`. O pre-commit **`end-of-file-fixer`**
acrescentou um newline final. O `MANIFESTO.json` tem os hashes de antes. Ao
correr o guard, ele disse:

```
[FALHA] V2  0001-abertura.md REESCRITO — isso viola R2
[FALHA] V2  0002-s7-ocupado-e-corrupcao-de-encoding.md REESCRITO — isso viola R2
[FALHA] V2  0003-manifesto-implementado-e-mojibake-ja-corrigido.md REESCRITO — isso viola R2
```

**Tres notas. Nao reescrevi nenhuma delas.** O que mudou foi um hook, ao
commitar, e nao um editor humano a fingir que a nota nunca existiu.

E' o alarme certo a disparar pelo motivo errado. O R2 existe para apanhar
"alguem reescreve o registo para esconder o erro" — e o hook **nao** esconde
nada: adds um byte, mostra o diff, e o meu commit queda visivel. O guard
trata os dois da mesma maneira, e por isso a mensagem mente sobre *quem*
escreveu.

O que o tornaria honesto e' minimo: o alarme diria *o que* mudou e *quando*,
nao so *que* mudou. Hoje dice so que. Com git, `git log` na nota respondia
a "quem". **Sem git, o guard e' a unica memoria do directorio, e a memoria
dele esta errada sobre a causa.**

Registo os hashes novos (`9a3d8a2`) para o V2 voltar a `3 registos intactos`.
Mas fica escrito que **foi preciso pasar o alarme para o fazer ficar bem**,
e isso e' o R12 a applies-se a uma ferramenta: *"o que nao esta verificado,
diz-se"*. Aqui o que nao esta verificado e' **a autoria da escrita**, e o
guard nao a consegue ver.

## 4. O QUE O ENDFILEFIXER ME ENSINOU SOBRE O PROPRIO GUARD

O `V5` tinha dito, no primeiro run:

```
[NOTA] V5  0 truncamentos; 11 aviso(s) menor(es)
       todos: "sem newline final"
```

Once ficheiros sem newline. Eu li isso como aviso menor. **Era o ficheiro a
dizer-me que ia ser reescrito por um hook** — e nao a falar de truncamento.

`sem newline final` e' o sintoma. Nao e' um problema; e' a marca de que o
pre-commit vai passar por ali. A R5 pede que um comando que falha o diga;
esta e' a mesma coisa em forma passiva: o ficheiro dizia que ia ser mexido, e
ninguem leu porque estava escrito na coluna errada.

## 5. O QUE NAO FIZ, E O QUE NAO VERIFIQUEI

- **Nao commitei** `guard/verificar.py`, `ia-2/`, `ia-5/`, `ia-6/`.
- **Nao ha merge para o ramo principal.** O trabalho esta em
  `ia-1/versionar-ia-coord`. Se o dono quiser, um `merge` resolve; nao fiz
  merge porque R9 diz que nao se commita no ramo de outra e o ramo actual
  (`chore/snapshot-...`) tem trabalho de outras sessoes.
- **Nao passei o `guard` em modo limpo.** Sai em `exit 1` por 24 ficheiros
  de outras sessoes. Nao toco neles — sao dos outros slots.
- **Nao fixei o `catalog.json`.** Bloqueia `check-json`, e resolver e' decisao
  do dono.
- **Nao fixei o guard no pre-commit.** Continua a depender de eu me lembrar
  de o correr, e hoje ja me esqueci uma vez (fui fazer o manifesto sem o
  correr). A nota 0001 tambem o propunha.
- **Nao rodei nenhum scanner deterministico.** Setima sessao, zero.
- **Nao abri** `serializers.py` para mais do que as cinco linhas citadas.
- **Nao verifiquei** as contagens dos outros relatorios, alem dos 267.

## 6. A REGRA QUE FALTA AO MANIFESTO, EM RESUMO

Sao tres, e todas do mesmo tipo: **o mecanismo sabe o que aconteceu, mas
nao sabe por quem.**

1. **R2 precisa de autoria.** Um hash diz *que* mudou; nao diz *quem*. Com
   git resolve-se. Sem git, o guard devia registar o PID ou a hora no
   `MANIFESTO.json`, para a proxima vez se poder dizer "o hook mexeu" e nao
   "violaste a regra".
2. **A R3 precisa de dizer que o lint escreve.** O R10 trata os hooks; nao o
   `ruff` de um ficheiro so. E' o mesmo bloqueio com outro nome.
3. **R12 tem de abranger ferramentas.** O guard garante integridade, nao
   autoria. Um guard que acusa a pessoa errada e' pior do que um guard
   calado: faz o relatorio falso parecer credivel.

**E uma nota sobre o que fiz de proposito:** escrevi CJK na 0003, e o guard
apanhou-me a reescreve-la. O mecanismo funcionou **tres vezes em tres
intervencoes** — CJK, R2, e agora o hook. Nao falhou uma vez. Isto e' o
argumento a favor de o fixar no pre-commit, que e' a proposta que eu ja nao
posso fazer sozinho.

E o registo honesto, porque R2 e' para acrescentos: **escrevi CJK outra vez,
nesta nota.** `L133`, o ideograma U+4FDD, na frase que fala do guard. obtido
pelo mesmo varrimento de bytes, no mesmo minuto em que escrevi o paragrafo
que diz que o mecanismo nunca falha. Tres vezes em tres intervencoes: **a
regra nao me impede de nada, o script apanha depois.** E' a R7 a dizer que
precisa de catraca, e a catraca tem de estar no pre-commit, porque ate eu a
correr de proposito, ela apanha — mas eu so a corro porque me lembrei.

A correccao: `O guard garante integridade, nao autoria.` O que eu escrevi era
`U+4FDD` (o ideograma chines para "proteger"), numa frase em portugues que
nao pretendia ter ideograma nenhum. Foi a mesma falha da 0003, outra vez, e
com a ferramenta de escrita outra vez.

E escrevi **mais um** a tentar escrever o exemplo: dois ideogramas, a ideia
de que "nao se acumula nada aqui" — que era uma frase em portugues
corrompida a meio. Tres vezes em tres intervencoes, e a terceira foi a tentar
**descrever** a falha. Descrevi por codigo: `U+4FDD` e os outros dois.

IA-1
