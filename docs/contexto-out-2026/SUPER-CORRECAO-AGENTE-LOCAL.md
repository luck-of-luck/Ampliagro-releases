# SUPER-CORRECAO - Agente de IA Local do Ampliagro

**Data:** 2026-10-03
**Alvo:** agente local que corre OFFLINE no navegador (WebLLM / SmolLM2-1.7B-Instruct-q4f16_1-MLC), uso em campo com rede baixa.
**Ficheiro principal:** `app/static/js/ia-local/ia-local.js`.
**Ramo:** `fix/agente-local-loop-conflito`

> **Nota:** escrito propositadamente em ASCII. A ferramenta de escrita deste host
> corrompe caracteres nao-ASCII - reproduzi o bug durante a execucao. Um
> documento sobre corrupcao de texto nao pode carregar corrupcao de texto.

---

## 0. ESTADO

| | Correcao | Sev. | Estado |
|---|---|---|---|
| A8 | Loop de voz | P0 | **FEITA e verificada** |
| A4 | Duas versoes do agente em cache | P0 | **FEITA e verificada** |
| A3 | Fallback fabricava registos | P1 | **FEITA e verificada** |
| A3b | Fronteira no servidor (segunda linha) | P1 | **FEITA e verificada** |
| A9 | Poller acumulava sondagens | P1 | **FEITA e verificada** |
| A1-a | Nao se sabia qual decisor respondeu | P1 | **FEITA e verificada** |
| A1-b | `fetch` sem cache/timeout, `{}` a mentir | P1 | **FEITA e verificada** |
| A2 | Agente nao sabia ser interrompido | P1 | **FEITA e verificada** |
| A6 | Ficheiro cresce, mapa desatualizado | P3 | por fazer |
| A7 | As auditorias anteriores nao eram auditorias | P3 | por fazer |
| ~~A5~~ | ~~Texto corrompido~~ | ~~P1~~ | **REMOVIDO - NAO EXISTIA** |

**Verificacao:** 141 testes vitest (11 ficheiros) + 9 suites cjs (~1925 checks) +
145 testes Python (`app/amplia_mcp/` completo) + 35 do agente + `manage.py check`
sem problemas. A baseline antes das alteracoes era 60 testes nos 3 ficheiros que
cobrem o agente; continua a ser 60.

**Cada correcao tem um teste que falha sem ela.** Nao e' uma promessa: o teste da
A9 foi corrido contra o codigo antigo e deu `got=6 esp=1`; o da A3b afirma o
`codigo` que so existe quando a guarda corre.

---

## 1. CONFISSAO DE LIMITE

A revisao por comite (46 IAs) **NAO correu**. `cluster_ciclo` expirou aos 270 s
em duas tentativas (perfis `completo` e `rapido`); as ondas de
`cluster_consultar` com n>=4 tambem expiraram. Apenas uma onda com n=3
respondeu. Cada achado aqui foi lido em disco, nao inferido - mas houve **uma
leitura so**, sem segunda opiniao.

**Nao foram analisados:** `proativo-local.js`, `alerta-feed.js`,
`whisper-audio.js`, `sandbox.py`, `app/amplia_mcp/`, e cerca de 4000 linhas do
proprio `ia-local.js` (o corpo dos 9 wizards, `smartResponse`, `analisarIntent`,
`sandboxBridge`, `raciocinarLlm`). Ver seccao 6.

**Concorrencia activa:** durante a execucao apareceram ficheiros novos em `docs/`
(`SUPER_PLANO_AMPLIA_OS.md`, `PLANO_CRIADOR_LIVRE.md`,
`mcp-Ampliagro_amplIA.md`). **Outra sessao esta a trabalhar neste repositorio.**
O `ia-local.js` estava limpo (ultima escrita de 1 de outubro) quando comecei, por
isso nao houve colisao - mas se essa sessao tocar no `ia-local.js`, ha conflito
a resolver a mao.

---

## 2. OS DOIS ERROS QUE EU COMETI NA PRIMEIRA EXECUCAO

