# A VISÃO DO AMPLIAGRO — e a linha de raciocínio até ela

> Para as IAs que vão trabalhar neste repositório.
> Não é um documento de marketing. Não é uma lista de funcionalidades.
> É a cadeia de raciocínio que vai do que existe hoje ao que pode existir,
> escrita para que uma IA nova não tenha de a redescobrir — e para que não
> a invente.
>
> Escrita 04/10/2026, depois de ler quatro sessões de trabalho registadas no
> `console.md` (s1, s2, s5, s6).
>
> Regra de leitura: **se este documento e uma acção tua divergem, este
> documento tem razão e tu vais ver porquê.** Se achares que ele está errado,
> escreve no teu slot do `console.md` _com a medição que o refuta_.

---

## 0. TRÊS COISAS QUE NÃO SÃO OBVIAS E QUE MUDAM TUDO

Antes da visão, o que aprendemos e que não está em nenhum README.

### 0.1 O produto tem um único diferencial, e não é uma funcionalidade

`app/validators.py`, e aigrations 0061-0062. O vocabulário:

```
medido | declarado | sem_dado | suspect | simulado
```

Um produtor escreve "65 sc/ha". Isso é `declarado`, **não** `medido`.
A ZARC é publicada pela Embrapa — é uma declaração _dela sobre a região_, não
uma medição na propriedade. Também `declarado`, com o campo `fonte` ao lado.

Nenhuma empresa de software agro global faz esta distinção. Todas mostram um
número com a mesma cara. É o único ponto onde o Ampliagro ganha sem
concorrente, e a §2 do `console.md` (s2) provou que é coerente em todo o
código: `null` em vez de `0` onde é razão, `0` onde é soma, e o comentário em
`app/api/views/user.py:297` diz porquê.

**Isto é uma filosofia, não uma funcionalidade.** Filosofias são baratas de
copiar. Este documento assume que vai ser copiado, e por isso o §4 não depende
dele ser original — depende de ser aplicado todos os dias.

### 0.2 A honestidade é simultaneamente o diferencial e o problema

`ESTADO.md` §7, medido:

```
Cultura no catálogo ............................... 709
Registos em ZARC (janela por município) .......... 0
```

Um painel honesto começa vazio. Mostrar `sem_dado` onde os outros mostram um
número é o correcto **e é a primeira coisa que faz um produtor desistir.**

Isto não se resolve escolhendo entre as duas coisas. Resolve-se **trazendo para
o primeiro minuto o que já existe e é verificável** — sem inventar. A §3 é
isso.

### 0.3 A evidência deste projecto já foi gerada uma vez

Isto está aqui porque é a armadilha mais cara em que esta fell.

`docs/super-estudo-globo-rural/` chegou a 273 MB e 1.400 "capítulos de vídeos"
que sustentavam a comparação com giants globais. Medido a 04/10/2026:

| Ficheiro                                | Linhas | Únicas |      Taxa |
| --------------------------------------- | -----: | -----: | --------: |
| `MANIFEST-REAL.json`                    |      9 |      9 |    100,0% |
| `00-ARQUITETURA-TOP1.md`                |     93 |     88 |     94,6% |
| `SISTEMA-TOP1-INTEGRACAO.md`            |     86 |     79 |     91,9% |
| `SUPER-ESTUDO-REAL.md`                  |  1.605 |    429 |     26,7% |
| `ANALISE-1001-2400-PROXIMO.md`          | 25.203 |  3.036 | **12,0%** |
| `ANALISE-50-VIDEOS-PRODUTOR-SISTEMA.md` |  3.104 |    241 |  **7,8%** |

As 1.400 URLs desse ficheiro (`episodio/2300` … `episodio/3699`) foram
**geradas por um contador**. Verificado por fetch, com controlo positivo no
mesmo host: as URLs dão **404**; uma URL real do Globo Rural dá **200** e o
artigo completo. E o nome do ficheiro confessava: `PROXIMO`.

**PROIBIÇÃO, para todas as IAs:**

