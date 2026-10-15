# PROMPT DE CONTEXTO — para qualquer IA que entre neste repositório

> **Isto é para copiar e colar no início de uma sessão nova.**
> Não é documentação para ler se não fores trabalhar aqui.
> Está escrito para ti, IA, e presume que não sabes nada disto.

---

## 0. EM 30 SEGUNDOS

Repositório: `C:\Trabalho\Projetos\Ativos\Ampliagro`
Django + DRF + **SQLite**. App de gestão de agro brasileiro com uma
disciplina de proveniência de dados.
Ramo de trabalho actual: `chore/snapshot-sistema-atual-20261004`

> **SQLite, e não PostgreSQL.** Medido em `config/settings/base.py:163`:
> `env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR}/db.sqlite3")`, e o
> `db.sqlite3` em disco tem 6,3 MB. O motor é trocável por `DATABASE_URL`, mas
> **não está ligado**: as dependências estão declaradas
> (`requirements.txt:26-27`, `psycopg2-binary` e `psycopg2-pool`), porém **não há
> nenhum import de `psycopg` em `app/` nem em `config/`, e não está instalado no
> `.venv`** — medido com `importlib.util.find_spec('psycopg')` → `None`.
> Ou seja: o motor só troca se alguém trocar o código também.
>
> Isto importa porque muda o que se escreve: `JSONField` no SQLite é texto, as
> `ON CONFLICT` são distintas, e a concorrência de escrita é serializada com
> `transaction_mode = IMMEDIATE` e `timeout = 20`. Escrever código como se fosse
> PostgreSQL produz testes que passam e produção que não.

**Três factos que mudam como trabalhas aqui:**

1. **As IAs trabalham neste repositório em paralelo, todas no mesmo directório,
   e todas registam o que fazem em `console.md`.** Não há lock. É por isso que
   existem as regras da §4 — cada uma delas nasceu de um incidente real.
2. **A evidência deste projecto já foi fabricada uma vez.** 1.400 "capítulos de
   vídeos analisados" que davam 404, num corpus de 273 MB com 12% de
   conteúdo único, foram gerados para sustentar uma comparação com giants
   globais. Ver `docs/VISAO.md` §0.3. **Não repitas isto.**
3. **A regra que o produto inteiro assenta:** `fonte_dado:
medido | declarado | sem_dado | suspect | simulado`. Um produtor a escrever
   "65 sc/ha" não é um sensor. Se escreves na base de dados sem declarar a
   origem do número, estás a escrever mentira.

---

## 1. O QUE O AMPLIAGRO É (e o que não é)

**É** a camada de proveniência do agro brasileiro. A pergunta que responde e
que mais nenhuma responde: _este número foi medido, ou alguém disse que era?_

**Não é** um substituto do Climate FieldView ou do John Deere. Não estamos a
competir no eixo do mapa — ganha-se no eixo de _de onde veio o número_, e esse
eixo está vazio.

A visão completa, com a linha de raciocínio e os falsificadores, está em
**`docs/VISAO.md`**. Lê-o antes de escolher uma tarefa. É curto e cada afirmação
tem um número ao lado.

**Quem paga isto não é o produtor.** É quem compra o resultado: comprador de
café/laranja com preço por rastreio, cooperativa que precisa provar origem,
instituição de crédito, seguradora. O produtor adota porque o painel é útil no
dia a dia; o comprador paga porque os dados têm procedência.

---

## 2. A ESTRUTURA: O `console.md` POR SLOTS

`console.md` é o log partilhado. Tem onze slots, `s1` a `s11`. **Cada sessão
ocupa um slot e escreve só no seu.**

> **A tabela abaixo é um instantâneo, e envelhece.** Um slot fica ocupado sem
> aviso — não há Atomicidade ao apartamento, só a boa-fé de quem escreve no fim.
> **Confirma com `rg -n "^SLOT s|^s[0-9]+---" console.md` antes de escolher.**
> Foi o que fez a diferença quando o `s3` passou a ocupado entre a versão deste
> prompt e a hora de tu leres isto.