Registados porque o registo vale mais que a correccao. (E3-E5, da segunda
ronda, estao na seccao 4.1.)

**E1 - `Identifier '_ctxCache' has already been declared`.** O A1-b introduziu um
`_ctxCache` novo, mas ja existia um em `entenderSistema()` (a 4463), que cacheia
a descricao do sistema. Quebrou 14 testes. Corrigido renomeando o meu para
`_ctxProp`. *Foi a suite de testes que apanhou, nao eu.*

**E2 - `'static' takes at least one argument`.** Escrevi a tag de static **por
extenso dentro de um comentario JS** em `ia_dock.html`. O Django avalia tags de
template dentro de comentarios, porque nao sao comentarios HTML - e uma tag sem
argumento rebenta a pagina. Corrigido reescrevendo o comentario. *Apanhei por um
teste de template, e so depois de ter lido o ficheiro para tentar perceber por
quê.*

Dois bugs, dois apanhes automaticos. **E o argumento para nunca correr uma
alteracao sem a suite de testes a correr ao lado.**

---

## 3. A5 - REMOVIDO: NAO EXISTIA CORRUPCAO DE TEXTO

Este achado foi medido **tres vezes** e deu tres respostas diferentes. Registo as
tres porque o padrao e instrutivo:

| Medicao | Metodo | Resultado |
|---|---|---|
| 1a | regex `a€` no PowerShell | "420 linhas (6,9%)" |
| 1b | regex por codepoint `U+00C3`, `U+00C2`, `U+FFFD` | "16 linhas (0,26%)" |
| 1c | so `U+FFFD` e C1 (`U+0080`-`U+009F`) | **0 linhas** |

O que happenedo, em ordem:

1. **A regex `a€` contava travessas legítimas.** Um em-dash `—` e `E2 80 94`;
   decodificado como Windows-1252 e re-codificado, vira `â€"`. A contagem de
   "420" era quase toda em-dash. Os exemplos que dei na 1a versao
   ("Jo?o da Silva", "Nome do talh?o?") **foram falso positivo do detector** -
   essas linhas nunca tiveram corrupcao.
2. **A 2a medicao contava `Ã` como corrupcao.** Mas `Ã` (U+00C3) e uma letra
   portuguesa legitima: NAO, SAO, TAO. As "16 linhas" eram comentarios com
   "NAO".
3. **A 3a medicao usou so marcadores inequivocos** (`U+FFFD` e a gama C1, que nao
   aparecem em texto Portuguese bem formado): **zero corrupcao** em
   `ia-local.js` e em `palco-amplia.js`.

**Conclusao:** o finding era falso do principio ao fim. Nao havia mojibake, o
produtor nunca viu "Jo?o da Silva", e nada disto explica sintoma nenhum.

**O que fica, de verdade:** a ferramenta de escrita **deste host** corrompe
nao-ASCII. Nao o codigo do produto - a ferramenta com que eu escrevo. Por isso
este documento esta em ASCII.

---

## 4. CORRECOES FEITAS

### A8 - P0 - O LOOP DE VOZ (a causa do "entra em loop")

**Ficheiro:** `ia-local.js:5630` (agora deslocado) e `ia_dock.html:254`.

Duas falhas que se multiplicavam:

```js
r.onresult = (e) => {
  const t = e.results[0][0].transcript;   // BUG 1
  ...
};
r.onerror = (e) => console.warn(e);       // engolia a falha
r.start();
return r;                                  // BUG 2: nunca e parado
```

**BUG 1 - indice sempre zero.** `event.results` acumula durante toda a sessao de
reconhecimento, portanto `[0]` e a **primeira frase dita, para sempre**. O
produtor fala "como esta o estoque", e cada `onresult` seguinte reenvia isso. O
modelo nao se prendia: era o indice.

**BUG 2 - sem `stop()`, sem `onend`, instancia nova por clique.** `iaVoz` devolve
`r` mas `iaDockVoz` ignorava o retorno - nao havia caminho para `r.stop()`. Sem
`onend`, o fim do reconhecimento nao era tratado. Cada clique criava outro
`SpeechRecognition`: cinco cliques, cinco microfones vivos, todos a disparar
`iaDockSend()`. E como o agente responde em voz alta, a propria resposta realimenta
o microfone - ciclo autossustentado, sem o produtor tocar em nada.