1. **Nunca gerar um número para cumprir uma meta.** Nem de linhas, nem de
   vídeos, nem de culturas, nem de widgets. Se o alvo é uma meta, o número que
   cresce é o gerador, não o conhecimento.
2. **Nunca escrever uma URL, uma citação ou uma fonte que não tenha sido
   buscada.** Se não foi buscada, é ficção com formato de referência.
3. **Antes de usar um volume como evidência, correr a taxa de unicidade**:
   `python tests/estudo_volume.py`. Está em `ESTADO.md` §3.2 e existe precisamente
   para isto.
4. **Um `if False` dentro de um comprehension é código morto que parece
   conteúdo.** Havia um exactamente assim no `test_evidencia_carimbada.py:192`.

Se em algum momento te pedirem "cria NNN linhas", a resposta correcta é
perguntar **que conhecimento** justifica NNN linhas.

---

## 1. O QUE O AMPLIAGRO É HOJE, MEDIDO

Sem bravata, e com o número ao lado.

```
app/                 75.220 linhas de Python
tests/                8.571 linhas
rotas                179
modelos              ~966 classes
migrations           65 (até 0064)
cobertura            25%   (20.363 de 27.326 linhas por cobrir)
commits 30 dias      ~700
```

E o que a §1 do `console.md` (s5) mais um teste de `ruff` apanharam:

- As **12 catracas do projecto estavam fora do git**, por centenas de commits.
  Invisíveis a qualquer revisão, e um `git clean` comia-as.
- A catraca agronómica estava a morrer de `DatabaseOperationForbidden` — o
  alarme do dono de sistema estava tapado por um alarme de instrumentação.
- Nove erros de lint. **Dois eram armadilhas de perda de dados:** o lint dizia
  "variável não usada" e apagá-las parava de gravar o XML na base de dados.

E o que `s6` (Predador) achou e **ninguém corrigiu ainda**:

| Gravidade | O quê                                                                                                                                                                                                         | Onde                                        |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------- |
| **GRAVE** | Revogação de acesso não se propaga: 4 de 5 rotas de `/servidor/` não checam `ativo_servidor`. Quem tem sessão ativa continua a ler maquinário, tarefas e alertas de telemetria **depois de ser desactivado.** | `servidor.py:196,239,275`, `operario.py:21` |
| **GRAVE** | Uma view **escreve dado falso no banco**: renderizar a página de um produtor sem tarefas cria 6 `TarefaEstagio` falsas + um `RegistroProducao` "Demo". Sem gate de DEBUG.                                     | `operario.py:68-112`                        |
| MÉDIO     | `except Exception: is_servidor = True` — falha **aberta**, concede privilégio                                                                                                                                 | `operario.py:38-41`                         |
| BAIXO     | Card renderiza `[]` (lista como escalar)                                                                                                                                                                      | `cadastro-funcionario.html:30`              |

**O segundo é o inverso exacto do princípio do produto.** A `s1` do `console.md`
defendeu `null` em vez de `0` porque `0` é mentira. A `s6` provou que a mesma
mentira está a ser escrita no disco noutro sítio. Uma IA que implemente a §2
sem corrigir isto constrói o produto ao contrário.

E uma lacuna que atravessa as quatro sessões:

> **Nenhum scanner determinista correu. Nenhum.** Sem `sast`, sem `semgrep`, sem
> `astgrep`. IDOR, CSRF, XSS, injecção: **não olhados.** Não é "estão bem" — é
> "ninguém olhou."

---

## 2. A VISÃO

Não um sistema de gestão que ganha mapas ao FieldView. **A camada de
proveniência do agro brasileiro.**

A pergunta que o Ampliagro responde e mais nenhuma responde:

> **Este número foi medido, ou alguém disse que era?**

Tudo o que decorre daqui:

- Um produtor que registou safras sabe, ao fim do ano, o que tem medido e o que
  tem de memória. Hoje perde essa distinção na primeiraHarvest de resumo.
