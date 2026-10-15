# Unificação do Ampliagro — estado e evidências

**Data:** 07/10/2026. Revisão de alinhamento com `docs/VISAO.md`.

---
## 0. O QUE ESTE DOCUMENTO NÃO É

Não é sobre unificar "ferramentas do agro". O diferencial do Ampliagro é a **camada de proveniência dos dados**.

> **Pergunta que o Ampliagro responde e nenhuma outra responde:**
> **Este número foi medido, ou alguém disse que era?**

Um produtor escreve "65 sc/ha". Isso é `declarado`, **não** `medido`. A ZARC da Embrapa também é `declarado`, com `fonte="Embrapa — ZARC"` ao lado da data — o campo `fonte` diz de onde veio a janela de plantio, não "o sistema". Nenhuma empresa de software agro global faz esta distinção. `app/validators.py` e migrations 0061-0062 registram o vocabulário:

```
medido | declarado | sem_dado | suspect | simulado
```

O abismo que esta distinção tem de fechar: **709 culturas no catálogo, 0 registos
em ZARC.** O catálogo está cheio e o primeiro ecrã está vazio. É por isso que o
produtor desiste — e não é por causa do `sem_dado`.

Filosofias são baratas de copiar. Este documento assume que será — e por isso a §5 não depende de originalidade, depende de aplicação diária.

**Este documento é a §3 da `docs/VISAO.md` (a sequência) com o estado medido de
cada fase.** Onde os dois divergirem, a `VISAO.md` tem razão e esta é que está errada.

## 1. FASE 0 — DEIXAR DE MENTIR AO DISCO (NÃO COMPLETADO)

Antes de qualquer função nova. Não há porquê adicionar uma capacidade a um sistema que já grava mentira.

| Problema | Local | Evidência | Correção necessária |
|---|---|---|---|
| Escrita de dados falsos | `app/views/operario.py:68-112` | Renderizar página de produtor sem tarefas cria 6 `TarefaEstagio` falsas + 1 `RegistroProducao` `"Demo"` | Teste: abrir BD, contar antes/depois — **não deve criar nenhuma linha** |
| Revogação não propagada | `servidor.py:196,239,275`, `operario.py:21` | 4 de 5 rotas de `/servidor/` não checam `ativo_servidor` | `app/tests_servidor.py:286` deve iterar **todas** as rotas |
| Falha aberta concede privilégio | `operario.py:38-41` | `except Exception: is_servidor = True` | Falha deve: exceção no perfil → `is_servidor=False`, redirecionar |
| Scanner nunca corrido | — | Nenhum `sast`/`semgrep`/`astgrep` executado | **OBRIGATÓRIO** antes de qualquer outra fase |

**Status: FALHOU.** `operario.py:68-112` continua a escrever sem `fonte_dado`. Sem scanner determinístico, **nenhuma fase abaixo é verificável.** A regra que torna isto obrigatório: qualquer fase nova que escreva na base de dados passa a ter de declarar `fonte_dado` na mesma passagem. Sem `fonte_dado`, a escrita não entra.

---

## 2. FASE 1 — PRIMEIRO MINUTO, SEM INVENTAR NADA (NÃO COMPLETADO)

O produtor abre a aplicação e não vê nada. Não é culpa do `sem_dado` — é falta de material de origem verificável no primeiro ecrã.

| Item | Estado | Critério de saída |
|---|---|---|
| ZARC semeada com fonte real | Não semeada | `tests/test_zarc_regiao.py` passa e **varre o JSON à procura de qualquer ISO date** com a ZARC vazia |
| "Estou em Passo Fundo, o que posso plantar?" | Endpoint `/api/zarc/para_minha_regiao/` existe mas retorna vazio | Produtor escreve município + recebe culturas e janelas, sem escolher cultura primeiro |
| Importar o que já existe | Não implementado | Um produtor com 5 safras em papel chega a um painel em menos de 2 minutos, sem digitar 40 campos |
| Painel com `declarado` visível | Não implementado | Produtor reconhece o próprio número e vê que está marcado como `declarado`, com a fonte ao lado |

**Status: FALHOU.** O que NÃO entra na Fase 1: qualquer widget novo, qualquer mapa novo, qualquer notificação nova. A Fase 1 é sobre **material de origem**, não sobre superfície.

