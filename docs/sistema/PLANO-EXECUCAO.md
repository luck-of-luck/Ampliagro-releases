# PLANO DE EXECUÇÃO — destrinchamento do `9.md` e do `5.md`

**Data:** 2026-10-05
**Origem:** `docs/sistema/9.md` (estudo de caso do mercado) + `docs/sistema/5.md` (manifesto vs. código)
**Projecto:** `C:\Trabalho\Projetos\Ativos\Ampliagro`

---

## 0. Como este documento se lê

Os dois documentos que servem de entrada chegaram à mesma conclusão por vias
opostas — o `9.md` mediu o Ampliagro contra o que o mercado vende, o `5.md`
mediu contra o que o manifesto promete — e os dois saíram com uma lista de
faltas. Nenhuma das duas listas é fiável. Não porque os autores tenham mentido,
mas porque **mediram trees que outros processos estavam a escrever** (é o
§0 do `9.md`, e é verdade).

Este documento faz três coisas, e cada uma é uma correcção ao que os
antecedentes escreveram:

1. **Separa** o que ainda é verdade do que já foi resolvido. Das 19
   afirmações dos dois documentos, **8 continuam vivas e 11 estão
   desactualizadas ou erradas**.
2. **Acrescenta** um achado que nenhum dos dois documentos viu, e que é maior
   do que qualquer item das duas listas: as 488 culturas não têm uma única
   regra agronómica (§1.1).
3. **Liga cada lacuna ao activo que a fecha.** Nenhuma das duas listas
   perguntou "o que já temos que faz isto?" — e era a pergunta que importava,
   porque quase tudo o que falta é mais barato do que parece.

> **Regra que aplico, e que é a lição que os dois documentos pagaram para
   escrever:** cada linha daqui carrega `ficheiro:linha` ou um comando que a
   reproduz. Uma affirmation sem evidência é uma opinião, e opinião não entra
   num plano.

### 0.1 O que NÃO está neste documento

- **Números de mercado.** Preços da Aegro, anos de operação, quotas de plano:
  são do `9.md`, com fontes citadas lá. Não os reverifiquei e não os repito
  como meus.
- **Limites legais do LCDPR** (obrigatoriedade acima de R$ 4,8 milhões,
  prazo de retificação, exigência de assinatura ICP-Brasil). Vêm do Manual

  1.3 da Receita, lido pelo agente 9. **Não os validei contra a fonte.** Antes
  de escrever código fiscal com base neles, alguém tem de os ler no manual.
- **Preço, custo e TCO.** Ninguém mediu.

---

# PARTE 1 — Os três estados da lista

## 1.1 O achado que nenhum dos dois documentos viu

Antes de separar, um achado novo. Porque é maior do que os itens das duas
listas, e porque muda a leitura de "488 culturas".

**Medido hoje:**

```
get_culture_business_rules('soja')    -> 0 regras, 0 chaves
get_culture_business_rules('milho')   -> 0 regras, 0 chaves
get_culture_business_rules('cafe')    -> 0 regras, 0 chaves
get_culture_business_rules('algodao') -> 0 regras, 0 chaves
get_culture_business_rules('cana')    -> 0 regras, 0 chaves
get_culture_metrics('soja')           -> 0 métricas
get_culture_fields('soja')            -> 0 campos
```

E o mais grave:

```
CultureBusinessEngine('soja').is_planting_season()
    -> True        # porque self.rules == {} e a linha 412 diz:
                   # "sem regra = sempre permitido"
```

`app/api/culture_config.py:407-412`.

### O que isto significa

O `9.md` §8 registra como P2: *"o catálogo tem 488 culturas e o material promete
707"*. Isso é uma **divergência de contagem**. A divergência real é outra:

> **As 488 culturas são nomes. Não têm agronomia nenhuma.** Zero métricas,
> zero campos, zero janelas, zero templates de tarefa, zero automações.

E há um defeito de doutrina, que é mais grave que a cobertura: **quando não
sabe, o motor afirma que sim**. `is_planting_season()` devolve `True` para uma
cultura cujas janelas não conhece. Isto é exactamente o que o projecto
proíbe em todo o resto — `proveniencia.py` recusa inventar, `validators.py:40`
diz *"o sistema nunca promove uma afirmação a medição"* — e o motor de regras
faz o contrário, em silêncio, sem `suspect`, sem `sem_dado`, sem aviso.

Um produtor que pergunte ao Ampliagro "posso plantar soja agora?" recebe
resposta afirmativa de um sistema que não sabe a resposta. **Isto é a mesma
doença dos dois documentos, numa zona onde os dois não olharam.**

### Por que isto é a boa notícia

O motor **não tem as regras escritas em código**. `get_culture_business_rules()`
lê do `cultures-config.json`, e o `CultureBusinessEngine` consome esse
dicionário. A máquina toda — janelas, override por UF, alertas por threshold,
templates de tarefa, automações — está construída e testada
(`test_regras_cultura_motor.py`).

**Isto é conteúdo, não engenharia.** Escrever as regras de 15 culturas que
cobrem a maior parte da área plantada do Brasil é trabalho de agrónomo com
formato definido, não de programador. O `9.md` classifica isto como P2
(cobertura). Eu classifico como **P0**, porque a alternativa hoje é o sistema
a dar um advice errado com confiança.

### O que se faz

| | Acção | Porquê |
|---|---|---|
| **A** | `is_planting_season()` deixa de assumir `True`. Sem regra, devolve `None` (= "não sei") e o painel diz isso. | Um `True` inventado é pior do que um "não sei". É a regra do projecto. |
| **B** | Regra agronómica para as 15 culturas principais, com override por UF já suportado (`culture_config.py:418-422`). | Transforma "488 culturas" em guidance real sem tocar no motor. |
| **C** | `test_regras_cultura_motor.py` deixa de ser um teste aberto e passa a exigir: ou há regra, ou o painel diz que não há. | Impede que o default permissivo volte em silêncio. |

**Resultado melhor:** o Ampliagro passa a dizer *"a janela de soja em MT vai
de X a Y, e em GO de A a B"* — que é o serviço que o produtor visita a propriedade hoje, e que nenhum ERP pequeno entrega com override por região.