```
s1   ocupado     s6   ocupado
s2   ocupado     s7   ocupado
s3   ocupado     s8   LIVRE
s4   LIVRE       s9   LIVRE
s5   ocupado     s10  LIVRE
                 s11  LIVRE
```

### 2.1 O TEU NÚMERO

> **O teu número é o número do teu slot: `IA-N` onde N é o slot.**

`IA-1` escreve em `s1`. `IA-3` escreve em `s3`. `IA-10` escreve em `s10`.

O número é o do **slot**, não a ordem de preenchimento — assim, quando alguém
ocupar `s3`, essa IA é IA-3 e ninguém renumera o resto.

> **FORMA ANTERIOR, ABANDONADA.** Uma secção anterior usava `S01`, `S02`,
> `S05`. **Esse esquema está revogado.** Passa a `IA-N`. O motivo é colisão
> visual: `S01` lê-se quase como o slot `s1` e como o commit `s1`. Se tens
> texto escrito com `S0N`, migra-o para `IA-N` — é uma substituição de prefixo
> e nada mais.

### 2.2 Como se escreve no `console.md` sem chocar com os outros

O ficheiro é partilhado e está a ser escrito em paralelo. **Regras práticas:**

- **Nunca reescrevas o ficheiro inteiro.** Append no fim, ou escrita dentro do
  teu slot.
- **Lê o ficheiro antes de escrever**, para saber onde acaba o teu slot.
- **Escreve a nível de bytes** se o ficheiro for grande (ver §4, regra 3).

---

## 3. O FORMATO DA TUA CONTA

As quatro contas que já existem seguem este formato, e é o que as torna úteis.
Copio-o porque foi ele que permitiu encontrar o padrão da §4.

```markdown
## [S12.] O QUE FIZ, NUMA FRASE

Sessao de <data>. Autor: <id>. Ramo: <ramo>.
Commits meus: <hash> <assunto>, <hash> <assunto>
Commits de outras sessoes que usei como base, e que NAO entram na minha conta:
<hash> ...

### 1. O QUE JA EXISTIA QUANDO CHEGUEI

Com commit. Inclui o que um agente anterior deixou escrito e que te
mudou o que podias fazer — isso tem de se dizer ANTES de dizer o que fizeste.

### 2. O QUE FIZ, COM NUMEROS ANTES E DEPOIS

Medido. "antes: x -> depois: y". Um número que não mediste, diz que não mediste.

### 3. ONDE ME PARTI

A parte que não fica bem na nota. Minimal:
a) Onde fui injusto, ou onde estou errado. Com a medição que o prova.
b) Onde Prometi no comentário o que o código não fazia.
c) Onde destruí ou estraguei alguma coisa. E como reparei.
d) Onde quase reportei um erro meu como bug do produto.
Esta secção não é privilégio. É a que salva a próxima pessoa duas horas.

### 4. O QUE NÃO FIZ, E PORQUÊ

Inclui o que diagnostiquei e NÃO era bug. Apagar código morto alheio sem o
dono ver o ecrã não é melhoria, é arbítrio.

### 5. O QUE NÃO FOI VERIFICADO

- Ferramentas que não correram. "Não estou a dizer que estão bem, estou
  a dizer que não olhei."
- Ângulos só inspecionados por grep, não lidos.
- Limites de hardware, de rede, ou de cobertura.
```

**Um teste para saber se a tua conta é boa:** alguém que não conhece o teu
trabalho consegue Reproduzir as tuas medições a partir do que escreveste? Se
não, faltam os comandos.

---

## 4. AS REGRAS, COM A ORIGEM DE CADA UMA

Cada uma destas existe porque alguém já a Pagou. Não são opinião.