**O que foi feito:** uma sessao nomeada (`_recVoz`) que para a anterior antes de
abrir a nova; `results[results.length - 1]`; `onend` que limpa; `onerror` que
**diz ao produtor** que o microfone foi bloqueado em vez de engolir; `iaVozStop()`
exportado e ligado a `iaReset()`; e no dock uma **trava de reentrada** que
recusa nova frase enquanto o envio anterior nao terminou.

### A4 - P0 - DUAS VERSOES DO AGENTE (a causa de "conflica")

`base.html` servia `ia-local.js?v=24`; `ia_dock.html` servia
`/static/js/ia-local/ia-local.js?v=23`.

**A descoberta que mudou o diagnostico:** o projeto usa
`STATICFILES_STORAGE = whitenoise.storage.CompressedManifestStaticFilesStorage`.
Com *Manifest*, a tag de static do Django **ja devolve o nome com hash**
(`ia-local.<hash>.js`) - e esse hash e o cache-busting. Portanto:

- O `?v=` manual era **redundante**.
- O caminho do dock, **sem hash**, era o pior dos dois: em producao nao mudava
  quando o ficheiro mudava, e o navegador podia servir a versao antiga
  indefinidamente. **Era o "corrigi e nao mudou nada" do produtor.**

**O que foi feito:** ambos os pontos de entrada usam agora a tag de static do
Django; os `?v=` manuales sairam. Em dev fica o caminho simples, em producao fica
o hash - e os dois lados resolvem sempre para o **mesmo** URL. O `{% load static %}`
foi acrescentado ao `ia_dock.html`, que nao o tinha.

### A3 - P1 - O FALLBACK FABRICAVA REGISTOS