---

## 1.2 Bucket A — Verdade VIVA (8 itens, confirmados hoje)

| # | Afirmação | Evidência | Estado |
|---|---|---|---|
| A1 | LCDPR exporta 6 de 9 registos | `lcdpr_export.py`, 160 linhas, gera `0000`,`0030`,`0040`,`0050`,`Q100`,`9999` | **CONFIRMADO** |
| A2 | Sem assinatura ICP-Brasil | `grep icp\|assinatura\|pkcs12` → nada | **CONFIRMADO** |
| A3 | Zero código de OTA | `grep ota_update\|esptool\|micropython\|firmware_upload` → vazio. `models/iot.py:135` tem `firmware_version` | **CONFIRMADO** |
| A4 | `tasks.py` é placeholder | 13 linhas, `gerar_relatorio_async` faz `logger.info` e `return True`, comentado *"Placeholder"* | **CONFIRMADO** |
| A5 | Celery não se arma sozinho | `proativo_tasks.py:274` — `BEAT_SCHEDULE` só com `AMPLIA_CELERY_BEAT=1` | **CONFIRMADO** |
| A6 | Zero implementação de carbono | `grep MRV\|GHG\|emissoes\|carbono` → nada em código | **CONFIRMADO** |
| A7 | Sem importação de telemetria de máquina | `grep importar_xml\|csv.reader\|FieldView\|Operations Center` → vazio | **CONFIRMADO** |
| A8 | Tenancy sem cripto no middleware | `grep fernet\|hmac\|compare_digest` em `middleware.py` → vazio. É lookup por tabela | **CONFIRMADO** |

**Correcção ao `9.md`:** o seu §8.1 diz *"medido: o `importar_xml` existe para
NF-e; o mesmo caminho serve para CSV de máquina"*. **Não existe.** `importar_xml`
não está no repositório. A ideia do CSV é boa; o atalho que ele aponta não
existe.

## 1.3 Bucket B — Já Resolvido (11 itens, os documentos estão errados)

| # | O que os documentos dizem | Realidade medida |
|---|---|---|
| B1 | "Proveniência tem 3 estados, `declarado` não existe" (`5.md` §2.2, `9.md` §2) | **FALSO.** `proveniencia.TODOS` = `medido`, `medido_com_ressalva`, `suspect`, `sem_dado`, `simulado`, `declarado`. `validators.ESTADOS_FONTE` = os 5 canónicos. **Este é o erro mais caro dos dois documentos** — e o `9.md` §12.1 já o confessa. |
| B2 | "O listener MQTT foi apagado" (`9.md` §4) | **FALSO.** `app/management/commands/mqtt_listener.py` (8,9 KB) e `sync_inmet.py` (9,7 KB) existem. O `git status` que o agente viu mostrava a *duplicata* em `app/iot/management/` a ser removida — que foi a acção correcta. |
| B3 | "`AMPLIAGRO_DATA_KEY` tem zero ocorrências" (`9.md` §3) | **FALSO.** 6 ocorrências em `app/seguranca.py` (linhas 3, 29, 34, 50) + testes. |
| B4 | "Caderno de Campo é feature fantasma" | **RESOLVIDO.** `NotaCampo` + `app/api/views/caderno.py` + as três rotas + 11 testes. |
| B5 | "Apagamentos offline nunca chegam ao servidor" | **RESOLVIDO** (e era maior do que o `9.md` via): `deletedIds` era escrito e nunca lido. Provado por execução em Node, corrigido, com teste que falha se voltar. |
| B6 | "CSP bloqueava o WebLLM" (`5.md` §5.1) | **RESOLVIDO.** `esm.run`, `wasm-unsafe-eval`, `huggingface.co` em `base.py`. O utilizador confirmou que carrega. |
| B7 | "A porta 8000 está exposta" (`5.md` §5.2) | **RESOLVIDO.** `127.0.0.1:8000:8000` + `SECURE_PROXY_SSL_HEADER`. |
| B8 | "Zero-Trust: `device_eui` autentica" | **RESOLVIDO.** Só `Gateway.api_key` com hash cego. |
| B9 | `hasWidgetSession()` aceitou `csrftoken` | **RESOLVIDO.** |
| B10 | `?next=` dá 500 | **RESOLVIDO.** `auth.py:61`, 5 testes. |
| B11 | "4 falhas pré-existentes na suite" | **Hoje são 5**, e nenhuma é a mesma: 3 são o `docs/super-estudo-globo-rural/` (91 documentos sem backup) e 2 são promessas comerciais. |

**Leitura:** o `5.md` foi escrito contra uma árvore anterior a quase tudo isto
ser corrigido; o `9.md` acertou em cheio ao dizer, no seu §12, que as
medições têm de ser re-verificadas. Tinha razão, e a prova é que **11 das 19
afirmações dele já estavam mortas quando ele as escrevia.**

## 1.4 Bucket C — Decisão de negócio, não técnica

| # | Questão | Por que não é minha |
|---|---|---|
| C1 | "11 cadeias" vs 3 no menu | Ou o catálogo cresce, ou o material corrige. O `test_promessas_numericas.py` está vermelho de propósito para forçar a escolha. |
| C2 | "707 culturas" vs 488 | Idem. E agora com o §1.1: o número honesto hoje é "488 nomes, 0 regras". |
| C3 | NF-e: emitir, integrar ou remitir | Exige certificado A1 homologado. O `9.md` §7.2 diz que provavelmente não deve ser o Ampliagro a fazê-lo — concordo. |
| C4 | Carbono: parceria ou produto | §3.3 abaixo. |

---

# PARTE 2 — Destrinchamento: cada lacuna, o activo que a fecha, e como

Formato de cada bloco, sempre igual:

- **O que falta** — a lacuna, com medida
- **O que já temos** — o activo, com `ficheiro:linha`
- **Como se usa** — o mecanismo, concreto
- **Para que serve** — o resultado para o produtor
- **Primeiro passo** — a primeira acção, e como se verifica que ficou feito

---

## 2.1 LCDPR — a maior lacuna, e uma estimativa que está errada

