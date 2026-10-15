# Comparativo 100 × 50 — a análise, e o que ela diz contra o Ampliagro

**Agente:** 9 · **Data:** 2026-10-05 · revisto depois da verificação por fetch, **da campanha em massa** e **da auditoria semântica dos `E`**
**Planilha:** [`comparativo-100x50.xlsx`](comparativo-100x50.xlsx) · 7 folhas
**Reprodução:** `verificar_evidencia.py` (busca e prova) · `tests/test_comparativo_100x50.py` (trava)

---

## 0. O que mudou nesta revisão

A primeira versão marcava células `S` a partir de **snippets de pesquisa**. Esta revisão **busca cada página e confirma a citação**. O resultado não foicosmético — o verificador **reprovou 6 das 29** e a tabela ficou diferente:

| Célula | O que eu escrevi | O que a página diz |
|---|---|---|
| upCampo F16 | "não faz contabilidade" | A frase é *"não faz **é** contabilidade"* — o `é` partia a citação |
| Carbonova G05 | "MRV" | A página **nunca escreve "MRV"**. Escreve "Inventário de Emissões", "Escopos 1, 2 e 3" |
| CO2Token G05 | "ERC-20" | A página devolve **9 caracteres**. É SPA — sem execução de JavaScript não há citação possível |
| Lucro Rural | NCM, presumido, DRE | Não estão na homepage. Estão em `/produtor` |
| Aegro F11 | fluxo de caixa | Não está em `/solucoes/gestao-rural/` (0 ocorrências). Está na homepage (3) |
| upCampo O05 | cronograma de atividades | **"cronograma" e "planej" dão 0 ocorrências.** A capacidade não está provada |

**Cada uma delas era um `S` que eu publicaria como facto.** Um snippet de busca é um resumo do motor, não a fonte.

---

## 1. O caso Fluere — e porque a evidência mais forte não passa por fetch

O `§5` (Carbono) do `docs/sistema/9.md` foi construído sobre `fluere.ag`. Quando o verificador a buscou, **devolveu 404.** E `fluere.com.br` é outra coisa: uma empresa de **tiras nasais**.

Fui atrás. A empresa existe, e a prova é **melhor** do que a página do fornecedor:

> **SLC Agrícola** — companhia **listada** — comunica: *"a maior operação automatizada de mensuração de carbono (GEE) já realizada no agronegócio brasileiro. A ação abrangeu **736 mil hectares** e gerou dados auditáveis, compatíveis com os protocolos internacionais **GHG Protocol** e FLAG. Desenvolvido em colaboração com a **Fluere**, deeptech da Cerensa."*

Mais duas fontes independentes: o `fluere.ag/sobre` diz que nasceu em 2024 como **spin-off da Cerensa**; e o LinkedIn da empresa descreve *"inventário baseado no GHG Protocol adaptado ao agro"*.

**Isto vale umaermark nova.** Chamei-lhe `D` — **documentado por terceiro**. E não é um `F` fraco: é a companhia a confirmar numa comunicação de bolsa, não o fornecedor a prometer na própria página. Numa tabela de concorrentes, um comunicado de bolsa vale **mais** do que o site do fornecedor.

O que **não** consegui confirmar, e desceu para `?`: *"resultados em 30–60 dias"* e a validação pela UFSM/FAPESP. Estavam no meu `9.md` §5 e **não têm fonte que eu consiga provar.** Devem sair de lá.

---

## 2. As marcas, e o que cada uma custa

| Marca | Significado | N.º |
|---|---|---|
| **F** | **Provado por fetch.** A citação foi buscada e está na página | **49** |
| **D** | Documentado por terceiro. A máquina não alcança a fonte | **1** |
| **?** | Sem prova. **Não é zero** | **4 950** |
| **C** | Ampliagro confirmado no código, com `ficheiro:linha` | **20** |
| **E** | Ampliagro enfraquecido — campo, constante ou nome de view | **16** |
| **N** | Ampliagro não tem | **14** |

E há um quarto estado que **não aparece na tabela** e é o mais importante:

> **REJEITADO — 0.** As seis células que o verificador reprovou foram corrigidas ou caíram. Nenhuma foi "ajustada até passar".

---

## 3. O teste que trava tudo isto

`tests/test_comparativo_100x50.py` — **8 testes, verdes com a rede ligada**:

1. Confirma que a matriz tem 100 × 50 = 5 000 células
2. Confirma que toda célula do registo tem URL, fragmento e motivo
3. Confirma que nenhuma queda está silenciosa
4. Confirma que os 50 veredictos do Ampliagro apontam para ficheiro e linha que **existem**
5. **Confirma que nenhuma célula `F` é rejeitada** pela página
6. **Canário:** a contagem de provados não pode descer

O canário funcionou. Disparou quando removi as duas células de `F16` — que eram citações com o texto certo na coluna errada. Uma verificação que só conta números não apanha isto; o canário apanha, porque a contagem desce.

**Sem rede, os testes 1–4 correm e os 5–6 dão `skip` com o motivo escrito.** Nunca passam em silêncio: um teste que falha quando a net cai é um teste que a equipa aprende a ignorar.

---

## 4. O que a verificação mudou nas conclusões

**Onde estamos sozinhos — 9 de 50.** Saiu `F12` (OFX, que a Aegro tem) e entrou `F06` (NCM, extração por OCR). E o `M07` — IA no dispositivo — continua `E`, não `C`.

**Onde perdemos — 8 de 50**, não 9. Saiu `L05` (contratos de safra): AgriChain e SAP têm, mas **não tenho fonte lida**. Fica em "ninguém provado".

| ID | Dimensão | Quem tem, com citação provada |
|---|---|---|
| F15 | Benchmark de mercado | Aegro — *"Aegro Compare Safras"*, plano Premium |
| F14 | Orçado x realizado | Aegro — *"planejado vs. realizado"* |
| F17 | Projeção de IR | Lucro Rural — *"imposto de renda"*, 15 ocorrências |
| M02/M03 | Deere, Stara, FieldView, Solinftec | Aegro **e** upCampo |
| X06 | WhatsApp | Aegro — *"Aegrozap"*; upCampo — *"WhatsApp"*, 15 ocorrências |
| G05 | Carbono | Fluere (por comunicado de bolsa), Carbonova |

**Onde estamos sozinhos e sobreviveu à verificação:**

| ID | Porquê é difícil de copiar |
|---|---|
| **G01** | `app/validators.py:17` — cinco estados de proveniência. Um ERP precisa de mostrar o número |
| **G02** | `app/models/ia.py:58` — 13 campos por execução de IA. Numa Nexml isto é add-on |
| **G03** | `app/middleware.py:41` — fecha a porta antes do DRF |
| **G04** | Multi-propriedade e multi-safra, sem custo por acesso |
| **F06** | NCM por OCR — a Aegro resolve por NF-e; nós por leitura. Caminho diferente |

---

## 5. As correções ao `9.md` que esta revisão obriga

O `docs/sistema/9.md` §5 (Carbono) tem afirmações que **não sobreviveram à verificação**:

| Afirmação no `9.md` | Estado real |
|---|---|
| "Fluere — resultados em 30–60 dias" | **Sem prova.** Descer a `?` |
| "Validado com UFSM, FAPESP, CNPq, SLC Agrícola" | **Só a SLC se confirma**, e por comunicação de bolsa — não pela Fluere |
| "Carbonova: Verra, Gold Standard, GCC" | **Não verificável.** A página prova "Inventário de Emissões", "Escopos 1, 2 e 3", "GEE" |

O que **se confirma** é mais forte do que o que eu tinha escrito: **736 mil hectares medidos** pela SLC, com GHG Protocol e FLAG.

---

## 6. O veredicto final

**O Ampliagro tem 20 colunas confirmadas de 50. O Aegro tem 23 confirmadas — e cada uma com a citação buscada e confirmada hoje.**

A diferença não está no número. Está em **onde** cada lista é fraca:

- O Aegro é forte onde o produtor **decide**: custo por talhão, orçado x realizado, fotos georreferenciadas, telemetria, benchmark.
- O Ampliagro é forte onde o produtor **não decide**: proveniência, auditoria de IA, isolamento.