- Um comprador que paga mais por um lote rastreado paga por uma **declaração
  declarada como declaração**, não por um número com a mesma cara dos outros.
- Uma cooperativa que agrega tem um DRE em que cada valor tem uma fonte.
- Um inspetor de GlobalG.A.P. recebe o rasto com `fonte_dado` por campo, e o
  campo `fonte` diz **de onde veio a janela de plantio** (Embrapa), não "o
  sistema".

### 2.1 Porquê isto e não outra coisa

|                       | FieldView / John Deere     | Planilha do produtor |
| --------------------- | -------------------------- | -------------------- |
| O que mostra          | mapas, camadas, telemetria | números              |
| De onde veio o número | **não diz**                | não sabe             |
| Auditoria             | difícil                    | impossível           |
| Para quem paid        | o Helmut                   | ninguém              |

O Ampliagro **não ganha** no eixo do mapa. Ganha no eixo da proveniência, e
esse eixo hoje está vazio. Deixá-lo vazio é uma escolha de produto, não uma
falta de envergadura.

### 2.2 Quem paga isto — e porque o produtor não é o primeiro cliente

O produtor não paga por proveniência: paga por harvest. A proveniência paga
**quem compra o resultado**:

1. Comprador de café/laranja com preço por qualidade e por rastreio.
2. Cooperativa que precisa de provar origem para vender a um programa público.
3. Instituição de crédito que em princípio exige histórico verificável.
4. Seguradora, quando a-App ressurge.

Isto é uma **estratégia de horizontal**. O produtor adota porque o painel é útil
no dia a dia (§3); o comprador paga porque os dados têm procedência (§4). São
dois utilizadores do mesmo registo.

---

## 3. A SEQUÊNCIA — com critério de saída, não com intenção

Cada fase tem uma **condição verificável**. Sem ela, a fase não passou.
É a diferença entre um plano e um relatório.

### FASE 0 — Deixar de mentir ao disco _(antes de qualquer função nova)_

Não há porquê añadir uma capacidade a um sistema que já grava mentira. Duas
correções curtas (`s6` §9 já as especificou) e uma lacuna:

|                                       | Critério de saída                                                                                                                                            |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `operario.py:68-112` sem dados falsos | Renderizar a página de um produtor sem tarefas **não cria nenhuma linha na base de dados**. Teste que abre a BD e conta antes/depois.                        |
| Revogação propagada                   | `app/tests_servidor.py:286` passa a iterar **todas** as rotas de `/servidor/`, não só o dashboard.                                                           |
| `operario.py:38-41` falha fechada     | Excepção no perfil → `is_servidor=False`, redireccionar.                                                                                                     |
| **Scanner correr**                    | `sast scan_all` + `semgrep` + `astgrep` executados, resultados colados no `console.md`. Isto não é opcional: sem ele nenhuma das fases abaixo é verificável. |

**A regra que torna isto obrigatório:** `operario.py:68-112` é uma prova de que
o `sem_dado` não está a ser aplicado ao lado que escreve. Qualquer fase nova
que escreva na base de dados passa a ter de declarar `fonte_dado` na mesma
passagem. **Sem `fonte_dado`, a escrita não entra.**

### FASE 1 — O primeiro minuto, sem inventar nada

O produtor abre a aplicação e não vê nada. Não é culpa do `sem_dado` — é
falta de **material de origem verificável** no primeiro ecrã.

|     | O que traz                                                                                                                                                                     | Critério de saída                                                                                                                         |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------- |
| 1.1 | A ZARC semeada com a **fonte real** (Embrapa, por município), com `fonte="Embrapa — ZARC"` ao lado da data. Endpoint `/api/zarc/para_minha_regiao/` já existe (`ESTADO.md` §8) | Zero datas geradas. `python tests/test_zarc_regiao.py` passa, e **o teste varre o JSON à procura de qualquer ISO date** com a ZARC vazia. |
| 1.2 | "Estou em Passo Fundo, o que posso plantar?" — já feito (§8)                                                                                                                   | Produtor escreve município + recebe culturas e janelas, sem escolher cultura primeiro                                                     |
| 1.3 | Importar o que já existe: Excel do produtor, painel da máquina, memória                                                                                                        | Um produtor com 5 safras em papel chega a um painel em menos de 2 minutos, sem digitar 40 campos                                          |
| 1.4 | **O painel que entra com `declarado` visível.** O que o produtor escreveu aparece como dele, com a fonte                                                                       | Produtor reconhece o próprio número e vê que está marcado como-declared                                                                   |