---

## 3. FASE 2 — PROVENIÊNCIA QUE ALGUÉM PAGA (NÃO INICIADA)

A Fase 2 não produz superfície: produz **a prova de que a Fase 1 é verdadeira**.
Só entra depois da Fase 1 fechar, e o que entra é a exportação com origem
declarada por campo — não um widget novo.

| Item | O quê | Critério de saída |
|---|---|---|
| 2.1 | Exportação GlobalG.A.P.: cada campo com `fonte_dado` e `fonte` no documento | Um inspetor distingue o que foi medido do que foi importado **sem perguntar ao sistema** |
| 2.2 | Custo por hectare, por talhão, por safra — com `fonte_dado` por linha | `custo_ha` que é `None` quando não há despesa **continua** a ser `None`. É o contrato do `console.md` s1/s2 e não se toca |
| 2.3 | O comprador pede o dado | Um comprador real pede o rasto e o sistema responde com `fonte_dado` por campo |

**Status: NÃO INICIADA.** Nenhum dos três itens tem critério cumprido. A
conformidade LCDPR está em andamento (`test_lcdpr_rotas_unificadas.py`,
`test_lcdpr_consolidado.py` existem), mas **LCDPR é obrigação legal — não é a
Fase 2**. A Fase 2 mede-se por um terceiro a pedir o rasto, e esse pedido ainda
não existe.

**Falsificador desta fase (F2).** Se, com a Fase 2 completa, ninguém pedir o
rasto, então `fonte_dado` é boa prática de engenharia e não posicionamento de
mercado. Nesse caso o Ampliagro é um sistema de gestão honesto e BOM — e o
pitch tem de dizer isso em vez de prometer mais.

---

## 4. FASE 3 — A MÁQUINA (NÃO INICIADA)

Só entra quando o sensor é real e o dado entra com a sua origem.

| Item | Estado | Pré-condição |
|---|---|---|
| ZARC/Janelas próprio talhão | Não | Fase 1 completa |
| NDVI/Sentinel-2 | Não | Fonte nomeada e datada; nunca interpolação sem `fonte` |
| IoT/LoRa/sensores | Não | `Device` + `TelemetryData` com `fonte_dado: medido` e `device_eui` |
| Integração máquina (CAN/ISOBUS) | Não | Depende de 3.3 |

**Status: NÃO INICIADA.** A pré-condição de 3.1 é a Fase 1 completa: uma janela
de plantio gerada é uma recomendação de risco climático falsa.

## 5. FALSIFICADORES

Uma visão sem falsificador é um destino, e um destino não se mede. Estes são
condições que **anulam a visão** (a §2 da VISAO.md) — não são riscos de qualidade.

**F1 — Se o produtor continuar a não adotar depois da Fase 1 completa.**
Com ZARC semeada, import de Excel e `declarado` visível, se fechar a aplicação
no primeiro minuto, **o problema não é material de origem — é outro, e ainda não
o identificámos.** É o mais importante e o mais desvalorizado: a Fase 1 tem de
poder falhar.

**F2 — Se ninguém pagar por proveniência.**
Se, depois da Fase 2, nenhum comprador, cooperativa ou instituição de crédito
pedir o rasto, `fonte_dado` é boa prática de engenharia e não posicionamento de
mercado. O Ampliagro é um sistema de gestão honesto e BOM — e o pitch tem de
dizer isso, não mais.

**F3 — Se um concorrente maior adicionar `fonte_dado`.**
É o cenário mais provável e o mais barato para eles: **é uma coluna.** Não
construir nada à volta disso. Construir à volta do que o comprador **paga** — a
procedência — que exige anos de registo com `fonte_dado` correto e é barreira
de saída real.

**F4 — Se a Fase 0 não fechar.**
Se `operario.py:68-112` continuar a escrever dados falsos depois de duas
tentativas, o problema não é o ficheiro: é que **ninguém tem o direito de dizer
não ao que já está feito.** É coordenação (`ESTADO.md` §5), não código.

**Regra:** todo dado tem `fonte_dado` declarado e rastreamento completo da
entrada à saída. Sem `fonte_dado`, a escrita não entra.