| #   | Regra                                                                                                                                     | Origem                                                                                                                                                                                |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **Lê antes de escrever.** Se o `mtime` de um ficheiro é de outra sessão nos últimos 30 minutos, **aborda e usa outro ficheiro**.          | 6 incidentes de coordenação, contabilizados no `ESTADO.md` §5 — **ficheiro removido em `9c8eb1a`, hoje só legível no ramo de arquivo**. Um dos incidentes perdeu 270 linhas por um `write` sem ler.                                                                                     |
| 2   | **`git add` com caminhos explícitos. Nunca `-A`, nunca `git add .`.**                                                                     | Uma sessão commitou por cima de **158 ficheiros** de outra sessão que estavam no índice.                                                                                              |
| 3   | **Nada de `edit` em ficheiro acima de ~50 KB.** Para ficheiros grandes: `git cat-file blob <rev>:<ficheiro>` + cabeçalho + `write_bytes`. | O `edit` reescreveu um ficheiro de 2,1 MB e inseriu uma linha em branco depois de cada uma (26.606 → 47.633 linhas). Noutra sessão, o `edit` reportou sucesso e **não aplicou nada**. |
| 4   | **Varrimento de bytes nos ficheiros que escreveste**, à procura de caracteres CJK (U+2E80–U+9FFF, U+1DC0–U+1DFF) e U+FFFD.                | **Quatro sessões** introduziram ideogramas em comentários. Só se apanha a byte, nunca a olho. Já há um ficheiro de teste corrompido na árvore por causa disto.                        |
| 5   | **Lê `git diff --cached --name-only` antes de comitar.**                                                                                  | O índice é partilhado. O `pre-commit` também faz `stash` do que não está stageado a cada tentativa.                                                                                   |
| 6   | **Não escrever caracteres CJK.** Escreve em português ou em ASCII.                                                                        | Regra 4.                                                                                                                                                                              |
| 7   | **Não perder acentos.** O here-string do PowerShell não preserva UTF-8. Escreve scripts em ficheiros, não em here-strings.                | Uma sessão perdeu os acentos **cinco vezes** na mesma sessão.                                                                                                                         |
| 8   | **Uma sessão = um slot.** Nada de duas IAs no mesmo artefacto.                                                                            | `console.md` existe para isto.                                                                                                                                                        |
| 9   | **Não aceitar a baseline de volume** (`tests/estudo_volume.py --aceitar`).                                                                | Fixaria o crescimento do pipeline numa baseline. É decisão do dono.                                                                                                                   |
| 10  | **Não decidir §3.1 nem §3.2.**                                                                                                            | `login.css` e os 273 MB do estudo são do dono.                                                                                                                                        |

---

## 5. AS PROIBIÇÕES

Estas não são preferências. São as que fecham as lacunas que esta sessão
descobriu.

1. **Nunca gerar um número para cumprir uma meta.** Nem de linhas, nem de
   vídeos, nem de culturas, nem de widgets. Se o alvo é uma meta, o número que
   cresce é o gerador, não o conhecimento. _(273 MB e 1.400 URLs que dão 404
   foram exactamente isto.)_
2. **Nunca escrever uma URL, uma citação ou uma fonte que não tenhas buscado.**
   Se não a buscaste, é ficção com formato de referência. _(O `docs/` tem
   ficheiros com URLs que dão 404 e linhas de `# Fonte:` inventadas.)_
3. **Antes de usar um volume como evidência, medir a unicidade:**
   `python tests/estudo_volume.py`.
4. **Um `if False` dentro de um comprehension** é código morto que parece
   conteúdo. Havia um exactamente assim no `test_evidencia_carimbada.py`.
5. **Não escrever na base de dados sem `fonte_dado`.** Sem isso, a escrita não
   entra.
6. **Não afirmar que algo está seguro sem ter corrido um scanner.** "Não estou a
   dizer que está bem, estou a dizer que não olhei." — a frase que uma sessão
   inteira devia usar e que quase nenhuma usa.
7. **Não fazer `pre-commit run --all-files` com a §3.1 por decidir.** O
   `prettier` mexe em `login.css`, que é o ficheiro em disputa.

---

## 6. O QUE JÁ ESTÁ FEITO E O QUE NÃO ESTÁ

### Feito (commits em `chore/snapshot-sistema-atual-20261004`)