**O que NÃO entra na fase 1:** qualquer widget novo, qualquer mapa novo,
qualquerNotificação nova. A fase 1 é sobre **material de origem**, não sobre
superfície.

### FASE 2 — A proveniência que alguém paga

|     | O quê                                                                       | Critério de saída                                                                                                 |
| --- | --------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| 2.1 | Exportação GlobalG.A.P.: cada campo com `fonte_dado` e `fonte` no documento | Um inspetor consegue distinguir o que foi medido do que foi importado, **sem perguntar ao sistema**               |
| 2.2 | Custo por hectare, por talhão, por safra — com `fonte_dado` por linha       | `custo_ha` que é `None` quando não há despesa **continua** a ser `None`. É o contrato de `s1`/`s2` e não se toca. |
| 2.3 | O comprador pede o dado                                                     | Um comprador real pede o rasto e o sistema responde com o `fonte_dado` por campo                                  |

### FASE 3 — A máquina, e só depois

Só entra quando o sensor é real e o dado entra com a sua origem.

|     | O quê                                       | Pré-condição                                                                                                                                             |
| --- | ------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 3.1 | ZARC e janelas de plantio do próprio talhão | 1.1 semeada. Uma janela gerada é uma recomendação de risco climático falsa.                                                                              |
| 3.2 | NDVI / Sentinel-2                           | Fonte nomeada e datada. Nunca uma interpolação sem `fonte`.                                                                                              |
| 3.3 | IoT / LoRa / sensores                       | `Device` + `TelemetryData` **com `fonte_dado: medido` e o `device_eui`**. Um valor de sensor que chegue ao painel sem `device_eui` é um número sem dono. |
| 3.4 | Integração com a máquina (CAN/ISOBUS)       | Depende de 3.3                                                                                                                                           |

---

## 4. O QUE FAZ ESTA VISÃO FALHAR — os falsificadores

Uma visão sem falsificador é um destino, e um destino não se mede.

**F1 — Se o produtor continuar a não adotar depois da Fase 1 completa.**
Se com a ZARC semeada, o import de Excel e o `declarado` visível o produtor
ainda fechar a aplicação no primeiro minuto, então **o problema não é
material de origem — é outro, e ainda não o identificámos.** Este é o
falsificador mais importante e o mais desvalorizado: a Fase 1 tem de poder
falhar.

**F2 — Se ninguém pagar por proveniência.**
Se, depois da Fase 2, nenhum comprador, cooperativa ou instituição pedir o
rasto, então `fonte_dado` é uma boa prática de engenharia e não um
posicionamento de mercado. Nesse caso o Ampliagro é um sistema de gestão
honesto e BOM, e o pitch tem de dizer isso em vez de prometer mais.

**F3 — Se um concorrente maior adicionar `fonte_dado`.**
É o cenário mais provável e o mais barato para eles: é uma coluna. Não construir
nada à volta disso. Construir à volta do §2.1 (a procedência que o comprador
**paga**), que exige confiança acumulada — anos de registo com `fonte_dado`
correto é uma barreira de saída real.

**F4 — Se a Fase 0 não fechar.**
Se `operario.py:68-112` continuar a escrever dados falsos depois de duas
tentativas, o problema não é o ficheiro: é que **ninguém tem o direito de dizer
não ao que já está feito.** Isso é um problema de coordenação e diz respeito à
regra da ESTADO.md §5, não ao código.

---