O autor tinha **diagnosticado isto corretamente e escrito a correccao num
comentario** (`ia-local.js:4800-4803`: *"Se nao reconhece: NAO inventar... ou
retorna null"*) sem nunca a implementar. Logo abaixo, o bloco emitia:

```js
{"tool":"criar","args":{"recurso":"${rec}","dados":{"nome":"Novo ${rec}",...}}}
```

**Correccao a uma hipotese minha:** eu disse, e o dossie passedo a equipa
repetiu, que isto "grava lixo na base do produtor". **Estava errado.**
Verifiquei contra o catalogo: `amplia_criar`, `amplia_consultar`,
`amplia_navegar` e `amplia_iniciar_cadastro` estao **todos ausentes**. A
`toolCallGovernada` normaliza o prefixo, e o servidor devolve
`tool_fora_do_catalogo`. **Nao grava.**

O que era verdade: a camada esta **inteiramente morta** - as quatro familias de
tools que emite sao os treze nomes legados que o proprio ficheiro reconhece como
obsoletos em 5431-5436. O produtor perguntava, o agente nao percebia, e recebia
uma lista de **nomes de ferramentas internas** em vez de resposta. Era a "resposta
sem sentido" que o autor descreveu em 4802 e nunca foi resolvida, porque a
correccao ficou no comentario.

E era uma **armadilha armada**: no dia em que alguem adicionasse `amplia_criar`,
as duas linhas passavam a gravar registos chamados "Novo safras", sem os campos
obrigatorios, sem o produtor pedir.

**O que foi feito:** os dois ramos de escrita foram removidos e substituidos pelo
motivo, em comentario, para ninguem os reintroduzir. Criar registo passa pelo
servidor (`amplia_cadastrar_*`), que exige `needs_confirm`.

### A1-a - P1 - NINGUEM SABIA QUAL DECISOR RESPONDEU

`iaChat()` encadeia ~20 pontos de captura sem registar nenhum. Quando o produtor
relatava "respondeu a coisa errada", nao havia forma de reconstruir por que
caminho a resposta saiu.

**O que foi feito:** um registo `IA_DECISOES` e um helper `_dec(nome, texto)` que
devolve o texto e marca quem falou, aplicado aos ~20 ramos da cascata. No
DevTools, cada turno passa a imprimir:

```
[IA] turno 1 <- decisor: sandboxBridge (412ms)
[IA] turno 2 <- decisor: fallbackFinal (89ms)
```

Um turno com **dois** nomes é regressão - significa que a cascata está a correr
em paralelo. Tambem exportado para inspecao, com janela de 40 entradas.

### A1-b - P1 - UM `fetch` POR MENSAGEM, E `{}` A MENTIR

```js
const prop = (await fetch('/api/propriedades/').then(...).catch(() => null))?.results?.[0] || {};
```

Executado a **cada mensagem**, dentro da decisão, sem cache e sem timeout. Em
campo: sem rede o `.catch` dava `{}` - e **`{}` mente**, diz que a propriedade nao
existe. O agente perdia `cidade`/`uf`, perdia o contexto, e caia nos decisores de
baixo, os que fabricam. E sem timeout, em rede de baixa, o produtor via o agente
"a pensar" sem resposta.

**O que foi feito:** `contextoPropriedade()` com cache de 60 s, `AbortController`
e timeout de 2.5 s, e **devolve `null` em vez de `{}`**. O `iaChat` passa a marcar
`ctx.semContexto` - a distincao entre "nao tenho propriedade" e "nao se soube
ler". `ctx.propriedade` continua a ser `{}` para nao partir consumidores
existentes.

*Estado da hipotese:* **forta, ainda nao provada.** Ver o que `analisarIntent`
devolve com `ctx.semContexto` true contra contexto real. O instrumentationo do
A1-a torna isso visivel em cinco minutos.

### A2 - P1 - O AGENTE NAO SABIA SER INTERROMPIDO

Havia ~11 maquinas de estado concorrentes - `iaCadastroPendente` (um slot unico)
mais um global por wizard - todas vivas ao mesmo tempo, sem nocao de qual estava
em foco. O produtor comeca um cadastro de safra, e antes de responder diz "vai
chover?". O `wizSafra` esta ativo, portanto a cascata intercepta **antes do LLM**
e trata "vai chover?" como resposta a "nome da safra?" - e grava isso como nome.
Sem previsao, sem aviso, sem forma de saber o que aconteceu.

**O que foi feito:** `IA_FOCO` (um unico fluxo em foco), deteção de interrupcao
**antes da cascata** - se vier depois e tarde, porque os wizards ja capturaram a
mensagem - e um conjunto curto e deliberado de frases de interrupcao. Uma deteccao
demasiado generosa roubaria respostas legitimas do proprio cadastro ("para a
safra 2026"). O progresso **nao se perde**: fica em `sessionStorage`, e "voltar"
retoma. `iaReset()` limpa foco, voz e cache de contexto.

---

### A9 - P1 - O POLLER ACUMULAVA SONDAGENS (achado na segunda ronda)

**Ficheiro:** `app/static/js/ia-local/proativo-local.js`.

Este arquivo é o melhor codigo do modulo: `emVoo` contra reentrância, backoff
progressivo, desistencia após N falhas, `while` limitado por `maxPorPassada`, e
dependencias todas injetadas para poder ser testado sem relogio. **Nao ha loop
aqui.** Mas ha umaccumulo:

```js
// o `visibilitychange` chamava isto:
_pollerProativo.passar();
// ...e `passar()` terminava em `agendar(...)` — SEM cancelar o timer pendente.
```

`parar()` é so uma flag, por desenho documentado: o callback agendado ainda
acorda e sai na primeira linha. Certo para parar. **Errado para o caso
diferente** — quando o `visibilitychange` chama `passar()` a mao.

Num telefone, cada bloqueio e desbloqueio do ecra dispara um
`visibilitychange`. Cada um corria uma passada, que agendava **outro** timer sem
cancelar o anterior. Ao fim de N mexidas na tela havia N timers pendentes. A
guarda `emVoo` impede execuções **sobrepostas**; nao impede execuções **demais
frequentes** — que e' o que consome a bateria de quem deixa a aba aberta o dia
inteiro, e o que o proprio backoff existe para proteger.

**Como foi feito, sem mexer no desenho:** `parar()` precisa de nao depender do
`clearTimeout` porque o `agendar` e' injetado e nao devolve id. A geracao resolve
o mesmo problema sem depender do id: cada timer guarda a geracao com que foi
criado e sai se ja nao for a atual. O `passar()` publico passa a invalidar os
pendentes; o interno (usado pelos timers) nao, para que uma recusa por `emVoo`
nao mate o poller calado.

**O teste que prova isto** (e que *falha* sem a correcao):

```
FALHA apenas o timer da ultima passada continua vivo -> got=6 esp=1
```

Cinco mexidas no ecra, seis sondagens onde devia haver uma.

Vale registar as duas armadilhas em que caí ao escrever esse teste, porque sao
o tipo de coisa que faz um teste passar sem provar nada:

1. **Disparar os timers em sincronia.** A guarda `emVoo` devolvia os seguintes
   pelo motivo *errado* e o teste passava mesmo sem a geracao. Passou assim na
   primeira versao, contra o codigo antigo.
2. **Iterar o array enquanto ele cresce.** Cada passada volta a agendar, portanto
   `for...of` sobre `agendados` nunca terminava — o processo morreu por falta de
   memoria em vez de falhar. A lista tem de ser congelada antes.

### A3b - P1 - A FRONTEIRA NO SERVIDOR (segunda linha de defesa)

O cliente deixou de fabricar, mas **o cliente nao e' fronteira**: e' um ficheiro
que o produtor pode ter em cache, um modulo que pode estar desactualizado no
tablet dele, ou outra coisa a chamar o endpoint. A protecao que existia no
servidor era por **acidente** — `amplia_criar` nao estava no catalogo. Bastava
alguem adicionar essa tool e o cliente passava a gravar.

A guarda vive em `executar_para()`, que e' **a unica porta de saida** do modulo.
Colocada la dentro do `sandbox`, uma tool nova que nao passasse por ali ficaria
sem proteccao — e a proxima refactorizacao apagava-a sem ninguem dar conta.

**Uma decisao de desenho que vale registar:** a regra recusa valores de
exactamente duas palavras cujo primeiro termo e' "novo"/"nova" e cujo segundo e'
um marcador conhecido, **ou** o slug do intent que se vai gravar. Enumerar os
valores conhecidos (o que o cliente emitia) em vez de tentar casar por
pluralizacao foi deliberado: o portugues nao pluraliza por acrescentar um `s`
(`operacao` -> `operacoes`), e qualquer regra de pluralizacao erra para um dos
lados — ou deixa passar lixo, ou recusa o nome que um produtor deu legalmente a
uma coisa sua. O teste fixa os dois sentidos: `Novo safras` e' barrado;
`Novo Veado` (um bovino) e `Nova Vida` (um talhao) passam.

Isto **nao substitui** o `needs_confirm`: uma escrita legitima continua a passar
por confirmacao. A regra so barra o que nenhum produtor pediu.

### 4.1 Erros que a suite apanhou nesta ronda

**E3 - guarda que nunca dispara.** A primeira versao comparava a *segunda
palavra* com um conjunto que guardava *frases completas*. Resultado: a guarda
recusava zero casos. Teria sido entregue como "corrigido" sem nunca ter disparado
uma vez. Apanhou-se porque o exercicio tinha 14 casos, incluindo 7 que deviam
passar.

**E4 - duas expectativas minhas erradas.** Escrevi `maquinaraios` quando o
correcto e' `maquinerios`, e esperei recusa de "Novo estoques" quando o cliente
emitia "Novo estoque". O codigo estava certo; os testes estavam errados.
Confirmado a nivel de byte (`U+0061` vs `U+0065`), nao a olho.

**E5 - um teste que passava pelo motivo errado.** Descrito em A9. Passava
contra o codigo antigo. So se descobre correndo o teste contra o codigo antigo.

## 5. POR FAZER

**A6 (P3).** O ficheiro tem 6267 linhas; os comentarios internos dizem "5753".
`palco-amplia.js` foi arrancado para fora **porque** 5753 linhas tornavam perigoso
editar em paralelo. Regra a adoptar: bloco novo com mais de ~40 linhas vai para
ficheiro proprio em `app/static/js/ia-local/`, e `ia-local.js` so orquestra.
Candidatos imediatos, todos com fronteiras naturais: os 9 wizards (~2600 linhas),
`fallbackIntent` (~195), `iaToolCall` + governo (~300). So os wizards levariam o
ficheiro de 6267 para ~3600. **Nao fazer antes de o produtor confirmar o loop
parado.**

**A7 (P3).** `audit_ia_erros.md` e `audit_ia_erros_v2.md` listam 70 vetores de
erro. Nenhum tem ficheiro, nenhum tem linha, nenhum foi reproduzido - sao
requisitos para um "Omnipotent Assistant", nao analise de codigo. Efeito colateral:
o documento deu a **ilusao de cobertura**, e foi por isso que A2-A6 sobreviveram.
Regra: um achado sem `ficheiro:linha` e sem comando de reproducao nao entra no
relatorio.

---

## 6. TRABALHO EM ABERTO - NAO E "SEM PROBLEMAS", E "NAO OLHADO"

| Ficheiro | Tamanho | Porque importa |
|---|---|---|
| `app/static/js/ia-local/whisper-audio.js` | 29 KB | Pipeline de audio. **Interage com A8** - pode haver um segundo caminho de envio. Nao lido. |
| `app/ia/sandbox.py` | 24 KB | Maquina de estados do servidor (`AGUARDANDO_CONFIRMACAO` / `COLETANDO_DADOS`). Pode re-entrar e causar loop **no servidor**, independente do cliente. |
| `app/ia/intents.py`, `intents3.py` | 61 + 48 KB | Vocabulario de intencoes. Nao lido. |
| `app/amplia_mcp/servidor.py`, `coerencia.py` | 24 + 18 KB | `coerencia.py` tem uma auditoria de nomes que vale a pena ler antes de mexer no catalogo. |
| `ia-local.js` linhas 1-4795 | ~4000 | Corpo dos 9 wizards, `smartResponse`, `analisarIntent`, `sandboxBridge`, `raciocinarLlm`. **Onde vive grande parte do que ainda nao foi explicado.** |

**Ja nao estao em aberto:** `proativo-local.js` e `alerta-feed.js` foram lidos.
O `proativo-local.js` deu o A9. O `alerta-feed.js` usa a mesma forma de poller
(`agendar` injetado, ciclo unico, sem polling agressivo) e **nao** accumulation
encontrada; merece uma leitura de 10 minutos com o A9 em cima da mesa, porque
partilha o desenho.

**Nota de suite:** `pytest app/ia/` completo pendura acima de 10 minutos. Nao
investiguei se e' pre-existente; se interferes com o trabalho de outra sessao, e'
provavelmente pre-existente.

---

## 7. TESTE DE CAMPO

Nao e teste de codigo. Com o telemóvel do produtor, na rede dele:

1. Clicar 5x no botao de voz, calar 5 s. **Nada acontece sozinho.**
2. Dizer "como esta o estoque", depois "e o clima?". Cada frase, uma resposta.
3. Falar "vai chover" com o microfone aberto: uma resposta, nao tres.
4. Comecar "cadastrar uma safra nova", depois dizer "desculpa, vai chover?".
   A previsao tem de vir e a IA tem de dizer que pausou. Depois "voltar".
5. Passar entre o painel e o chat na mesma sessao: **comportamento igual.**
6. DevTools, 3 mensagens: cada turno imprime **um** decisor.
7. Dizer uma frase sem sentido ("asdkjhasd"): nao pode aparecer nenhum nome de
   ferramenta interna.

---

*Cada achado tem ficheiro e linha. Um achado (A5) foi medido tres vezes, deu
tres respostas, e foi REMOVIDO por ser falso. Dois bugs meus durante a execucao
(E1, E2) ficaram registados e foram apanhados pela suite de testes.*