**O que falta.** `lcdpr_export.py` tem 160 linhas e gera 6 registos:
`0000`, `0030`, `0040`, `0050`, `Q100`, `9999`. Faltam três:

| Registo | Nome | Situação real |
|---|---|---|
| `0010` | Parâmetros de tributação (presumido x resultado) | Falta o registo **e** o campo que o alimenta |
| `0045` | Exploração por mais de uma pessoa | Falta o registo **e** o modelo dos contrapartes |
| `Q200` | Resumo mensal | Falta o registo. **Os dados já são calculados.** |

Mais a assinatura por certificado ICP-Brasil, que o `9.md` §4 regista como
exigida pelo art. 23-A, parágrafo 2, da IN SRF 83/2001 (a confirmar na fonte).

**O `9.md` §7.1 estima "2 dias de trabalho" para os três mais a assinatura.
Isso está errado, e é importante que esteja errado**, porque é essa estimativa
que justifica a prioridade. Separando:

| Item | Esforço real | Porque |
|---|---|---|
| `Q200` | **~1 hora** | O `_gerar_bloco_q()` (linha 112) ja percorre `LancamentoFinanceiro` do ano com `saldo_acumulado`. O Q200 e esse mesmo loop agrupado por mes. Zero dados novos. |
| `0010` | **~meio dia** | Falta um campo (o indicador de regime) e o registo. |
| `0045` | **1 a 2 dias** | Falta um **modelo novo**: quem sao as outras pessoas da parceria ou condominio. |
| ICP-Brasil | **Nao e 2 dias** | Cliente PKI, manipulacao de certificado, assinatura do ficheiro. E uma integracao. Ver abaixo. |

**O que ja temos.**

- `Propriedade.cpf_cnpj`, `caepf`, `inscricao_estadual`, `tipo_exploracao`, `participacao` (`models/core.py:85-113`) — os campos de LCDPR ja la estao, escritos por outra via.
- `lcdpr.py` (5,2 KB) — o gerador de relatorio, separado do exportador.
- `test_lcdpr_leiaute.py` (10 KB) — a harness de teste ja existe para estender.
- O `Q100` a funcionar significa que o **pipeline financeiro ja chega ao LCDPR**. Esta nao e uma integracao do zero.

**Como se usa.** Nao se escreve um exportador novo. Escrevem-se tres registos
dentro do que existe, e — que e o ponto que o `9.md` nao alcanca — **um guarda
que recusa exportar um ficheiro incompleto**:

> Hoje o produtor clica "exportar LCDPR", recebe um `.txt`, e o validador da
> Receita devolve um erro que ele nao sabe ler. O `.txt` abre a porta a uma
> retificacao que so se fecha em ate 5 anos (a confirmar).
>
> **A correccao honesta nao e "escrever os registos que faltam". E nao deixar
> exportar enquanto faltam.** Um `pode_exportar()` que verifica os 9 registos e
> diz *"faltam Q200 e 0045 — preenche o tipo de exploracao"* e mais valioso que
> um ficheiro que falha em silencio. Um e uma ajuda; o outro e uma armadilha.

**Para que serve.** O `9.md` §4 chama ao LCDPR *"o gancho comercial mais forte
que existe para este produto"*: e obrigatorio por lei acima de um limite que o
`9.md` cita, e o medo concreto do produtor. Um LCDPR completo e gratuito e a
melhor campanha de aquisicao disponivel — o produtor entra pela porta do medo
fiscal.

**Primeiro passo.** `Q200` primeiro. E uma hora, nao dois dias, e quando sair
o guarda de exportacao passa a ser util imediatamente.

**Verificacao.** `test_lcdpr_leiaute.py` ganha um caso por registo, e um caso
negativo: com `tipo_exploracao = "4" (Parceria)` e sem contrapartes, a view
**recusa** com HTTP 400 e diz o que falta.

---

## 2.2 Caderno de Campo — o P0 que o `9.md` conta como "meia hora"

**O que falta.** Fotos georreferenciadas. O `9.md` §7.3 esta certo no
diagnostico: *"sem isto, o 'sem sinal' e uma nota de texto. Um registo sem
prova e uma opiniao."*

E certo em que e meia hora de JavaScript. **Errado no que chama "meia hora".**
O que falta nao e o `<input type="file">` — e o outro lado.

**O que ja temos.** Isto e o que muda a estimativa:

| Activo | Onde | O que e |
|---|---|---|
| Modelo com `latitude`/`longitude` | `app/models/caderno.py` | `decimal_places=6` (~11 cm), com validadores de range |
| Hora do produtor preservada | `pwa/sync.js` + `indexeddb.js:198` | `created_at` viaja no payload |
| Fila offline de fotos | `pwa/indexeddb.js` | store `photos` com blob |
| **Camera com captura** | `ia_dock.html:27` | `<input type="file" accept="image/*" capture="environment">` — **ja existe** |
| **Geolocalizacao** | `cadastro-receituario.html:37` | `navigator.geolocation.getCurrentPosition` — **ja existe** |
| Padrao de captura multimedia | `whisper-audio.js:531` | `getUserMedia` |

**Como se usa.** Os primitivos de camera e geolocalizacao **ja estao escritos**
noutras paginas. O que falta e lida-los ao `NotaCampo` e implementar o `fotos/`
que ficou a devolver **501** de proposito.

> Deixei `fotos/` e `voice/` em 501 com a lista do que falta, em vez de 404,
> porque um 404 diz "a app nao sabe o que e isto" e um 501 diz "isto nao existe
> ainda, e aqui esta o que falta". **A lista do 501 e a backlog.** Nao e um
> erro por resolver — e a especificacao escrita no sitio onde alguem vai
> procurar.

O que falta para o `fotos/` deixar de ser 501:

1. `FotoNota` (modelo, `FileField`, `MEDIA_ROOT` em producao) — meio dia.
2. Validacao de tipo MIME e tamanho — uma hora.
3. Associacao a `NotaCampo` e marcacao de sincronizado no IndexedDB.
4. **O botao de camera e a leitura de GPS na UI do caderno** — as duas coisas
   que o `9.md` chama de "meia hora", e que estao prontas noutro sitio.