**E há uma coisa que a verificação mudou e que vale mais que o resto:** as duas listas são desigualmente honestas. A do Ampliagro tem `ficheiro:linha` e 20 de 50 são `C` — os outros 30 estão marcados como `E` ou `N`, com o motivo. A dos concorrentes tem 49 de 5 000 com citação buscada, e as outras 4 951 são `?`.

**Isso não faz o Ampliagro melhor. Faz a comparaçãoAuditável** — e uma comparação auditável é a única que sobrevive a um Gathering de investment, a umadue diligence ou a um produtor que abre o separador e pergunta "onde está isso?".

O ficheiro de Cache (`.cache_fontes.json`) guarda o HTML de cada página buscada. **A prova é reexecutável, não uma memória.**

---

## 9. A campanha em massa — 52 células comprovadas, e três conclusões partidas

Enquanto só procurava por produto, o registo tinha 52 células. Esta rodada
perguntou o inverso: das 100 páginas alcançáveis, **quais dims podem
comprovar-se e eu ainda não comprovei?**

`descobrir_em_massa.py` → 53 páginas alcançáveis × 50 colunas = **375
candidatos crus**. Desses, 122 passaram o filtro de força. **22 entraram no
registo, todas verificadas uma a uma antes de escrever.** As outras 100 são
majoritariamente `field log`, `cash flow`, `map`, `ERP` numa landing page:
verdadeiras, mas não distintivas — provam que o produto existe, não que seja
melhor. Uma tabela de 5 000 células onde tudo é `F` deixa de ser prova.

### 9.1 O que mudou nas conclusões

**Três colunas deixaram de estar vazias.** A versão anterior dizia "ninguém
tem evidência" e estava errada:

| Coluna | Antes | Agora | Fonte |
|---|---|---|---|
| **F05** Reforma Tributária | ninguém | **Senior, TOTVS Protheus** (5x) | a transição IBS/CBS é argumento de venda |
| **F10** Contas a pagar | ninguém | **Aegro, Sage X3, SYSPRO** | backoffice de ERP |
| **L05** Contratos de safra | ninguém | **Bushel Farm** (3x) | *"grain contract"* — é o negócio da Bushel |

As lacunas do Ampliagro passaram de **9 para 11** — número desta rodada. A **§10** leva-as a **14**, porque a auditoria dos `E` encontrou mais três capacidades que eu tinha marcado com evidência falsa (certificado A1, folha de pagamento, conectores). F05 e F10 não são um detalhe: são exactamente onde o Ampliagro é mais fraco — o ERP já tem conformidade fiscal pronta.

**Uma exclusividade minha caiu.** O `G02` (auditoria de IA) aparecia como
vantagem exclusiva do Ampliagro. A **Datacor tem `audit trail`** — a palavra,
pelo menos. Mantive `G01` (proveniência como *tipo em código*) como
diferenciado, porque log de alteração e tipagem de origem não são a mesma
coisa, mas a distinção é minha e está anotada na nota da célula.

**A Carbonova tem IA na borda.** `"edge AI"` (3x) — o mesmo sítio onde o
Ampiagro põe o WebLLM. É carbono, não agro, mas a afirmação "somos os únicos
com IA local" já não é verificável como exclusivity.

### 9.2 Três que eu desci por cautela

O verificador confirma que a frase **está** na página. O que a página diz não
basta para a coluna. Marquei-as `P` — um estado novo:

| Célula | A página diz | A coluna pede | Estado |
|---|---|---|---|
| TOTVS Protheus F16 | `financial services` | crédito rural | `P` |
| Aptean F16 | `financial services` | crédito rural | `P` |
| Datacor G01 | `audit trail` | proveniência tipada | `P` |

`P` **não desce a `?`**: um quase-é é um achado — a Datacor está a trabalhar
nisto, e isso é informação de mercado. Uma ausência não é. Mas também não
sobe a `F`, porque a capacidade não está provada. E **não conta** para o
canário: 69 capacidades provadas, não 72.