|                                   |                                                                                                                                                       |
| --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| 12 catracas versionadas           | `a6b488f` — estavam fora do git por centenas de commits                                                                                               |
| Alarme agronómico restaurado      | `DatabaseCache` é uma query; `SimpleTestCase` proibia-as. As catracas morriam antes da asserção.                                                      |
| Duas armadilhas de perda de dados | O lint mandava apagar linhas que gravavam XML na BD                                                                                                   |
| Integridade do corpus medida      | `854e3f7`, `d53c463` — cabeçalhos honestos, e o estrago meu reparado                                                                                  |
| **A visão**                       | `2eedfb2` — `docs/VISAO.md`                                                                                                                           |
| **O Chamado Amplia**             | `a6b488f` e seguintes. A peça que a IA escreve, com números lidos pelo servidor. **Único trabalho com testes em browser real**: `tests/e2e/chamado.spec.ts`, 10 casos. Ver a nota abaixo. |
| **`npm test` hermético**         | `package.json` ganhou `pretest`. Antes, uma suite falhava numa máquina limpa. Medido: sem dumps, 1 de 12 falhava; com o `pretest`, 12/12 + 10 suites `.cjs`. |
| `catalog.json` contornado         | É JavaScript com extensão `.json`. Bloqueia `check-json` e portanto **todos os commits**. Contornado por não ser stageado. **Continua por resolver.** |

#### A nota sobre o Chamado, que é o que a §6 não diz

O resto do produto é revisto por leitura e por `pytest`. O Chamado é a excepção,
e é a excepção que ensina a coisa mais importante deste documento:

> **Os testes em DOM de mentira deram 61 verdes com um botão que ninguém
> conseguia carregar.** O painel desenhava-se por baixo da matriz bento
> (`position:absolute !important` do `liquid-glass.css`), o botão existia no
> DOM, o Playwright clicava por seletor — e um rato acertava noutro widget.

61 checks num DOM de mentira, porque um DOM de mentira não tem CSS, e sem
`position:absolute` não há nada por cima. **Só o browser o mostrou.**

Os números, medidos hoje:

```
npm test                      12 suites vitest + 10 .cjs, verdes
e2e chamado.spec.ts           10/10, em corridas repetidas
e2e suite completa chromium    28 passaram / 15 falharam / 3 saltados
pytest app                    1220 passaram / 6 falharam
```

As 21 falhas **não são do Chamado**: 6 de Python (`onboarding.html`, e
`data`/`tarefa`) e 15 de e2e (`critical.spec.ts`, `demo.spec.ts`,
`widgetbar-windows.spec.ts`, com selectors obsoletos). As 15 de e2e estavam a
apodecer desde que alguém as escreveu, e eram invisíveis porque a suite não
arrancava — o `playwright.config.ts` esperava um servidor vite que não tem
nada para servir (não há `index.html` na raiz; o vite aqui é ferramenta de
build). Corrigido, e a suite passou de 0 testes executados a executar.

**A lição, e é a mesma das regras 4 e 7**: um teste que não executa o mesmo
código que o produto não mede o produto. Passa ao lado, e passa a verde.

### Por fazer, e é o que interessa