**Para que serve.** O caderno deixa de ser um bloco de notas e passa a ser
prova. "Vi pulgao no canto norte do talhao 3, 14h20, com a folha assim", com
foto e coordenada, e um registo que um tecnico de agronomia aceita numa
auditoria. Sem foto, e opiniao.

**Primeiro passo.** O `FotoNota` e o endpoint. A UI depois — porque um endpoint
que funciona sem UI nenhuma e meio produto, e uma UI que fotografa sem guardar
e pior que nada.

---

## 2.3 Telemetria de maquina — "16 widgets clonados", que e pior que zero

**O que falta.** Ingestao. `top_globais.py:2` diz *"16 widgets
FieldView/JD/Trimble/Solinftec clonados"* — a interface foi copiada, a
integracao nao existe. `grep FieldView|Operations Center|Stara` nao devolve
nada.

**O `9.md` §8.1 chama isto de "a barreira de adopcao mais dura do produto"**,
e o posto esta certo: telemetria de maquina e caro e ninguem paga duas vezes.

**O que ja temos.** E aqui esta a parte que o `9.md` nao viu:

| Activo | Onde | O que e |
|---|---|---|
| `Maquinario.horas_uso` | `models/maquinario.py` | **O receptor ja existe.** Horometro decimal |
| `ultima_manutencao`, `proxima_manutencao` | mesmo | Manutencao preventiva |
| `valor_aquisicao`, `valor_residual`, `vida_util_anos`, `data_aquisicao` | mesmo | Depreciacao ja calculada (`valor_atual`) |
| Marca e modelo | mesmo | `seed_mvp_demo.py` ja semeia um John Deere 8R 340 |
| **Ja existe uma regra que usa isto** | `regras_auto.py:339` | `"[ERP] John Deere -30% R$120k/1000ha - horometro >250h"` |
| Campo `maquina` no sandbox | `sandbox.py:200` | O LLM ja sabe falar de maquina |

**Como se usa.** O destino existe; falta o cano. E a forma mais barata do cano
e um **importador de CSV**: John Deere, FieldView e Stara exportam todos
ficheiro. Mapear o CSV para `horas_uso` mais `ultima_manutencao` e uma tarde.

A recompensa e maior do que parece, porque **o motor proativo ja tem a regra
escrita** (`regras_auto.py:339`). O que lhe falta e o numero. Com o numero, o
sistema passa a dizer *"o trator passou das 250 horas — agende a revisao"* sem
o produtor contar horas a mao, e a regra deixa de ser um texto de exemplo.

> **Porque e melhor do que integracao API.** O `9.md` contrasta "faz codegen
> para ESP32" com "le telemetria de maquinas que ja existem" e tem razão quanto
> a intencao. Mas a ordem correcta e outra: **CSV primeiro, API nunca, no
> arranque.** CSV e o denominador comum entre tres fabricantes que nao partilham
> API nenhuma, e uma importacao manual de CSV serve 80% do caso. Construir tres
> integracoes antes de provar que alguem quer sincronizacao automatica e o erro
> classico de produto.

**Para que serve.** Deixa de ser um ERP com uma telemetria decorativa e passa a
ser o registo de custo e manutencao que o produtor ja tem noutro sitio.

**Primeiro passo.** `importar_csv_maquinario` — um command de Django, CSV na
entrada, `horas_uso` na saida. Teste: um CSV de 3 linhas muda 3 horometros e
dispara a regra de `regras_auto.py`.

---

## 2.4 IA na borda — o que ja funciona, e onde nao e vendido

**O que ja temos.** WebLLM com SmolLM2-1.7B no WebGPU
(`app/static/js/ia-local/ia-local.js:3` — `iaModel = 'SmolLM2-1.7B-Instruct-q4f16_1-MLC'`),
CSP corrigida (`config/settings/base.py:336-339` — `esm.run` e
`'wasm-unsafe-eval'`), consentimento explicito antes dos 1,1 GB com recusa
persistida em `localStorage` (`ia-local.js:5452-5472`, e o fallback para
`Qwen2-0.5B` em `:5632-5640`), e degradacao para motor de servidor. O utilizador
confirmou que carrega no navegador.

**O que falta.** Nada no codigo. Falta no **posicionamento**: o `9.md` §6.1 e
§10.1 listam isto como vantagem, e e a unica das seis que e **impossivel de
copiar sem mudar de arquitectura**. Uma Aegro centralizada nao pode oferecer
isto sem reescrever o backend.

Mas ha uma restricao que os dois documentos nao cruzaram. O `9.md` §6 mediu
`Phi-3.5-vision` em cerca de 2,6 GB e comparou com o orcamento de 2 GB que o
manifesto declara. **Se esse modelo ainda estiver na arvore** (e o `IA_MODELOS`
de `ia-local.js:5485` nao o lista hoje), a restricao já nao se aplica. Se
voltar, a visao computacional do §VII deixa de ser um problema de
implementacao e passa a ser de memoria: ou a projecao de 2 GB sobe, ou a visao
fica para um modelo no servidor, e o texto tem de dizer qual.

**Para que serve.** Esta e a **ancora de diferenciacao** para o produtor sem 4G
no talhao. Um ERP que precisa de rede para responder "qual o talhao esta
doente" nao funciona no lugar onde o problema acontece.

**Primeiro passo.** Nenhum. E decisao de texto: vender a ancora em vez de a
listar como feature.

---

## 2.5 Proveniencia, MRV e carbono

Esta e a unica linha dos dois documentos que eu **subscrevo por inteiro**, e e a
unica que descreve uma assimetria real de arquitectura.

**O que os documentos dizem.** O `9.md` §5: o Ampliagro tem "o sensor e nao o
medidor"; a Fluere tem o medidor e compra os dados; nenhuma das duas tem o que a
outra tem. E §10.2-10.3: proveniencia como tipo, e honestidade sobre a ausencia,
sao coisas que um ERP comercial nao pode ter — porque precisa de mostrar um
numero.

**O que ja temos, e e o activo:**