### 9.3 Dois bugs meus, encontrados pela campanha

**O verificador contava por substring.** `"OTA"` casava dentro de `"TOTAL"`
e `"ROTACAO"`; `"API"` dentro de `"capital"`; `"map"` dentro de `"roadmap"`.
Numa tabela de 5 000 células, um falso positivo por substring é um `S` falso.
Agora fragmentos com menos de 4 caracteres exigem fronteira de palavra
(10/10 provas). Reverifiquei as 52 anteriores com a correcção: as 49
sobreviveram — nenhuma era falso positivo.

**As células `F` e `D` pintavam-se a cinzento.** `MARCA_COR` não tinha
entradas para elas, e caíam no fallback `.get(marca, CINZA)` — a mesma cor do
`?`. Uma célula provada aparecer com a cor de "não verifiquei isto" é pior do
que não a pintar. Corrigido, e `F`/`D`/`P` entraram na legenda.

### 9.4 A folha deixou de poder divergir em silêncio

`test_comparativo_100x50.py` validava o registo. Não validava o `.xlsx` — o
que o leitor abre. Podia haver 69 no registo e 52 na folha sem ninguém dar por
isso. `tests/test_planilha_consistente.py` compara as **5 000 células** e
falha se uma divergir.

**Estado:** 10/10 com rede, 8 + 2 skips sem. 68 `F` + 1 `D` = **69
capacidades provadas** · 3 `P` · 4 928 `?`.

---

## 10. A auditoria dos 16 `E` — o `E` era enchimento

Este é o achado mais importante do trabalho, e só apareceu porque alguém leu
as linhas em vez de as contar.

O teste `test_nenhum_veredicto_aponta_para_ficheiro_inexistente` garantia que
cada `E` apontava para uma linha que **existe**. Não que a linha
**implementasse** a capacidade. Pensei que isso era pouco e era bastante.

### 10.1 O que as 16 referências eram

| Onde apontei | O que a linha é, na verdade |
|---|---|
| `financeiro.py:327` | docstring que menciona SEFAZ |
| `nfe.py:51` | **docstring a dizer "NÃO chama a SEFAZ"** |
| `custos.py:422` | a docstring da acção (o código começa na 427) |
| `hierarquia.py:82` e `:121` | entradas de um dicionário de permissões |
| `serializers.py:969` | **uma linha em branco** |
| `intents3.py:165` | `"drone": "DRONE"` num mapeamento de tipos |
| `contrato.py:143` | docstring com `brinco` de exemplo |
| `seed_muzambinho_demo.py:111` | **uma string em dados de demo** |
| `audit.py:19` | um `import` numa lista de registo |
| `urls.py:106` e `:75` | imports |
| `amplia.js:329` | um toast que diz "estás offline" |
| `alerta-feed.js:21` | comentário a dizer que esse ficheiro **não** infere |

Nenhuma delas implementa uma capacidade. Uma prova o contrário.

### 10.2 O que fiz, e porque não despromovi logo para `N`

Despromover para `N` também é uma afirmação que precisa de prova. Se a
capacidade existe e eu apontei para a linha errada, marcar `N` seria um novo
mentiro — só que mais difícil de detectar, porque não cites nada.

Por isso a ordem foi: **procurar a implementação real primeiro.**

- `pkcs12`, `dsig`, `xmldsig`: **0 ocorrências** em toda a `app` → F04 é mesmo `N`
- `class FolhaPagamento`, `provento`, `salario_base`, `fgts`, `liquido_salarial`: **0** → F18 é `N`
- `armazenagem`, `classificacao_café`, `cafe_colheita`: **0** → L04 é `N`
- `erp_externo.py` no seu próprio código: *"Não há SAP, Protheus ou JBS ligado ao Ampliagro"* → X02 é `N`
- "drone" só é um tipo de máquina; o imagery é Sentinel-2 → O08 é `N`

E para as outras, a capacidade **era real** — eu tinha apontado para o sítio
errado. Offline, fotos georreferenciadas, telemetria, IA no dispositivo,
exportação, conciliação OFX e NDVI têm implementação **e teste que passa**
(83 testes verdes).