## 5. PARA AS IAs: COMO USAR ESTE DOCUMENTO

### 5.1 O que fazer

1. **Leia a §1 antes de qualquer tarefa.** Ela tem os números reais e os dois
   bugs graves em aberto. Implementar sem os ler é construir às cegas.
2. **Escolha uma fase.** Não duas. A sequência existe porque a Fase 2 sem a
   Fase 1 produz uma feature que ninguém usa.
3. **Escreva o critério de saída no seu slot do `console.md` ANTES de
   codificar.** Se não consegue escrever um, não sabe o que está a fazer.
4. **Rode o scanner** (`sast` / `semgrep` / `astgrep`) e cole o resultado. Não
   herde a afirmação de outra sessão sem o comando.
5. **Toda a escrita na base de dados declara `fonte_dado`.** Sem isso, a escrita
   não entra.

### 5.2 O que não fazer

1. **Não gerar conteúdo para cumprir metas.** Ver §0.3. É a regra mais
   importante deste documento e a mais fácil de violar por acidente.
2. **Não tocar em `base.py` sem ler o comentário.** `CACHES` é `DatabaseCache`
   porque o `LocMemCache` fazia o painel voltar a um número antigo com
   autoreload. O hook de teste foi isolado **só nos testes** —
   `tests/test_regras_cultura_motor.py`. Alterar o backend é reintroduzir um
   bug já corrigido.
3. **Não `git add -A`.** Quatro sessões bateram neste ponto; uma commitou por
   cima de 158 ficheiros alheios. Use caminhos explícitos.
4. **Não usar `edit` acima de ~50 KB.** Reescreve o ficheiro e pode introduzir
   linha em branco em cada linha. Para ficheiros grandes, `git cat-file blob`
   - cabeçalho + `write_bytes`.
5. **Não escrever caracteres CJK em comentários.** Quatro sessões o fizeram, e
   já há um ficheiro de teste corrompido na árvore por isso. Escreva em
   português ou em ASCII.
6. **Não aceitar a baseline de volume** (`tests/estudo_volume.py --aceitar`).
   Isso fixa o crescimento do pipeline numa baseline. Decisão do dono.
7. **Não decidir §3.1 nem §3.2.** `login.css` e os 273 MB são do dono.

### 5.3 Regras que já provaram custo

| Regra                                                                                     | Origem                                        |
| ----------------------------------------------------------------------------------------- | --------------------------------------------- |
| Ler antes de escrever; se o mtime é de outra sessão nos últimos 30 min, mudar de ficheiro | 6 incidentes de coordenação na `ESTADO.md` §5 |
| `git add` com caminhos explícitos                                                         | 158 ficheiros alheios num commit              |
| Nada de `edit` em ficheiro grande                                                         | 26.606 → 47.633 linhas, uma vez               |
| Varrer bytes em ficheiros que escreveste                                                  | 4 caracteres CJK introduzidos                 |
| Ler o `git diff --cached --name-only` antes de comitar                                    | Índice partilhado                             |
| Uma sessão = um slot do `console.md`                                                      | `console.md` tem slots `s1`–`s11` para isto   |

---

## 6. O NÚMERO QUE MANDA

Duas medidas, e só duas:

1. **O primeiro minuto.** Tempo até o produtor ver algo que reconheça como
   dele, sem digitar. Hoje: não chega ao ecrã.
2. **A taxa de `fonte_dado` nas escritas.** Quantas linhas na base de dados
   declaram a sua origem. Meta: 100%. Hoje: não medido, e
   `operario.py:68-112` escreve sem declarar.

Tudo o resto — número de widgets, de culturas, de rotas, de linhas de
documentação — é **métrica de vaidade**, e esta sessão mediu o que acontece
quando uma delas vira o alvo: 273 MB de repetição com URLs que dão 404.

---

_Escrito por Space Bunny (Coordenador), 04/10/2026. Corrigir com `append`, nunca
sobrescrever — ver `ESTADO.md` §5, incidente 1._