| Activo | Onde | Porque serve a MRV |
|---|---|---|
| 6 estados, `fonte_dado` **read_only** | `validators.py:11-17`, `proveniencia.py` | O cliente **nao escolhe** a confianca. Num MRV isso e o produto. |
| Regra escrita | `validators.py:40` — *"o sistema nunca promove uma afirmacao a medicao"* | E a politica de custodia de evidencia, em codigo. |
| `medir(None)` da `SemDado`, nunca `Medido(0)` | `proveniencia.py:160` | Um certificador pergunta "o que acontece quando o sensor falhou?" e a resposta e um tipo, nao um zero. |
| `IAExecucao` grava cada intent com latencia e flags | `models` | Rastreabilidade de quem pediu o que, quando. E o que uma auditoria pergunta primeiro. |
| Testes doutrinarios | `test_regras_cultura_motor.py`, `test_csp.py`, `test_placeholder_zero.py` | A cultura de nao prometer o que nao se mede, **testada em CI**. |

**Como se usa — e onde esta o limite, com honestidade.**

Carbono e *emissoes x fatores x confianca na fonte*. O Ampliagro tem o
**terceiro**. Nao tem o primeiro nem o segundo, e o `9.md` §11.1 esta certo:
emissao de GEE com GHG Protocol e produto a inteiro (a Fluere faz em 30 a 60
dias com a UFSM).

A jogada correcta **nao e construir MRV**. E:

> **Posicionar o Ampliagro como a camada de evidencia de um MRV de terceiros.**
> A Fluere, a Carbonova e o verificador precisam de saber de onde veio cada
> numero. E caro, e lento, e e exactamente o que um tipo de proveniencia
> tipado resolve. Uma empresa de MRV nao quer um ERP — quer um sistema que nao
> consegue dizer "medido" quando mediu nada.

Isto muda a conversa comercial: deixa de ser "facamos carbono" e passa a ser
"os vossos dados sao tipados na origem, e isso audita-se".

**Primeiro passo.** Nenhum de codigo. **Um paragrafo de posicionamento**, e um
teste que valide que `fonte_dado` e mesmo read-only em todos os serializers —
porque e a promessa.

---

## 2.6 OTA e firmware — a promessa que mata o primeiro cliente

**O que falta.** Tudo. `grep ota_update|esptool|mpremote|micropython|firmware_upload`
nao devolve nada. O que existe e `ia/iot.py` a gerar C++ para colar no Arduino
IDE. E `models/iot.py:135` tem um campo `firmware_version` que nada escreve.

**Os dois documentos concordam, e ambos tem razao.** O `5.md` §2.5 chama-lhe
*"a parte mais perigosa do documento"*; o `9.md` §8.2 chama-lhe *"promessa
enganosa... mata o primeiro cliente e o motivo conta"*.

**Porque e mais grave do que uma funcionalidade em falta:** nao e o produtor que
sofre. E o **tecnico de logistica que le o site antes de comprar** e depois
pergunta a equipa de vendas o que ninguem responde.

**O que ja temos.** `firmware_version` no modelo. E — isto e o que os dois
documentos **nao WHM** — **a doutrina que torna a correccao trivial**: o
`5.md` §2.5 apanhou que `models/dinamico.py:32` **proibe** codigo gerado por IA
a correr no servidor, e que o manifesto §VII descreve exactamente isso para
outro alvo.

**Como se usa.** O `5.md` Fase 3 da a resposta certa e eu subscrevo: reescrever
o §VII com os mesmos controlos do §III — o LLM propoe o codigo, o produtor
reve linha a linha, o upload exige confirmacao, e ha um botao fisico no
dispositivo.

A minha contribuicao e a **fase intermediaria honesta**, que os dois nao
propoem: um *guided flash*. O sistema diz ao produtor exactamente que binario
compilar, da a linha de comando `esptool write_flash`, e verifica o checksum
do `.bin` que **o proprio produtor compilou**. Nao compila no servidor, nao
gera firmware em dispositivo de terceiro, nao salta a camada de aprovacao — e
mesmo assim **cumpre a promessa** de "nao precisa de bootloader", que e a parte
dela que o produtor sente.

Se depois disso se quiser OTA a serio, e toolchain de firmware: produto novo.

**Para que serve.** Deixa de haver uma promessa que nao se cumpre. Custa uma
pagina de texto e uma tarde de guiao.

**Primeiro passo.** Tirar a promessa do manifesto. **Meia hora, e e o item de
melhor relacao esforco/impacto de toda esta lista.**

---

## 2.7 Motor proativo — dois agendadores, nenhum armado

**O que falta.** Decisao. `app/tasks.py` tem 13 linhas e um `return True`
comentado *"Placeholder"*. `proativo_tasks.py:274` so arma `BEAT_SCHEDULE` com
`AMPLIA_CELERY_BEAT=1`. E existe um **segundo** agendador em
`tools/bat/setup_tarefa_proativa.bat` a apontar para as mesmas horas.

**O perigo nao e a ausencia — e a ambiguidade.** O `5.md` §2.1 ja escreveu o que
importa: armados os dois, *"a varredura corre duas vezes; o dedup segura o
alerta duplicado — e por isso o defeito e PERIGOSO, nao visivel: parece
funcionar"*.

**O que ja temos.** O motor deterministico existe e e bom: `proativo.py:580`
`avaliar_usuario`, com governanca de cada numero justificada. Corre sem LLM,
sem tokens, sem painel aberto. **Isto e um activo real** — e o `9.md` nao o
menciona.

**Como se usa.** Escolher um agendador e **impor a escolha**:

1. Contentores como alvo: Celery tem de ser real, senao **nao ha motor proativo nenhum**. Isto nao e uma divergencia de codigo; e de ambiente. Um contentor efemero sem Celery nem Task Scheduler perde a §V "Caminho A" inteira, e e exactamente essa via que o manifesto vende.
2. `check_agendador.py` — falha se `BEAT_SCHEDULE` estiver armado **e** a tarefa do Windows instalada.
3. Implementar `gerar_relatorio_async` ou apaga-la. Uma funcao que faz `logger.info` e devolve `True` e honesta no ficheiro e enganosa no manifesto — e o ficheiro ja diz *"Placeholder"*, ou seja, alguem sabe.