### 10.3 A âncora passou a ser o teste, quando a capacidade é comportamento

Dizer "existe uma linha em `test_caderno_fotos.py`" é mais fraco do que dizer
"há um teste que grava uma foto e confirma a latitude". Comportamento prova-se
executando. Três âncoras passaram a ser o teste, com a linha da asserção.

### 10.4 O resultado, e porque parece bom e é mau

| | antes | depois |
|---|---|---|
| `C` confirmado | 20 | **30** |
| `E` enfraquecido | 16 | **1** |
| `N` ausente | 14 | **19** |

**(continua na §11: o guard escrito depois desta apanhou mais 6 âncoras `C` com a mesma doença e duas desceram de facto. O estado final é 28 `C` / 3 `E` / 19 `N`.)**

O `C` subiu porque encontrei implementações reais. O `N` **também** subiu, e é
esse o número honesto: o Ampliagro não tem 19 das 50 capacidades.

O `E` colapsou de 16 para 1. Uma categoria que valia um terço da coluna e
servia paratodo: segura o que nao era `C` nem `N` de verdade.

Na análise, as exclusivas caíram de **6 para 4** (drones e beneficiamento
eram falsos) e as lacunas cresceram de **11 para 14** (A1, folha de pagamento e
conectores apareceram onde eu tinha markado `E`).

---

## 11. O guard que impede a repetição — e o que ele apanhou sozinho

Escrever §10 deixava a tabela mais honesta, mas não a impedia de voltar a
mentir. O teste garantia que cada `C` apontava para uma linha existente; uma
docstring existe. Escrevi `tests/test_ancora_tem_codigo.py` para fechar essa
porta, e ele **apanhou 6 offenders sozinho** — 4 dos quais eram `C` de antes da
minha auditoria, com a mesma doença que os `E`:

| Célula | Âncora antiga | O que era |
|---|---|---|
| F11 | `financial.py:30` | o `import` de `projetar_fluxo_caixa` |
| O01 | `caderno.py:37` | o `import` de `NotaCampo` |
| M08 | `coerencia.py:99` | um `import` dentro de outra função |
| M07 | `proativo-local.js:83` | um `@param` de JSDoc |
| F06 | `bridge.py:84` | uma entrada de dicionário |
| F08 | `lcdpr_export.py:42` | a chave `"porque"` de um dicionário |

Auditei a coluna `E` e achei que tinha tratado o problema. A coluna `C` tinha a
mesma doença — e ninguém tinha olhado, porque `C` é onde se olha menos.

### 11.1 Duas desceram mesmo

Não chega trocar a linha. Li as duas:

- **F06 (NCM/TIPI)** desceu de `C` para `E`. O sistema **transporta** o NCM
  do XML para o rascunho (`"ncm": _txt(prod, "NCM")`) — não classifica
  fiscalmente. Trazer o código não é TIPI.
- **F08 (Presumido × Resultado)** desceu de `C` para `E`. O registo 0010 é
  escrito, mas com `FORMA_APURACAO_LIVRO_CAIXA` **hardcoded**. As duas formas
  estão definidas no código e o produtor **não escolhe** — o próprio comentário
  diz que *"trocar isto é uma decisão de configuração, não de código"*. A
  coluna é a escolha entre regimes, e a escolha não existe.

### 11.2 O mapa `âncora → teste`

Nas 3 células ancoradas em ficheiro de teste eu escrevi, no documento, que se
apoiam em "83 testes verdes". Esse número foi medido **numa corrida** — nada o
guardava. `tests/test_ancora_tem_teste.py` garante que o mapa
`âncora → teste` está completo nos dois sentidos: uma `C` nova apontada para um
teste novo falha o guard até o teste entrar na lista, e entrar na lista
significa que a suite o corre.

### 11.3 Balanço final

| | §9 | §10 | agora |
|---|---|---|---|
| `C` | 20 | 30 | **28** |
| `E` | 16 | 1 | **3** |
| `N` | 14 | 19 | **19** |