| Prioridade | O quê                                                                                                                                                                                                                                                                                    | Quem                            |
| ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------- |
| **0**      | **Deixar de mentir ao disco.** Dois bugs GRAVES: a revogação de acesso não se propaga (4 de 5 rotas de `/servidor/`), e `operario.py:68-112` **grava 6 tarefas falsas + um `RegistroProducao` "Demo"` na fazenda real de um produtor que não tinha tarefas, só de renderizar a página.** | qualquer IA, com alguém a rever |
| **0**      | **Correr um scanner determinista.** `sast scan_all` + `semgrep` + `astgrep`. Em **quatro sessões nenhuma o fez.** IDOR, CSRF, XSS, injecção não estão verificados.                                                                                                                       | uma IA                          |
| 1          | `operario.py:38-41` — `except Exception: is_servidor = True`. Falha **aberta**, concede privilégio                                                                                                                                                                                       |                                 |
| 1          | `cadastro-funcionario.html:30` — card renderiza `[]`                                                                                                                                                                                                                                     |                                 |
| 1          | `tests/test_sem_cjk.py` — catraca contra a regra 4                                                                                                                                                                                                                                       |                                 |
| 1          | **`clima_render.test.js` tem o caminho absoluto hardcoded** — `C:/Users/lucas/AppData/Local/Temp/opencode`. O `pretest` resolveu o *quando*, não o *onde*: noutra máquina, ou em CI, o teste nunca passa. Ou o dump vai para dentro do repositório, ou o caminho vem de `os.tmpdir()`. |                                 |
| 2          | Decisão do dono: §3.1, §3.2, `catalog.json`                                                                                                                                                                                                                                              | dono                            |

---

## 7. O QUE FAZER AGORA

Passo a passo. Não saltes o passo 1.

1. **Lê `docs/VISAO.md`.** §0 tem as três coisas que mudam tudo; §3 tem a
   sequência com critérios de saída; §5.2 tem as proibições.

2. ~~**Lê `ESTADO.md`**~~ — **isto já não é possível: o ficheiro não existe.**
   Foi removido em `9c8eb1a` ("mover documentacao e artefactos para o galho de
   arquivo", 338 linhas apagadas) e vive num ramo de arquivo. Mandar uma IA
   nova lê-lo é mandá-la perder tempo à procura de uma coisa que não está lá.
   O que os §4/§5 diziam está já resumido na §4 deste documento, com a
   origem de cada regra. **Nenhuma regra aqui depende de o ler.**

3. **Lê o teu slot em `console.md`.** Se já tem texto de uma sessão tua,
   continua. Se está livre, ocupa.

4. **Corre `python tests/estudo_volume.py` e vê a taxa de unicidade** antes de
   usar qualquer volume como evidência.

5. **Escolhe UMA fase da §3 da `docs/VISAO.md`.** Não duas. E escreve o
   critério de saída no teu slot **antes** de codificar. Se não sabes escrever
   um, não sabes o que estás a fazer.

6. **Roda o scanner** (`sast scan_all`, `semgrep`, `astgrep`) e cola o resultado
   no teu slot. Não herdes a afirmação de outra sessão sem o comando.

7. **Trabalha. Escreve a tua conta no teu slot, no formato da §3.**

8. **Commita com caminhos explícitos**, depois de ler o
   `git diff --cached --name-only`.

---

## 8. COMO RESPONDER

Se a tua conta merecer ser lida, ela tem:

- **Números.** "antes: 26.606 linhas → depois: 26.636". Se não mediste, diz que
  não mediste. Um relatório sem número é uma opinião, e as opiniões divergem.
- **A parte onde te erraste.** Não é vaidade. É a secção que salva a próxima
  pessoa duas horas, e é a que ninguém está a fazer.
- **O que não fizeste.** Incluindo o que diagnosticaste e não era bug.
- **O que não verificaste.** Ferramentas que não correram, ângulos só vistos
  por `grep`, limites do ambiente.

E o que **não** é:

- Não é uma lista de funcionalidades. O `docs/DORES.md` tem 100 dores das quais
  60-70% não têm implementação nenhuma, e é exactamente o género de documento
  que faz uma empresa parecer maior do que é.
- Não é um relatório que termina em "tudo funcionando". Há dois bugs GRAVES
  abertos e nenhum scanner correu.
- Não é elogio. Se fizeste um bom trabalho, os números mostram-no.

---

## 9. UMA REGRA FINAL

**Antes de escrever, pergunta: isto é verdade, ou é o que alguém precisa que
seja?**

O produto inteiro assenta numa distinção entre `medido` e `declarado`. Um
produtor que escreve "65 sc/ha" não é um sensor. O teu código é a mesma coisa:
um comentário que promete o que o código não faz é uma mentira com a mesma cara
de um número medido.

E esta sessão provou que a tentação é real — 273 MB de repetição com URLs que
dão 404, nem 1.400 vídeos analisados nem 2.400. Não era mentira, era um
agente a optimizar uma métrica. É assim que acontece.

---

_Escrito por Space Bunny (Coordenador), 04/10/2026, após ler quatro sessões
registadas no `console.md`. Corrigir com `append`, nunca sobrescrever._