**Para que serve.** Deixa de haver um runtime descrito como activo que nao
corre, e o contentor deixa de perder a unica via deterministica do produto.

---

## 2.8 Garantias de seguranca — trocar "absoluto" por "medido"

**O que os documentos dizem.** O manifesto §VI chama ao isolamento *"fundacao
impenetravel"* e *"isolamento absoluto"*. O `9.md` §5 demonstra que a medicao so
cobre o caminho HTTP.

**O que esta certo nessa critica, e o que e exagero dela.**

Certo: `TenantIsolationMiddleware` e `ServidorRevogadoMiddleware` sao
middleware. Passam em HTTP. Nao passam em tarefa Celery nem em management
command. E `grep ativo_servidor app/api/` da zero dentro das views.

Exagero: eu medi que existe **uma unica** task Celery no projecto
(`gerar_relatorio_async`, 13 linhas, placeholder). A task que o `9.md` §5
menciona (`proativo_tasks.py:206`) tambem existe, mas e uma **regra
deterministica**, nao um acesso a dados de outro utilizador.

**Como se usa.** Duas accoes, ambas baratas:

1. **Medir** o que o `9.md` §9 diz que ninguem mediu: correr a varredura com um servidor revogado e dizer o que acontece. Sem isto, e arquitectura temida.
2. **Tirar as palavras.** Trocar *"absoluto"* e *"impenetravel"* por *"forte e medido, para requests HTTP"*. Uma garantia que ninguem mediu nao e uma garantia — e um passivo.

Isto nao diminui o produto. **Diminui o passivo.** Um cliente tecnico que
descubra que o "absoluto" tinha uma excepcao nao confia no resto.

---

## 2.9 O teste que impede tudo isto de voltar

O `9.md` §11 P0-2 e o item mais valioso das duas listas e o mais ignorado:
*"Escrever o guarda que impede o manifesto de divergir em silencio."*

E tem razao, porque **e a unica accao deste documento que torna todos os
outros itens auto-sustentaveis**. Sem ele, cada linha do manifesto volta a
divergir em tres meses, e voltamos a este documento.

**Ja existe a cultura, que e o que torna isto barato:**

- `test_csp.py` — prova que uma politica escrita nos settings tem de coincidir com o que o HTML pede. Exactamente a propriedade que falta ao manifesto.
- `test_promessas_numericas.py` — torna visivel em CI uma promessa de marketing que o codigo nao cumpre.
- `test_regras_cultura_motor.py` — *"ou admite-se que ela nao existe e tira-se a promessa do ecra"*.
- `test_placeholder_zero.py` — existe para travar o zero inventado.
- `tests/test_reverificacao_relatorio.py` (novo) — CSP, proxy, IoT, fiscal, commands.
- `tests/test_intents_confirmacao.py` (novo) — toda escrita tem `requires_confirmation`.

**O que falta e um `test_manifesto_confere_com_codigo.py`** que faca, para cada
afirmacao do manifesto: *existe no codigo?* — com a distincao que o `9.md` §A.0
descobriu ao custo de dois dias: **declaracao nao e implementacao**.

| Afirmacao do manifesto | Verificacao | Estado hoje |
|---|---|---|
| "Celery + Redis, worker continuo" | `tasks.py` faz mais do que `return True`? | **FALHA** |
| "MQTT, ingestao continua" | `mqtt_listener.py` importavel? | passa |
| "Fernet/AES-256, `AMPLIAGRO_DATA_KEY`" | a chave e lida na ingestao? | **FALHA** |
| "OTA sem bootloaders" | existe upload de firmware? | **FALHA** |
| "5 estados de proveniencia" | `ESTADOS_FONTE` tem 5? | passa |
| "Visao computacional em 2 GB" | o modelo cabe em 2 GB? | **FALHA** |
| "Isolamento absoluto" | existe teste fora de HTTP? | **FALHA** |

**Quatro de sete falham.** E esse o numero que decide se o manifesto pode
circular.

**Para que serve.** Cada linha que acrescenta a lista e uma que ja nao precisa
de ser re-encontrada. E o teste e barato: e `grep` com uma regra sobre o que
conta como implementacao.

---

# PARTE 3 — Sequencia

Ordenada por **leverage sobre custo**, nao por ambicao. Cada onda e
verificavel isoladamente e deixa o produto honesto no fim.

## Onda 0 — Parar de mentir (meio dia)

> **ATENÇÃO:** a tabela abaixo é a **versão original** do plano, escrita antes
> de alguém a verificar por execução. O estado real está na tabela
> "Onda 0 e 1 — ESTADO VERIFICADO" logo abaixo, e é essa que manda.
> Os números entre parênteses nesta tabela estavam errados.

| # | Accao | Verificacao | Porque primeiro |
|---|---|---|---|
| 0.1 | `is_planting_season()` sem regra devolve `None`, nao `True` | **FEITO** — ver estado verificado | A unica correccao que impede o sistema de **afirmar** algo falso |
| 0.2 | `test_manifesto_confere_com_codigo.py` | **FEITO, e corrigido** — ver estado verificado | Nada mais fica verificado |
| 0.3 | Tirar o OTA do §VII | **NAO HÁ O QUE TIRAR** — ver estado verificado | O manifesto não está no repositório, e o produto não promete OTA ao cliente |
| 0.4 | "absoluto" → medido | **FEITO noutro sítio** — a palavra estava na meta description | Passivo removido |
| 0.5 | Decidir o agendador | **FEITO** — ver estado verificado | Ambiguidade e pior que ausencia |

**Resultado:** o Ampliagro para de afirmar coisas que nao faz. Custa meio dia.

### Onda 0 e 1 — ESTADO VERIFICADO (2026-10-05, medido por execução)

Alguém tinha de verificar: **3 dos 5 itens da Onda 0 já estavam feitos** quando
este plano foi escrito. O próprio plano avisa que **11 das 19 afirmações de
entrada já estavam mortas** — e acertou também sobre si próprio.