28 confirmados, 3 enfraquecidos, 19 ausentes. Cada `C` tem uma linha de código
por trás, e o guard verifica isso com `ast` — não por regex, porque três aspas
pode ser um delimitador ou o conteúdo de uma string, e só a árvore sabe.

---

## 12. O comité — e o que ele me refutou

Escrevi tudo o que está acima sem nunca correr o comité. Isso viola a regra do
papel: o comitê **opina**, os scanners **constatam**, e euusei so scanners. A
correção não foi um achado meu — foi o comitê a discordar de mim.

### 12.1 Duas coisas que correr o comitê me ensinou sobre a própria ferramenta

**O motor trunca cada ficheiro a 6000 caracteres.** `lcdpr_layout.py` tem
19 180. A primeira consulta mandou 8 ficheiros e o comitê viu cabeças — as
minhas afirmações estão nas linhas 100–500. Não viu nada do que tinha de
julgar. Tive de **colar o código na pergunta**. Um comitê que julga sem ver
não é um comitê: é um-ruído com opinions.

**Só 2 das 10 lentes responderam.** Três gastaram 4 506 tokens a raciocinar e
acabaram sem escrever (`finish=length`). Uma respondeu "NENHUM DEFEITO" — a
lente de legibilidade, à qual não foi perguntado nada sobre defeitos.
**Cobertura real: 1 lente com julgamento.** Isto é lacuna declarada, não
"nada foi encontrado".

### 12.2 O que o comitê refutou

A lente de segurança, sobre F08:

> **REFUTADO** — `lcdpr_export.py:507-519`: o `0010` é sempre `1`; falta
> escolha do regime, logo deveria ser `NAO TEM`, não `ENFRAQUECIDO`.

**Tinha razão, e devia ter visto antes.** A minha própria regra diz que uma
constante não é a capacidade. Apliquei-a ao F06 (extrai NCM mas não classifica
TIPI → `E`) e não a apliquei ao F08, onde o que se emite é precisamente
`FORMA_APURACAO_LIVRO_CAIXA`, uma constante. A diferença que sobrevive:

- **F06** — o produtor tem dados a entrar e eles são lidos e guardados. Falta
  a classificação. Capacidade parcial a funcionar → `E`.
- **F08** — não há nada a entrar. O produtor não tem palavra no resultado. É
  um valor fixo num template de saída. Capacidade inexistente com formato → `N`.

Emitir uma constante não é capacidade parcial. **F08 desceu para `N`.**

As outras seis foram corroboradas sem divergência.

### 12.3 Um erro meu que o comitê não viu

A nota do **L04** dizia que a única ocorrência de "beneficiamento" estava em
dados de demo. **Falso.** `grep` por todo o `app` devolve duas, ambas em
`app/models/equipe.py:56` e `:233`, como **cargo de trabalhador** —
`"Operador de Beneficiamento"`, mapeado para a área `ESTOQUE`.

A conclusão (`N`) mantém-se: um cargo não é um registo agrícola, e
`armazenagem` dá **zero ocorrências**. Mas o motivo que eu tinha escrito
estava errado — e um motivo errado é pior do que um motivo ausente, porque
convence quem lê.

### 12.4 O custo desta secção

Cortar o ficheiro por fatias de caracteres, a meio de um dicionário, comeu as
entradas `L05` e `M01`. Reconstrí-as — mas **verificando o código, não
recordando**: `torrente`, `torrentes`, `safra_torrente` e `contrato_safra` dão
zero ocorrências (por isso `L05 = N`), e `telemetria` tem 170 ocorrências em
código de execução (por isso `M01 = C`). As notas de ambas dizem que foram
reconstruídas. Um registo que não sabe o que deixou de saber devia dizer isso.

### 12.5 Balanço depois do comitê

| | §11 | agora |
|---|---|---|
| `C` confirmado | 28 | **28** |
| `E` enfraquecido | 3 | **2** |
| `N` ausente | 19 | **20** |

**28 confirmados, 2 enfraquecidos, 20 ausentes.** E um deles — o F08 — desceu
porque uma lente disse que eu estava a ser generoso comigo próprio.