---

## 6. PORTÕES E VERIFICAÇÕES

Não são métricas (§8 mede o produto). São condições que têm de estar verde
antes de chamar uma fase de fechada — e é verde **com o comando colado**, não
herdado de outra sessão.

1. **Fase 0** — Verificar que `operario.py:68-112` não crie dados falsos. Teste: abrir BD, contar antes/depois — **não deve criar nenhuma linha**.
2. **Fase 1** — Verificar que ZARC seja semeada com fonte real. Teste: `tests/test_zarc_regiao.py` varre JSON à procura de ISO dates com ZARC vazia.
3. **Scanner executado** — `sast scan_all` + `semgrep` + `astgrep` rodados, resultados colados no `console.md`, antes de qualquer nova fase.
4. **Falhas de permissão** — `operario.py:38-41` deve converter exceções em `is_servidor=False`.
5. **Exportação** — `test_lcdpr_rotas_unificadas.py`, `test_central_gestao.py`, `test_lcdpr_consolidado.py` devem passar.

---

## 7. NÃO FAZER

Regras de conteúdo:

- Não gerar conteúdo para cumprir metas (metas são para auditoria, não para produção).
- Não adicionar funcionalidades sem primeiro garantir a fase anterior.
- Não modificar o esquema de dados sem revisão de segurança.
- Não aceitar a baseline de volume (`tests/estudo_volume.py --aceitar`) — fixa o crescimento do pipeline numa baseline. Decisão do dono.
- Não decidir `login.css` nem os 273 MB de `docs/super-estudo-globo-rural/`. São do dono.

Regras de coordenação — estas já custaram tempo medido:

- **Não `git add -A`.** Quatro sessões bateram nisto; uma comitou por cima de 158 ficheiros alheios. Use caminhos explícitos.
- **Ler o `git diff --cached --name-only` antes de comitar.**
- Uma sessão = um slot do `console.md` (`s1`–`s11`).

Regras de edição:

- **Não usar `edit` em ficheiro grande** (acima de ~50 KB): reescreve o ficheiro e pode introduzir uma linha em branco em cada linha. Um ficheiro cresceu de 26.606 para 47.633 linhas assim.
- **Não escrever caracteres CJK em comentários.** Quatro sessões o fizeram e já há um ficheiro de teste corrompido na árvore por isso. Português ou ASCII.
- **Não tocar em `base.py` sem ler o comentário.** `CACHES` é `DatabaseCache` porque o `LocMemCache` fazia o painel voltar a um número antigo com autoreload.
- **Se o `mtime` do ficheiro é de outra sessão nos últimos 30 minutos, mudar de ficheiro.** Seis incidentes de coordenação.

---

## 8. MÉTRICAS QUE MANDAM

Duas, e só duas. As restantes da §6 são **portões** — têm de passar, mas não
medem nada sobre o produto.

1. **O primeiro minuto.** Tempo até o produtor ver algo que reconheça como
   dele, sem digitar. Hoje: **não chega ao ecrã.**
2. **Taxa de `fonte_dado` nas escritas.** Quantas linhas na base de dados
   declaram a sua origem. Meta: 100%. Hoje: **não medida** — e
   `operario.py:68-112` escreve sem declarar.

Número de widgets, de culturas, de rotas, de linhas de documentação é
**métrica de vaidade**, e esta base de código já mediu o que acontece quando uma
delas vira o alvo: 273 MB de repetição com URLs a dar 404.

---

## 9. CONCLUSÃO

A unificação do Ampliagro é a **camada de proveniência** — a que separa o número
medido do número que alguém disse. Cada fase tem critério de saída verificável;
sem ele a fase não passou. Este documento é um plano de execução com portões, não
uma previsão.

*Versão:* 07/10/2026
*Responsável:* Equipe de Produto e Compliance
*Próximo passo:* escrever o critério de saída da Fase 0 no seu slot do
`console.md` **antes** de codificar, e depois medir o scanner
(`sast scan_all` + `semgrep` + `astgrep`) colando o resultado no mesmo slot.
`manage.py check` verifica configuração Django — não valida a Fase 0 nem a 1, e
não substitui o teste que abre a base de dados e conta as linhas antes/depois.