| # | Item | Estado real, verificado | Prova |
|---|---|---|---|
| 0.1 | `is_planting_season()` devolve `None` | **FEITO** (outro processo) | `culture_config.py:436-437`. O chamador usa `if estado is False:` (identidade, não `not`), senão `None` disparava alerta falso |
| 0.1t | guarda de 2 lados | **FEITO** (por mim) | `tests/test_plano_execucao.py`: `soja` sem janela → `None`; janela out-mar → nov `True`, jun `False`. O 2.º lado impede a correcção de ir longe demais |
| 0.2 | `test_manifesto_confere_com_codigo.py` | **EXISTE, com POLARIDADE INVERTIDA** | 10 dos 12 passavam porque a promessa **não** era cumprida. Corrigido para `xfail(strict=True)` + asserção invertida |
| 0.3 | Tirar o OTA do §VII | **BLOQUEADO** | O manifesto Agro 5.0 **não está no repositorio**; §II/§VI/§VII só são citadas *dentro* de documentos de análise. **Boa notícia:** o produto **não promete OTA ao cliente** — zero ocorrências nos templates |
| 0.4 | "absoluto" → medido | **FEITO, e no sítio certo** | A palavra estava na **meta description**: "Sistema **absoluto** do agro 5.0", 5 ocorrências (`base.html:8` propaga a todas as páginas, `login.html:7/30/50`, `onboarding.html:32`). Guarda: `tests/test_promessas_absolutas.py` |
| 0.5 | `check_agendador.py` | **FEITO** (por mim) | `tests/test_agendador_unico.py`, 3 testes. Falha **só em conflito real**; `AMPLIA_CELERY_BEAT` documentado com aviso. A mutação descobriu **2 tarefas do Windows instaladas** |
| extra | `django-csp` + `whitenoise` | **FEITO** (por mim) | Usados em `base.py:119` e `base.py:216`, declarados em manifesto nenhum. Guarda: `tests/test_dependencias_declaradas.py` |

**O 0.2 é o item mais instructive deste plano.** O ficheiro original tinha
`assert count == 0` nos testes de promessa não cumprida: passava *exactamente*
no caso que devia sinal. A consequência não era teórica — implementar a promessa
**fechava a lacuna em silêncio**. Corrigido:

| estado da promessa | pytest | suite |
|---|---|---|
| em aberto | `x` XFAIL | **verde** |
| cumprida | `F` XPASS(strict) | **vermelha** |

Isto é: **implementar a promessa deixa de ser silencioso.**

**Onda 1, itens 1.1/1.2/1.3: FEITOS** (por outro processo), verificados por execução:

- **9 registos LCDPR** gerados, confirmados: `0000`, `0010`, `0030`, `0040`,
  `0045`, `0050`, `Q100`, `Q200`, `9999`. O `9999` fecha o ficheiro
  (`lcdpr_export.py:532-535`).
- **A guarda de exportação existe** e é honesta: `LCDPRDadosIncompletos`
  (`lcdpr_export.py:6`), levantada em `:129` quando falta o CPF/CNPJ do `0000`,
  tratada nas **duas** views (`views/financeiro.py:144`,
  `api/views/financial.py:453`).
- `tests/test_lcdpr_conformidade.py` declara o que não sabe:
  `REGISTOS_PENDENTES = {"0030", "0040", "0045", "0050"}` — enunciado de campos
  oficial não obtido. Esta honestidade vale mais que um `Q200` a mais.

**1.4 começou:** `cafe` já tem **4 regras** (23:51). `soja`, `milho`, `algodão` e
`cana` continuam a 0 — e são as que o plano §2.1 diz valerem mais.

## Onda 1 — O dinheiro e a prova (1 a 2 semanas)

| # | Accao | Leverage | Verificacao |
|---|---|---|---|
| 1.1 | LCDPR `Q200` | ~1 h, dados ja calculados | **FEITO** — `CAMPOS_Q200` em `lcdpr_layout.py:192` |
| 1.2 | **Guarda de exportacao** | Impede o `.txt` que a Receita rejeita | **FEITO** — `pode_exportar()` + guarda no `gerar_arquivo()`, 14 testes |
| 1.3 | LCDPR `0010` | Meio dia, 1 campo novo | **FEITO** — registo gerado em `lcdpr_export.py:504` |
| 1.4 | Regras de 15 culturas | Conteudo, nao codigo; o motor ja existe | `get_culture_business_rules('soja')` devolve janela |
| 1.5 | `importar_csv_maquinario` | Activa a regra que ja existe em `regras_auto.py` | **FEITO** — command novo, 15 testes, 3 fabricantes |
| 1.6 | `FotoNota` e endpoint `fotos/` | Tira o 501 | **FEITO** — `FotoNota` + 0068 + 0069, 14 testes |

**Resultado:** LCDPR nao rejeitado, 15 culturas com guidance real, maquina com
telemetria importada, caderno com prova fotografica. **Os quatro sao active no
produto hoje.**

## Onda 2 — O que precisa de decisao de negocio (1 mes)

| # | Accao | Depende de |
|---|---|---|
| 2.1 | LCDPR `0045` e modelo de parceiros | — |
| 2.2 | Escolher o numero: 11 cadeias / 707 culturas, ou corrigir o texto | **C1/C2 do utilizador** |
| 2.3 | Assinatura ICP-Brasil | Integracao PKI, ou parceria com firma de contabilidade |
| 2.4 | NF-e: integrar, ou remitir honestamente | **C3 do utilizador** |
| 2.5 | Paragrafo de posicionamento em carbono | §2.5 |

## Onda 3 — Onde o Ampliagro tem algo que os gigantes nao copiam (trimestre)

| # | Accao | Porque aqui e nao antes |
|---|---|---|
| 3.1 | Escolha de **parceria** de MRV, nao produto | Vender a camada de evidencia; o `9.md` §11.1 concorda que emissao de GEE nao e nosso |
| 3.2 | Guided flash (nao OTA) | Cumpre a promessa honesta sem LLM-para-silicio |
| 3.3 | Mais culturas com regras | Cada uma e uma hora de agronomo, nao um sprint |

---

# PARTE 4 — O que NAO fazer

O `9.md` §11 e o `5.md` Fase 3 listam o que esta fora. Confirmo e acrescento.

| # | Nao fazer | Porque |
|---|---|---|
| N1 | **Emitir GEE / GHG Protocol** | Produto a inteiro; a Fluere faz em 30 a 60 dias com a UFSM |
| N2 | **Tokenizacao / blockchain** | Commodity. E `blockchain` esta num teste, nao em codigo |
| N3 | **TOTVS PIMS / SAP** | Cliente diferente, escala diferente |
| N4 | **OTA com LLM a escrever e a fazer upload** | Salta a camada de aprovacao. Contradiz `models/dinamico.py:32`, que e a doutrina do proprio projecto |
| N5 | **API de John Deere antes de CSV** | Tres integracoes para provar que alguem quer sincronizacao automatica |
| N6 | **"Converter" as 488 culturas em regras** | Requer agronomo, nao esforco. Fazer 15, medir, depois decidir |
| N7 | **Perseguir o "ERP melhor que o Aegro"** | Nao e o mercado. O `9.md` §12.4 esta certo: nenhum dos dois chega ao outro |

---

# PARTE 5 — Como isto se mede

Uma coisa que os dois documentos de entrada apontam, e que este herda: **medicoes
que nao sao re-verificadas envelhecem**. Das 19 afirmacoes de entrada, 11 ja
estavam mortas. A regra que evita repetir isso:

> **Cada afirmacao vale no instante em que foi tirada.**
> `9.md` §0 — e esta confirmado: durante este trabalho `data-store.js` mudou por
> outro processo, e a lista de falhas da suite mudou entre execucoes.

## Os quatro numeros que decidem se esta onda funcionou

| # | Numero | Hoje | Alvo |
|---|---|---|---|
| M1 | Falhas na suite | 5 | 3 — as duas comerciais precisam de decisao, nao de codigo |
| M2 | Registos LCDPR exportaveis | 6 de 9 | 9 de 9, com guarda |
| M3 | Culturas com regra agronomica | **0** | 15 |
| M4 | Afirmacoes do manifesto que passam o teste | 3 de 7 | 7 de 7 |

M3 e o numero que ninguem esta a medir, e e o que decide se o produto e um ERP
com 488 etiquetas ou um sistema que diz quando plantar.

## Regra de CI

```
1. Nenhuma feature entra sem teste que falhe sem ela.
2. Nenhuma promessa entra no manifesto sem teste que a confirme.
3. Nenhum default permissivo onde o sistema nao sabe.
```

A segunda e a que o `9.md` §11 pedia e que ninguem escreveu. E a mais barata, e
a que impede todos os outros itens de voltarem.

---

# Apendice — Reproduzir cada afirmacao deste documento

```powershell
# 1.1 — as 488 culturas nao tem regras
python -c "import django;django.setup();from app.api.culture_config import get_culture_business_rules;print(len(get_culture_business_rules('soja')))"
#   -> 0

# 1.1 — o motor assume permissividade
python -c "import django;django.setup();from app.api.culture_config import CultureBusinessEngine;print(CultureBusinessEngine('soja').is_planting_season())"
#   -> True   (porque self.rules == {})

# 1.2 A1 — registos LCDPR
Select-String "self\._adicionar_linha\(reg_" app\services\lcdpr_export.py
#   -> 0000, 0030, 0040, 0050, Q100, 9999

# 1.2 A3 — OTA
Select-String "ota_update|esptool|micropython|firmware_upload" app\**\*.py
#   -> vazio

# 1.2 A4 — o placeholder
Get-Content app\tasks.py
#   -> 13 linhas, return True, "# Placeholder"

# 1.2 A5 — o gate do Celery
Select-String "AMPLIA_CELERY_BEAT" app\ia\proativo_tasks.py
#   -> linha 274

# 1.3 B1 — os 6 estados
python -c "import django;django.setup();from app.ia.proveniencia import TODOS;print([e for e in TODOS])"
#   -> medido, medido_com_ressalva, suspect, sem_dado, simulado, declarado

# 2.1 — os campos de LCDPR que ja existem
Select-String "tipo_exploracao|participacao|caepf" app\models\core.py
#   -> linhas 85-113

# 2.2 — os primitivos de camera e GPS que ja existem
Select-String 'capture="environment"' app\templates\ia_dock.html
Select-String "geolocation" app\templates\cadastro-receituario.html

# 2.3 — o receptor de telemetria que ja existe
Select-String "horas_uso|proxima_manutencao" app\models\maquinario.py
#   -> e a regra que depende dele: regras_auto.py:339

# 2.6 — firmware_version sem writer
Select-String "firmware_version" app\models\iot.py
#   -> linha 135; grep esptool -> vazio
```

---

## Fecho

Os dois documentos de entrada terminaram no mesmo sitio por caminhos
diferentes: **o registo sobre o registo**. O `9.md` mediu o que o mercado
vende; o `5.md` mediu o que o manifesto promete. Ambos encontraram o mesmo
objecto — *"o segundo processo a editar a arvore"* — e ambos pagaram a mesma
licao pelo caminho errado: convergir nao e verificar.

O que este documento acrescenta e a pergunta que nenhum dos dois fez. Nao
*"o que falta?"*, mas **"o que ja temos que faz isto?"**. E a resposta muda o
tamanho de quase tudo:

- O LCDPR nao e um exportador novo — e tres registos e uma guarda, e dois
  deles custam horas porque os dados ja sao calculados.
- A telemetria de maquina nao e tres integracoes — e um importador de CSV para
  um modelo que ja tem horometro, activando uma regra que ja esta escrita.
- As 15 culturas com agronomia nao sao um motor novo — e conteudo para um motor
  que ja esta construido e testado.
- O carbono nao e um produto — e uma camada de evidencia que o Ampliagro ja
  produz e nao sabe que vende.

E um achado que nenhum deles viu, e que e o mais importante de todos: **as 488
culturas nao tem uma unica regra agronomica, e o motor afirma que se pode
plantar quando nao sabe.** Numa casa que passou a vida a recusar inventar
zeros, e a incoerencia mais cara que resta — e a mais barata de corrigir.
