"""Sandbox da IA local: executa intents com flags auditadas e CACHE.

- Toda execução vira IAExecucao (intent, params, flags, fontes, via, ok/erro, duracao_ms).
- Resultados úteis viram IAArtefato (artifactory no BD do sistema).
- Cache por intent (TTL): clima e leituras não refazem HTTP/queries a cada pergunta.
- Auth: sessão do painel (via=sessao) ou X-IA-Key (via=chave, serviços locais).
"""

import hashlib
import json
import logging
import re
import time
import unicodedata
from typing import Any

from app.ia.registro import REGISTO as INTENTS

logger = logging.getLogger(__name__)
from app.ia.texto import prompt_de_confirmacao

# Onde este `import` estava, e porque mudou.
#
# Antes: `from app.ia.intents import INTENTS` — o primeiro catalogo, e so
# ele. Os intents que vivem em `intents2.py`, `intents3.py` e `intents4.py`
# existem, tem handler, e sao executaveis se chamados pelo nome certo —
# mas o sandbox nao os conhecia.
#
# `intents.py` turned out to be an AGGREGATOR: tem os 76, e portanto o
# bug estava latente, nao ativo. Mas "hoje" e' a palavra que faz este
# comentario valer a pena. Um `intents5.py` amanha, escrito direito e
# registado em lado nenhum, seria invisivel para a IA — e a IA nao tem
# como o adivinhar. Faltava-lhe, nao uma correccao, uma capacidade: a de
# descobrir o que existe.
#
# `app.ia.registro` descobre os catalogos por introspeccao, e junta-los e'
# trabalho de uma linha que nao se esquece. Isto mantem o sandbox como o
# caminho de execucao — um segundo caminho seria o bug que esta camada
# existe para fechar.

# TTL do cache por intent (segundos) — latência: 2ª pergunta igual responde na hora
# Os intents de `copiloto.INTENTS_DE_TEMPO` NAO podem ter cache.
#
# A resposta a "vai chover?" nao e' so o tempo: o sandbox acrescenta-lhe o
# copiloto, e o copiloto responde "Quer que eu remarque para dia 08/10?".
# Isso e' uma DECISAO sobre as aplicacoes pendentes. A chave do cache
# (`ia:v1:{user}:{intent}:{sha256(params)}`) nao inclui o estado das tarefas,
# portanto o cache guardava uma decisao tomada com o estado de ha 15 minutos.
#
# O produtor Remarkava a tarefa e, a pergunta seguinte, recebia de novo a
# oferta a apontar para uma tarefa que ja nao existia.
#
# A regra que ja valia para `listar_tarefas` ("reflete conclusao imediata")
# vale para estes tambem. O que se perde e' um fetch de previsao; o que se
# evita e' dizer ao produtor que a tarefa e' outra.
CACHE_TTL = {
    "clima_agora": 0,
    "vai_chover": 0,
    "previsao_estendida": 0,
    "melhor_pulverizar": 0,
    "ultimas_aplicacoes": 0,
    "status_sensores": 120,
    "ultima_leitura": 60,
    "resumo_safra": 300,
    "resumo_financeiro": 300,
    "consultar_estoque": 300,
    "listar_tarefas": 0,  # Sem cache: reflete conclusão imediata
    "contar_animais": 300,
    "resumo_aquatico": 300,
    "resumo_talhoes": 300,
    "listar_funcionarios": 300,
    "listar_culturas": 300,
    "dados_propriedade": 300,
    "historico_talhao": 300,
    "ajuda": 3600,
    # lote 2: leituras de domínio (só banco local, herméticas)
    "listar_maquinas": 300,
    "revisao_maquinas": 300,
    "listar_insumos": 300,
    "estoque_baixo": 120,
    "monitorar_pragas": 300,
    "calendario_sanitario": 300,
    "producao_leite": 300,
    "piquetes": 300,
    "apiario_resumo": 300,
    "contas_a_pagar": 300,
    "saldo_contas": 300,
    # leitura pura: 2 contas x 10 lancamentos na janela de 3 dias. O custo
    # e' de LEITURA, e a janela e' pequena de proposito - se ela crescer,
    # o custo cresce e este numero tem de ser revisto.
    "conciliar_banco": 400,
    "fretes_abertos": 300,
    "ordens_compra": 300,
    "analise_solo": 300,
    "alertas_telemetria": 120,
    "listar_devices": 300,
    "racao_estoque": 300,
    # lote 3: escritas nunca usam cache (efeito colateral)
    "lucro_talhao": 300,
    "recomendacao_adubacao": 300,
    "alerta_pragas": 120,
    "relatorio_vacinacao": 300,
    "gerar_lcdpr": 300,
    "simular_cenario": 300,
}
# intents que NUNCA usam cache (escrita/ação física/feedback)
# `frozenset`, e nao `set`.
#
# MEDIDO 2026-10-05: `conftest.py` limpa, entre testes, qualquer atributo de
# modulo cujo nome comece por `_CACHE` ou **termine** em `_CACHE` — substitui-o
# por `type(valor)()`, ou seja, por um vazio. Esta lista chamava-se `SEM_CACHE`,
# o nome acabava em `_CACHE`, e o fixture apagava-a entre testes.
#
# Medido: `app/tests_wizard_pergunta.py::test_o_intent_nao_tem_cache` passava
# sozinho e falhava com os irmaos, com `'concluir_tarefa' not found in set()`.
# Nao era o teste nem este ficheiro: era o isolamento a apagar a lista.
#
# O nome passou a `INTENTS_NAO_CACHEAVEIS` (o primeiro nome, `INTENTS_SEM_CACHE`,
# tambem acabava em `_CACHE` e nao resolvia) e o tipo passou a `frozenset`,
# que o fixture nao toca. As duas coisas juntas fecham o buraco: um dado de
# politica e' imutavel por natureza, e imutavelidade aqui nao e' estilo — e' o
# que impede que o isolamento o destrua.
#
# Ver `conftest.py::_limpa_caches_de_modulo` e
# `tests/test_conftest_nao_apaga_dado_imutavel.py`.
INTENTS_NAO_CACHEAVEIS = frozenset(
    {
        "ligar_irrigador",
        "desligar_irrigador",
        "associar_tarefa",
        "concluir_tarefa",
        "feedback",
        # lote 3: escritas guiadas
        "editar_safra",
        "excluir_safra",
        "cadastrar_maquina",
        "registrar_manutencao",
        "registrar_vacina",
        "criar_ordem_compra",
        "editar_lancamento",
        # ─────────────────────────────────────────────────────────────────────
        # MEDIDO 2026-10-05: 20 intents que ESCREVEM nao estavam nesta lista.
        #
        # A lista foi mantida a mao enquanto a REGRA ja existe em
        # `somente_leitura()`: uma flag `write`, `create` ou `comando`. Duas
        # Ways de dizer a mesma coisa, e a que se esqueceu 20 vezes.
        #
        # O que acontece a um intent que escreve e' fixo: o `sandbox` responds com
        # o resultado em cache no prazo do TTL, e o handler NAO corre. O produtor
        # ouve "feito" sem ter sido feito. `remarcar_tarefa` e' o pior caso
        # porque adia uma data e o sistema confirma.
        #
        # `criar_entidade` e `inserir_registro` sao os mais expostos: sao o
        # "criador livre" e escrevem o que a pessoa pedir, sem tipo nem forma
        # conhecida. Um TTL nelas significa que "cria uma tabela de forgets" pode
        # dizer que ja existe.
        #
        # `tests/test_todo_intent_que_escreve_esta_sem_cache.py` guarda a lista.
        # Sem ele, o proximo intent de escrita volta a nascer de fora.
        "automatizar_aerador",
        "automatizar_bigbrother",
        "automatizar_hedge",
        "automatizar_moba",
        "automatizar_piquete",
        "automatizar_pivo",
        "automatizar_sap",
        "automatizar_spd",
        "cadastrar_funcionario",
        "cadastrar_talhao",
        "chamado_criar",
        "chamado_editar",
        "chamado_publicar",
        "criar_entidade",
        "emitir_alerta_proativo",
        "inserir_registro",
        "ligar_proatividade",
        "provisionar_endpoint_iot",
        "remarcar_tarefa",
        "revogar_endpoint_iot",
        # ─────────────────────────────────────────────────────────────────────
        # MEDIDO 2026-10-05, mais 2. `pagar_conta` e `registar_conta` chegaram
        # ao `INTENTS` com flag `write` e ficaram de fora desta lista.
        #
        # São os dois mais graves que possam faltar, e por uma razão que os
        # outros não têm: **pagamento**. Um `pagar_conta` respondido de cache
        # diz ao produtor que a conta foi paga e o dinheiro não saiu. Não é um
        # estado que se auto-corrige no refresh seguinte — é um produtor que
        # conta com o dinheiro que já não tem.
        #
        # `registar_conta` é menos grave (registo, não desembolso) mas é a
        # mesma classe: uma escrita servida de cache é uma mentira com TTL.
        #
        # A regra que já existia e que estes dois violaram: qualquer flag
        # `write`, `create` ou `comando` sai da cache. `somente_leitura()`
        # calcula essa regra — a lista é só a materialização, e materializar
        # à mão é o que falha. `tests/test_todo_intent_que_escreve_sem_cache.py`
        # é o que apanha.
        "pagar_conta",
        "registar_conta",
        # Escrevem no dashboard do produtor: nunca de cache.
        "preset_palco",
        "preset_editar",
        "preset_apagar",
        "widget_alterar",
        "recurso_alterar",
    }
)


def somente_leitura(intent):
    """True se o intent só lê (nenhuma flag de escrita/ação)."""
    flags = (intent or {}).get("flags", []) or []
    if not flags:
        return False
    return not any(re.search(r"write|create|comando", f) for f in flags)


# Trava leitura × escrita: pedido de CADASTRO nunca pode ser respondido
# com intent de leitura (ex: "cadastrar uma nova safra" caía no resumo_safra).
# Inclui typo comum "cantar" (cantar uma safra = cadastrar): nesse contexto
# agro, bloquear com orientação é sempre mais seguro que cuspir o resumo.
_RE_CADASTRO = re.compile(
    r"\b(cadastr\w*|cantar\w*|cria\w*|crie|registr\w*|adicion\w*|exclu\w*|delet\w*|apag\w*|edit\w*|atualiz\w*)",
    re.IGNORECASE,
)


def parece_cadastro(texto):
    """True se o texto tem verbo forte de escrita (cadastro/edição/exclusão).

    Particípios ("cadastrados", "concluída") NÃO contam: é consulta ao existente.
    """
    t = re.sub(r"\b\w+(ados|adas|idos|idas)\b", " ", texto or "", flags=re.IGNORECASE)
    return bool(_RE_CADASTRO.search(t))


# ── Perguntar por um campo, em português, com exemplos ─────────────────────
#
# Este mapa é o que faltava entre a IA e a pessoa. Onze campos pedidos por
# algum intent não tinham pergunta própria, e caíam num
# `f"Por favor, informe: {campo}."` — que é o código a admitir que não
# sabe o que perguntar, e a pessoa a adivinhar.
#
# O caso que dói é `tipo`. Ele é pedido tanto por `cadastrar_maquina`
# (trator, colheitadeira) como por outras coisas, e "informe: tipo" não
# diz qual das duas. Um produtor que quer registar um vaqueiro leu
# "informe: tipo", respondeu "vaqueiro" — que é a resposta certa para a
# pergunta ERRADA — e ouviu "tipo inválido".
#
# Cada entrada tem três coisas: o que se pergunta, o que a resposta pode
# ser, e um exemplo real. O exemplo é o que resolve a dúvida sem fazer a
# pessoa errar uma vez para aprender.

_PERGUNTAS_CAMPO: dict[str, str] = {
    "nome": "Qual é o nome?",
    "area": "Qual é a área em hectares?",
    "area_ha": "Qual é a área em hectares?",
    "area_plantada": "Quantos hectares vão ser plantados?",
    "cargo": (
        "Qual é a função? Exemplos: tratorista, vaqueiro, diarista, "
        "motorista, mecânico, caseiro, técnico agrícola."
    ),
    "tipo": (
        "Que tipo? Se for uma máquina: trator, colheitadeira, pulverizador, "
        "caminhão, plantadeira, drone ou implemento."
    ),
    "salario": 'Qual é o salário em R$? (ou escreva "a combinar")',
    "data_admissao": "Qual é a data de admissão? (ex.: 30/09/2026)",
    # `tarefa` e `data` chegaram com o `remarcar_tarefa`. Sem estas duas, o
    # produtor que-write "sim" ao copilito levava com um "Por favor, informe:
    # tarefa" — que e' o sintoma exacto que o teste `test_nenhum_campo_cai_no_
    # fstring` existe para apanhar.
    "tarefa": "Qual tarefa quer remarcar? (ex.: a aplicação de glifosato)",
    # `titulo` é `required_fields` de `associar_tarefa` (intents.py:1399).
    # Sem esta linha caía no f"Por favor, informe: titulo." — que obriga o
    # produtor a saber que o sistema chama "titulo" ao nome da tarefa.
    #
    # Os exemplos são os do intent: os `exemplos` de `associar_tarefa` já são
    # nomes de tarefa reais ("consertar a cerca", "vacinar o gado",
    # "aplicação de fungicida"), e são eles que a pessoa vai ler.
    #
    # Se outro intent adoptar `titulo` para outra coisa, isto passa a estar
    # errado da mesma maneira que `tipo` estava — é o caso que o override de
    # `_perguntar_por` trata. Hoje só `associar_tarefa` o pede (medido).
    "titulo": "Como se chama a tarefa? (ex.: aplicar herbicida, vacinar o gado)",
    "data": "Para que dia quer ficar? (ex.: 12/10/2026)",
    "valor": "Qual é o valor, em R$?",
    "safra": "De que safra? (ex.: soja 2026/27)",
    "talhao": "De que talhão? (ex.: T-01)",
    "campo": "De que campo? (ex.: taxa de aplicacao, ou equipamento)",
    "maquina": "De que máquina? (ex.: trator John Deere)",
    "descricao": "Descreva o que aconteceu, em uma frase.",
    "produto": "Que produto? (ex.: glifosato, ureia, vacina aftosa)",
    "fornecedor": "De que fornecedor? (ex.: Agroshop, Coopersanta)",
    "lancamento": "De que lançamento? (ex.: a nota de diesel de agosto)",
    "brinco": "De que animal, pelo brinco? (ex.: 142)",
    # O Chamado Amplia. Sem estas quatro, a pergunta que o `sandbox` fazia era
    # a genérica — "Para chamado editar, o que precisa de saber sobre preset?"
    # — que não é uma pergunta: é o nome do campo com as palavras trocadas. E
    # para `preset` era pior do que inútil, porque a resposta certa é UMA
    # palavra e o produtor tinha de a adivinhar.
    "preset": (
        "Em que preset? O único onde a IA pode escrever é o Chamado Amplia "
        "(chamado-amplia) — nos outros a IA só lê."
    ),
    "blocos": (
        "O que queres ver? Posso por texto, um número, um gráfico, uma tabela "
        "ou uma planilha. Diz o que precisa e eu escolho os blocos."
    ),
    "delta": (
        "O que queres mudar? Posso acrescentar, remover, substituir, "
        "reordenar ou reescrever um bloco."
    ),
    "acao": (
        "O que queres fazer? Posso publicar (abrir para edição), arquivar "
        "(fechar, e a IA só lê a partir daí) ou deixar em rascunho."
    ),
    # ─────────────────────────────────────────────────────────────────────
    # MEDIDO 2026-10-05: `pagar_conta` e `registar_conta` chegaram ao
    # registo com `required_fields` e sem pergunta. Um campo pedido sem
    # pergunta cai no `"Por favor, informe: <o nome do campo>"` — que é o
    # sintoma exacto que `test_nenhum_campo_cai_no_fstring` existe para
    # travar, e que volta por outra porta quando a lista não cobre o campo.
    #
    # A pergunta não diz o que responder — diz o que se quer, e o que uma
    # resposta tem de parecer. `id` é o identificador da conta: quem não
    # sabe qual é, precisa de ver a lista, não de escrever "id".
    "id": (
        "Qual é o identificador da conta? Precisa ser o número da conta "
        "bancária — se não souber, abre Contas e olhe qual quer pagar."
    ),
    "vencimento": (
        "Qual é a data de vencimento desta conta? No formato "
        "AAAA-MM-DD (por exemplo 2026-11-30)."
    ),
}


#: Uma RECUSA é uma resposta que não é resposta.
#:
#: MEDIDO 2026-10-04. A pergunta "Como se chama a tarefa?" respondida com
#: "não" guardava `titulo = "não"` e depois propunha ao produtor confirmar
#: uma tarefa chamada "não". A causa é o `for` da rama `COLETANDO_DADOS`,
#: que enche o primeiro campo vazio com `entrada.strip()` sem perguntar o que
#: a entrada é.
#:
#: A lista espelha o `wizNao` + o `WIZ_SEM_REGISTO` de `ia-local.js`, para
#: que o "não" diga a mesma coisa nos dois lados da conversa — o servidor e
#: o que manda na writes.
#:
#: Âncora no início, como lá: em português a negação é verbo/advérbio à
#: frente. "Medida de nada" continua a ser um título, e tem de continuar.
#:
#: NÃO inclui "qualquer": em `_perguntar_por` e nos wizards, "qualquer" é
#: resposta válida ("pode ser qualquer um"). Incluí-lo aqui transformaria uma
#: resposta honesta em cancelamento — o defeito oposto ao que se está a
#: corrigir, e pior, porque perde-se o dado.
#:
#: E o texto é dobrado para ASCII ANTES do `match`. MEDIDO: com "não" escrito
#: com cedilha, a lista — que só tem `nao` — não casava, e a recusa voltava a
#: ser o valor do campo. Escrever a lista com os acentos todos seria a mesma
#: coisa com o dobro do trabalho e mais um sítio para esquecer um: `naïvo`.
#: `_texto_sem_acento` é o que resolve os dois.
_RECUSA = re.compile(
    r"^(?:"
    r"nao|n|naum|nunca|jamais"
    r"|deixa|deixar|deixamos"
    r"|dispenso|dispense"
    r"|esquece|esqueceu"
    r"|cancela|cancelar|cancele"
    r"|sem\s+(?:isso|essa|este|esta|aquilo)"
    r"|melhor\s+nao"
    r"|por\s+(?:enquanto\s+)?nao"
    r"|para\s+(?:com\s+)?isso"
    r"|muda\s+de\s+(?:assunto|topico)"
    r")\b",
    re.IGNORECASE,
)


def _texto_sem_acento(texto: str) -> str:
    """A mesma do `voz.sem_acentos`, local porque aqui só se usa uma vez."""
    return "".join(
        c
        for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def _e_recusa(texto: str) -> bool:
    return bool(_RECUSA.match(_texto_sem_acento(texto.strip()).lower()))


def _perguntar_por(campo: str, intent_nome: str = "") -> str:
    """A pergunta por um campo, com o que uma resposta válida parece.

    A pergunta diz o que se quer. A lista de valores válidos diz o que
    uma resposta TEM DE PARECER — e é essa parte que impede a ida ao
    "tipo inválido" depois de a pessoa ter feito a melhor resposta que
    conseguia.
    """
    # o `tipo` precisa de saber de que intent veio: em `cadastrar_maquina`
    # a resposta é um equipamento, e dizer "trator, colheitadeira" ajuda.
    # noutro intent, o mesmo campo pode significar outra coisa — e aí a
    # pergunta tem de dizer qual, ou volta o mesmo erro.
    if campo == "tipo" and intent_nome and "maquina" not in intent_nome:
        return f"Que tipo de '{_legivel(intent_nome)}'? Diga em poucas palavras."
    return _PERGUNTAS_CAMPO.get(
        campo,
        # Último recurso: não repetir o nome do campo ao utilizador.
        # "Por favor, informe: xyz." obriga a pessoa a saber o que `xyz`
        # quer dizer; perguntar o que quer, e nao dizer o nome do campo, e
        # mais útil, mesmo sem o saber com precisão.
        f"Para {_legivel(intent_nome) or 'continuar'}, o que precisa de saber sobre "
        f"{campo.replace('_', ' ')}?",
    )


def _legivel(intent_nome: str) -> str:
    """`cadastrar_funcionario` -> `cadastrar funcionario`."""
    return (intent_nome or "").replace("_", " ")


#: O que se escreve ao lado de cada campo. NOME DO CAMPO, e nao legenda.
#:
#: MEDIDO: a primeira versao punha `nome: "como se chama"` e a lista saiu
#: "1 como se chama" — uma legenda que nao diz o que e'. Numa lista numerada o
#: rotulo e' o que identifica a LINHA, e "1 como se chama" obriga o produtor a
#: adivinhar o que e'. O rotulo tem de se ler sozinho: "Nome da safra".
#:
#: `_PERGUNTAS_CAMPO` continua a ser a fonte da PERGUNTA, que sao coisas
#: diferentes — e e' por isso que esta tabela existe em vez de se extrair de la.
_ROTULO_POR_CAMPO = {
    "cultura": "Cultura",
    "nome": "Nome da safra",
    "safra": "Safra",
    "area": "Área",
    "talhao": "Talhão/Zona",
    "ano": "Ano",
    "data": "Data",
    "responsavel": "Responsável",
    "quantidade": "Quantidade",
    "valor": "Valor",
    "local": "Local",
}


def _coleta_por_campo(intent_nome: str, campos: list[str], params: dict) -> list[dict]:
    """Os campos do pedido, na ordem, com o que ja' foi preenchido.

    POR QUE ESTA LISTA E NAO A PERGUNTA EM PROSA
    =============================================
    A tela que mostrou o problema fazia cinco perguntas seguidas: "Cultura? Nome
    da safra? Talhao? Ano? Area?". Cada uma era correcta e nenhuma era
    enganosa — mas o produtor tinha de as ler todas para saber quantas faltavam,
    e depois de responder a primeira nao sabia se faltava mais alguma.

    Numa lista, o que falta e' o que nao tem valor. E' a mesma informacao da
    prosa com a mesma fonte — `_PERGUNTAS_CAMPO` — so' que ordenada e contavel.

    O rotulo tem de ser um NOME, nao uma frase. De `_PERGUNTAS_CAMPO` tira-se
    a pergunta; daqui sai o que se escreve na linha. A pergunta COMPLETA continua
    em `resposta`: esta lista nao substitui a pergunta, acrescenta a ordem.
    """
    out = []
    for i, campo in enumerate(campos or [], start=1):
        valor = params.get(campo)
        preenchido = bool(valor)
        rotulo = _ROTULO_POR_CAMPO.get(campo)
        if not rotulo:
            p = _PERGUNTAS_CAMPO.get(campo, "")
            # Cortar a frase na interrogacao daria "Que talh" — pior do que nao
            # cortar. Sem pergunta escrita, o nome do campo capitalizado, que
            # e' melhor do que uma legenda que nao identifica nada.
            rotulo = (
                p.rstrip("?").strip() if p else campo.replace("_", " ").capitalize()
            )
        out.append(
            {
                "n": i,
                "campo": campo,
                "rotulo": rotulo,
                "valor": valor if preenchido else None,
                "estado": "preenchido" if preenchido else "a_pedir",
            }
        )
    return out


def _exige_confianca(intent):
    """True se o intent escreve/age (gate de confiança M3 se aplica)."""
    flags = (intent or {}).get("flags", []) or []
    return any(re.search(r"write|create|comando", f) for f in flags)


# Anti-injection (S1): tentativa de escalonamento de papel ("aja como gerente",
# "ignore suas regras") nunca executa nada. Não há LLM nem papel a sequestrar
# no servidor, mas a tentativa é barrada e auditada como bloco de segurança.
_RE_INJECAO = re.compile(
    r"\b(aja como|age como|finge (que |de )?(que |ser )?|ignore (suas|as) (regras|instrucoes|instruções)|"
    r"voce e (o |a )?(gerente|admin|dono|root)|você é (o |a )?(gerente|admin|dono|root)|sou (o |a )?(gerente|admin|dono|root)|"
    r"modo (deus|admin|root)|mostre (suas |as )?(regras|instrucoes|instruções)|prompt do sistema)",
    re.IGNORECASE,
)


def parece_injecao(texto):
    """True se o texto tenta escalonar papel ou extrair regras internas."""
    return bool(_RE_INJECAO.search(texto or ""))


# Gate de confiança (M3): escrita/ação física com score baixo de detecção
# não executa — vira pedido de confirmação (estado neutro, como needs_confirm).
_LIMIAR_ESCRITA = 0.60


def _score_escolhido(intent_nome, deteccao):
    scores = (deteccao or {}).get("scores") or {}
    try:
        return float(scores.get(intent_nome, 1.0))
    except (TypeError, ValueError):
        return 1.0


def _aviso_confianca(intent_nome, intent, deteccao):
    """O score de detecção, ou `None` se esta chamada não for subjecto a M3.

    MEDIDO, 2026-10-04: esta lógica estava escrita DUAS vezes, em dois
    caminhos, e as duas cópias podiam divergir sem nada as ligar. Pior: o
    caminho de `requires_confirmation` vivia DEPOIS do `return` do bloco de
    Human-in-the-Loop, ou seja, era inalcançável — o M3 só disparava para
    intents que NÃO escrevem, o inverso do seu público (`_exige_confianca`
    casa `write|create|comando`).

    O score NUNCA dispensa a confirmação: vem do cliente (ver
    `deteccao.py`: "Um cliente que mande `meta: {}` nunca passa pelo gate"), e
    um cliente não escolhe se a escrita é confirmada. O score só informa o
    texto, para o produtor não confirmar às cegas.
    """
    if not (deteccao and deteccao.get("scores") and _exige_confianca(intent)):
        return None
    score = _score_escolhido(intent_nome, deteccao)
    return score if score < _LIMIAR_ESCRITA else None


def _frase_confianca(intent_nome, score):
    return (
        f"Entendi '{intent_nome}' com confiança baixa ({score:.0%}) — "
        "se não era isso, diga o que quer dizer e eu pergunto outra vez."
    )


def _cache_key(user, intent_nome, params):
    bruto = json.dumps(params or {}, sort_keys=True, default=str)
    h = hashlib.sha256(bruto.encode()).hexdigest()[:24]
    return f"ia:v1:{user.id}:{intent_nome}:{h}"


def _passo(ctx, t0, etapa, detalhe=""):
    ctx.setdefault("passos", []).append(
        {
            "etapa": etapa,
            "detalhe": detalhe,
            "ms": int((time.perf_counter() - t0) * 1000),
        }
    )


def _registrar_execucao(
    user,
    intent_nome,
    entrada,
    deteccao,
    ctx,
    params,
    via,
    *,
    ok,
    duracao_ms,
    resposta=None,
    erro=None,
    fontes=None,
    flags=None,
    artefato=None,
    artefato_id=None,
):
    """Registo de auditoria de UMA execução, num único ponto.

    `executar` tem seis saídas — intent desconhecida, trava leitura×escrita,
    anti-injeção S1, gate M3, cache HIT e o handler real — e cada uma escrevia
    o mesmo `IAExecucao` com os mesmos oito campos comuns, repetidos. Reunir
    aqui significa que um campo novo ou renomeado passa a ser mexido num só
    sítio, e nenhum ramo pode esquecer `user`/`entrada`/`params` em silêncio.

    `duracao_ms` é sempre explícito: cada ramo mede o seu próprio instante (o
    HIT de cache prefixa `ms` antes de responder) e recalcular aqui daria um
    número diferente do que é devolvido ao cliente.

    `resposta`/`erro` a `None` significam "não escrever o campo" — fiel aos
    ramos originais, que passavam só um dos dois e deixavam o outro no default
    do modelo. `artefato` e `artefato_id` são o mesmo FK; só um é usado.
    """
    from app.models import IAExecucao

    campos = {
        "user": user,
        "intent": intent_nome,
        "entrada": entrada,
        "deteccao": deteccao,
        "passos": ctx["passos"],
        "params": params,
        "flags": flags or [],
        "fontes": fontes or [],
        "via": via,
        "ok": ok,
        "duracao_ms": duracao_ms,
    }
    if artefato_id is not None:
        campos["artefato_id"] = artefato_id
    else:
        campos["artefato"] = artefato
    if resposta is not None:
        campos["resposta"] = resposta
    if erro is not None:
        campos["erro"] = erro
    return IAExecucao.objects.create(**campos)


def executar(user, intent_nome, params, via="sessao", meta=None):
    from django.core.cache import cache

    from app.models import IAArtefato, IAEvento, IAExecucao

    t0 = time.perf_counter()
    params = params or {}
    meta = meta or {}
    intent = INTENTS.get(intent_nome)
    ctx = {"fontes": [], "passos": []}
    # Modos de criação vindos do cliente (chat/painel): SÓ apresentação
    # (gráfico no chat, peça no dashboard). Nunca decidem escrita, tenancy
    # ou confirmação — um cliente que minta aqui ganha no máximo um gráfico.
    # Lista ordenada (e não set): o ctx vai para o log de auditoria, e set
    # não é JSON.
    _modos = meta.get("modos") or []
    ctx["modos"] = sorted({m for m in _modos if isinstance(m, str)})
    entrada = str(meta.get("entrada") or params.pop("_entrada", "") or "")
    deteccao = meta.get("deteccao") or params.pop("_deteccao", {}) or {}

    # O SCORE É DO SERVIDOR, não do cliente.
    #
    # O `deteccao` chega no `meta`, e o `scores` que vem dentro é um número
    # que o cliente afirma. Confiar nele tornava o gate M3 (L~460) decorativo:
    # a condição era `deteccao and deteccao.get("scores")`, e um cliente que
    # mandasse `meta: {}` passava a pedir à granularidade que quisesse — ou
    # a não ter scores nenhum, e o gate não se aplicava.
    #
    # Agora: se o cliente não mandou scores, o servidor CALCULA os seus, com
    # `app/ia/deteccao.py`. O cliente continua a poder dizer o que entendeu —
    # a Interface é que sabe o que o produtor quis dizer — mas o número de que
    # o gate depende é do servidor. Se o cliente mandar scores, são usados, e
    # os calculados ficam registados ao lado para se compararem.
    if entrada and not (deteccao or {}).get("scores"):
        try:
            from app.ia.deteccao import detectar

            calculado = detectar(entrada)
            deteccao = {
                **(deteccao or {}),
                "metodo": calculado["metodo"],
                "scores": calculado["scores"],
                "calculado_no_servidor": True,
            }
        except Exception:  # noqa: BLE001 — nunca rebentar por causa da detecção
            logger.warning("[ia.sandbox] deteccao local falhou; segue sem scores")

    _passo(ctx, t0, "acesso", f"via={via}")
    if entrada:
        _passo(ctx, t0, "entendimento", entrada[:200])
    if deteccao:
        _passo(
            ctx,
            t0,
            "raciocinio",
            f"método={deteccao.get('metodo')} escolhido={deteccao.get('escolhido')}",
        )

    # 1. RECUPERAÇÃO DO ESTADO CONVERSACIONAL (STATE-MACHINE)
    #
    # SÓ QUANDO HÁ ENTRADA HUMANA — e esta linha é uma das mais importantes
    # deste ficheiro.
    #
    # A primeira versão recuperava o estado sempre que `estado_atual` não fosse
    # "NENHUM", INCLUINDO numa chamada sem `entrada`. Ou seja, num tool call
    # programático, que traz `tool` e `args` completos e não é resposta a nada.
    #
    # O que acontecia: uma pergunta que ficou pendente SECQUESTRAVA as
    # chamadas seguintes. O `chamado_editar` pedia o `delta`, e o próximo
    # `chamado_criar` — completo, explícito, com todos os blocos — recebia
    # "O que queres mudar?" e um `ok: true`. Nos testes do Chamado isso era uma
    # peça reescrita que nunca aparecia, e o `ok: true` dizia que tinha
    # corrido bem. Um `ok: true` que mente é pior do que um erro: o modelo
    # repete, o produtor vê a peça antiga e ninguém percebe porquê.
    #
    # A regra é a da natureza disto: uma máquina de estados conversacional
    # retoma-se com uma RESPOSTA. Sem `entrada` não há resposta, e portanto não
    # há nada a retomar — o intent pedido é que tem de correr.
    #
    # O estado pendente NÃO é apagado quando uma chamada programática passa por
    # aqui. Apagar seria deitar fora a pergunta que o produtor ainda pode
    # responder; e o próximo "sim" humano retoma o que ele perguntou, que é o
    # que ele espera. O que não pode é essa pergunta responder sozinha a uma
    # chamada que nada tem com ela.
    from app.models import IAContextoConversa

    contexto, _ = IAContextoConversa.objects.get_or_create(user=user)
    entrada_livre = entrada.strip()

    if entrada_livre.lower() in [
        "cancelar",
        "cancela",
        "pare",
        "parar",
        "esquece",
        "sair",
    ]:
        contexto.estado_atual = "NENHUM"
        contexto.intent_pendente = ""
        contexto.dados_coletados = {}
        contexto.save()
        return {"ok": True, "resposta": "Operação cancelada. Como posso ajudar agora?"}

    if entrada_livre and contexto.estado_atual == "AGUARDANDO_CONFIRMACAO":
        if entrada.strip().lower() in ["sim", "confirmo", "pode fazer", "ok", "isso"]:
            # Retoma o intent pendente. `params["confirm"] = True` é o que
            # destrava a execução: o gate de confirmação (abaixo) E os
            # handlers (intents.py, iot_intents.py, dinamico_intents.py)
            # testam `params.get("confirm")`. Sem marcar, um "sim" limpa o
            # estado, o gate dispara de novo na mesma chamada e o intent
            # nunca roda — loop infinito de "Você confirma...?"
            intent_nome = contexto.intent_pendente
            params = dict(contexto.dados_coletados or {})
            params["confirm"] = True
            intent = INTENTS.get(intent_nome)
            contexto.estado_atual = "NENHUM"
            contexto.intent_pendente = ""
            contexto.dados_coletados = {}
            contexto.save()
        else:
            contexto.estado_atual = "NENHUM"
            contexto.intent_pendente = ""
            contexto.dados_coletados = {}
            contexto.save()
            return {"ok": True, "resposta": "Operação cancelada."}

    elif entrada_livre and contexto.estado_atual == "COLETANDO_DADOS":
        # Assumir que a entrada é a resposta para o campo que estava faltando
        intent_nome = contexto.intent_pendente
        params = contexto.dados_coletados
        intent = INTENTS.get(intent_nome)

        # Uma RECUSA não é o valor do campo. MEDIDO 2026-10-04, conversando:
        #
        #   "cria uma tarefa para adubar o talhao"
        #     -> "Como se chama a tarefa?"
        #   "não"
        #     -> nome = "não"
        #     -> "Criar esta tarefa no cronograma? (Diga 'sim' ou 'não')"
        #
        # O sistema propôs ao produtor confirmar uma tarefa chamada "não".
        # O `for` abaixo é o culpado: guarda `entrada.strip()` no primeiro
        # campo vazio sem perguntar o que a entrada é.
        #
        # O alcance é largo: MEDIDO, **14** intents de escrita têm
        # `required_fields` (ver `registro.py`), e todos chegam aqui. Com
        # `cadastrar_funcionario`, "não" virava o `nome` do funcionário.
        #
        # Por que CANCELAR e não repetir a pergunta: é o que a rama irmã faz.
        # Em `AGUARDANDO_CONFIRMACAO` (linha 434) tudo o que não é "sim"
        # cancela. Uma recusa a "que safra?" não é um nome de safra — é
        # "não quero isto". E o cancelamento é reversível: o produtor volta
        # a pedir, e o pedido novo é limpo.
        #
        # A âncora no início é a mesma de `wizNao`/`wizDispensavel` em
        # `ia-local.js`: em português a negação é verbo/advérbio à frente.
        # "Nada" no meio de um título ("medida de nada") continua a ser título.
        if _e_recusa(entrada):
            contexto.estado_atual = "NENHUM"
            contexto.intent_pendente = ""
            contexto.dados_coletados = {}
            contexto.save()
            return {
                "ok": True,
                "resposta": "Operação cancelada. Como posso ajudar agora?",
            }

        # Identificar qual campo estava faltando (o primeiro vazio nos requeridos)
        req_fields = intent.get("required_fields", [])
        for campo in req_fields:
            if not params.get(campo):
                params[campo] = entrada.strip()
                break

        contexto.dados_coletados = params
        contexto.save()

    if not intent:
        ex = _registrar_execucao(
            user,
            intent_nome,
            entrada,
            deteccao,
            ctx,
            params,
            via,
            ok=False,
            duracao_ms=int((time.perf_counter() - t0) * 1000),
            flags=[],
            erro=f"intent desconhecida. Disponíveis: {', '.join(sorted(INTENTS))}",
        )
        return {"ok": False, "erro": ex.erro, "execucao_id": ex.id}

    # trava leitura × escrita (antes do cache: nem HIT pode vazar resumo p/ cadastro)
    if entrada and parece_cadastro(entrada) and somente_leitura(intent):
        erro = (
            "Isso parece um pedido de cadastro — resumo não cria nada. "
            "Recarregue a página (Ctrl+F5) e digite 'cadastrar nova safra' "
            "para o passo a passo guiado, ou abra o cadastro manual no menu."
        )
        ex = _registrar_execucao(
            user,
            intent_nome,
            entrada,
            deteccao,
            ctx,
            params,
            via,
            ok=False,
            duracao_ms=int((time.perf_counter() - t0) * 1000),
            flags=list(intent.get("flags", [])),
            erro=erro,
        )
        return {"ok": False, "erro": erro, "execucao_id": ex.id}

    # 2. VALIDAÇÃO DE CAMPOS (Function Calling / Coleta)
    req_fields = intent.get("required_fields", [])
    campos_faltantes = [c for c in req_fields if not params.get(c)]

    if campos_faltantes:
        campo_atual = campos_faltantes[0]
        contexto.estado_atual = "COLETANDO_DADOS"
        contexto.intent_pendente = intent_nome
        contexto.dados_coletados = params
        contexto.save()

        # PERGUNTAR POR UM CAMPO, EM PORTUGUÊS, COM EXEMPLOS
        #
        # O que estava aqui: um `perguntas` com DUAS entradas (`nome` e
        # `area`) e um `f"Por favor, informe: {campo}."` para o resto.
        #
        # A conversa de um produtor provou o que isso custa. Onze campos
        # pedidos por algum intent caíam nesse `f` — e `tipo` é um deles.
        # A pergunta que ele recebeu foi "Por favor, informe: tipo.",
        # seguida de "tipo inválido — use: trator, colheitadeira,
        # pulverizador, caminhão…", e "tipo" e' também o campo de MÁQUINA.
        # Ou seja: a IA perguntou o que queria saber COMO SE FOSSE
        # ÓBVIO, a pessoa respondeu "vaqueiro" (uma pessoa, não um
        # equipamento), e o sistema rejeitou.
        #
        # Duas coisas faltavam, e as duas são o trabalho de perguntar bem:
        #   1. o que o campo SIGNIFICA — "tipo" não se explica
        #   2. o que uma resposta VÁLIDA parece — sem exemplos, a pessoa
        #      adivinha o formato e erra
        #
        # Um `f"informe: {campo}"` é o código a admitir que não sabe o que
        # perguntar, e a pessoa a adivinhar.
        pergunta = _perguntar_por(campo_atual, intent_nome)

        return {
            "ok": True,
            "resposta": pergunta,
            "needs_confirm": False,
            "state": "COLETANDO_DADOS",
            # A LISTA, e nao so' a pergunta.
            #
            # A conversa que mostrou isto: a IA dizia "Vamos cadastrar uma
            # safra! Cultura? Nome da safra? Talhao? Ano?" — cinco perguntas
            # seguidas em prosa, e o produtor tinha de as ler todas para saber
            # quantas faltavam. `dados_coletados` ja' tem os campos preenchidos e
            # `campos_faltantes` tem os que faltam, portanto a LISTA e' a mesma
            # informacao que a prosa, so' que se pode ver e numerar.
            #
            # `resposta` continua a ser a pergunta em texto: e' o que o cliente
            # MCP e o telefone leem, e a lista e' um extra para quem tem ecra.
            "dados": {
                "coleta": _coleta_por_campo(intent_nome, req_fields, params),
                "faltando": list(campos_faltantes),
            },
        }

    # 3. HUMAN-IN-THE-LOOP (Confirmação Explícita)
    #
    # MEDIDO, 2026-10-04: o gate de confiança M3 (L561) era ALCANCÁVEL apenas
    # para intents que NÃO exigem confirmação — exactamente o inverso do seu
    # público. `_exige_confianca` casa `write|create|comando`, e todos esses
    # intents têm `requires_confirmation=True`, portanto este bloco devolvia
    # SEMPRE e a L561 nunca era alcançada. O M3 era código morto.
    #
    # A reconciliação NÃO é inverter a ordem (isso daria ao score — que vem do
    # CLIENTE, ver `deteccao.py`:13-16 — o poder de dispensar a confirmação de
    # uma escrita). É tornar o score INFORMATIVO dentro da confirmação que já
    # acontece: o produtor passa a saber que a máquina o entendeu com pouca
    # confiança, e pode corrigir em vez de confirmar às cegas.
    #
    # Ou seja: a protecção não foi afrouxada. A mensagem é que ficou honesta.
    if (
        intent.get("requires_confirmation")
        and contexto.estado_atual != "AGUARDANDO_CONFIRMACAO"
        and not params.get("confirm")
    ):
        contexto.estado_atual = "AGUARDANDO_CONFIRMACAO"
        contexto.intent_pendente = intent_nome
        contexto.dados_coletados = params
        contexto.save()
        # O TEXTO, e não a descrição.
        #
        # A `descricao` de um intent é escrita PARA O MODELO ("INSTRUÇÃO IA:
        # use para..."). Echoá-la ao produtor punha a única barreira antes de
        # apagar uma safra coberta de texto de engenharia. Ver
        # `app/ia/texto.py` para o porque de haver dois textos.
        #
        # E o score, quando é baixo, entra no texto. Antes isto não acontecia:
        # o M3 vivia DEPOIS deste `return`, em código morto. Confirmar sem
        # saber que a máquina o entendeu a 45% é confirmar às cegas.
        # MEDIDO 2026-10-05 (agente 9): era `prompt_de_confirmacao(intent)`.
        # Sem os `params`, o texto de confirmacao nao tinha como mostrar o ano
        # da safra, o valor da conta ou o brinco — e o produtor confirmava uma
        # descricao em vez de um objecto.
        _txt = prompt_de_confirmacao(intent, params=params)
        _score = _aviso_confianca(intent_nome, intent, deteccao)
        if _score is not None:
            _txt = f"{_frase_confianca(intent_nome, _score)} {_txt}"
        return {
            "ok": True,
            "resposta": f"{_txt} (Diga 'sim' ou 'não')",
            "needs_confirm": True,
            "state": "AGUARDANDO_CONFIRMACAO",
        }

    # anti-injection S1 (antes do cache: tentativa nunca aproveita HIT)
    if entrada and parece_injecao(entrada):
        erro = (
            "Não posso mudar de papel nem revelar regras internas. "
            "Você continua sendo você — diga o que precisa da fazenda."
        )
        ex = _registrar_execucao(
            user,
            intent_nome,
            entrada,
            deteccao,
            ctx,
            params,
            via,
            ok=False,
            duracao_ms=int((time.perf_counter() - t0) * 1000),
            flags=list(intent.get("flags", [])),
            erro=erro,
        )
        return {"ok": False, "erro": erro, "execucao_id": ex.id}

    # gate de confiança M3: escrita/ação com score baixo vira confirmação
    # (neutro, não erro) em vez de executar no escuro
    _score_m3 = _aviso_confianca(intent_nome, intent, deteccao)
    if _score_m3 is not None:
        score = _score_m3
        resposta = (
            f"{_frase_confianca(intent_nome, score)} "
            "Confirme com mais detalhes ou reenvie com confirm=true."
        )
        ex = _registrar_execucao(
            user,
            intent_nome,
            entrada,
            deteccao,
            ctx,
            params,
            via,
            ok=True,
            duracao_ms=int((time.perf_counter() - t0) * 1000),
            flags=list(intent.get("flags", [])),
            resposta=resposta,
        )
        return {
            "ok": True,
            "needs_confirm": True,
            "resposta": resposta,
            "execucao_id": ex.id,
        }

    # fast-path: cache
    ck = _cache_key(user, intent_nome, params)
    ttl = CACHE_TTL.get(intent_nome, 0)
    usa_cache = bool(ttl) and intent_nome not in INTENTS_NAO_CACHEAVEIS
    if usa_cache:
        hit = cache.get(ck)
        if hit and hit.get("artefato_id"):
            # artefato pode ter sumido (rollback/teste/limpeza): HIT órfão vira MISS
            if not IAArtefato.objects.filter(pk=hit["artefato_id"]).exists():
                hit = None
        if hit:
            ms = int((time.perf_counter() - t0) * 1000)
            _passo(ctx, t0, "busca", "cache: HIT — sem refazer HTTP/queries")
            ex = _registrar_execucao(
                user,
                intent_nome,
                entrada,
                deteccao,
                ctx,
                params,
                via,
                ok=True,
                duracao_ms=ms,
                resposta=hit.get("resposta", ""),
                flags=list(intent.get("flags", [])),
                fontes=["cache"],
                artefato_id=hit.get("artefato_id"),
            )
            out = dict(hit)
            out["cached"] = True
            out["execucao_id"] = ex.id
            out["duracao_ms"] = ms
            return out
        _passo(ctx, t0, "busca", "cache: MISS — executando handler")
    else:
        # O passo "busca" e' "fui buscar dados", e o sistema vai buscar
        # dados nos dois ramos. O que muda e' o detalhe: escrever
        # "cache: MISS" num intent que nao tem cache seria mentira, e quem
        # le a consola ha de poder confiar no que ela diz.
        _passo(ctx, t0, "busca", "sem cache — executando handler")

    # T1: handler + artefato + auditoria numa transação só — se o handler
    # criar metade (ex: plano sem atividade) e falhar, o savepoint volta
    # (sem órfãos) mas a auditoria do erro é preservada.
    from django.db import transaction

    with transaction.atomic():
        sid = transaction.savepoint()
        try:
            _passo(
                ctx,
                t0,
                "leitura",
                f"handler={intent_nome} flags={','.join(intent.get('flags', []))}",
            )
            res = intent["handler"](user, params, ctx) or {}
        except Exception as e:
            transaction.savepoint_rollback(sid)
            res = {"ok": False, "erro": f"falha interna: {e}"}
        artefato_obj = None
        if res.get("ok") and res.get("artefato"):
            chave, tipo = res["artefato"]
            artefato_obj, criado = IAArtefato.objects.update_or_create(
                user=user,
                chave=chave,
                defaults={
                    "tipo": tipo,
                    "dados": res.get("dados", {}),
                    "origem": intent_nome,
                },
            )
            _passo(
                ctx,
                t0,
                "edicao",
                f"artifactory {'criou' if criado else 'atualizou'} {chave}",
            )
        ms = int((time.perf_counter() - t0) * 1000)
        _passo(
            ctx, t0, "resposta", (res.get("resposta") or res.get("erro") or "")[:200]
        )
        ex = _registrar_execucao(
            user,
            intent_nome,
            entrada,
            deteccao,
            ctx,
            params,
            via,
            ok=bool(res.get("ok")),
            duracao_ms=ms,
            resposta=res.get("resposta", ""),
            erro=res.get("erro", ""),
            flags=list(intent.get("flags", [])),
            fontes=list(ctx["fontes"]),
            artefato=artefato_obj,
        )
        IAEvento.objects.create(
            user=user,
            tipo="resposta" if res.get("ok") else "erro",
            resumo=f"{intent_nome}: {(res.get('resposta') or res.get('erro') or '')[:150]}",
            dados={"entrada": entrada[:300], "duracao_ms": ms, "cached": False},
            execucao=ex,
        )
    out = dict(res)
    out["execucao_id"] = ex.id
    out["duracao_ms"] = ms
    out["flags"] = list(intent.get("flags", []))
    if artefato_obj:
        out["artefato_id"] = artefato_obj.id

    # A VOZ, NO LIMITE.
    #
    # Medido antes disto, em `app/ia/*.py`: 25 de 29 ficheiros usavam
    # cabeçalho markdown, 19 usavam negrito, 7 usavam setas, 4 tinham
    # emoji. Um produtor no meio do talhão não vê um asterisco duplo — vê
    # dois asteriscos e adivinha o resto.
    #
    # Lava-se AQUI, e não em cada handler, por uma razão: um handler novo
    # escreve `**negrito**` na resposta e nenhum lint o apanha. A regra
    # "não escrever markdown nas respostas" vive num ficheiro de regras que
    # ninguém lê. No limite, vale para todos os handlers — incluindo os que
    # outra gente escreve.
    #
    # Ver `app/ia/voz.py` para o que isto NÃO faz: não reescreve frases.
    # Uma voz que reescreve o sentido é pior do que uma voz robótica,
    # porque parece mais segura do que é.
    from app.ia.voz import limpar as _limpar_voz

    # O COPILOTO, ANTES DA VOZ: a oferta e' acrescentada antes de a
    # resposta ser lavada, para a pergunta final sair limpa como o resto.
    #
    # Só nos intents de tempo, e só quando a regra acha mesmo um risco. Sem
    # isso isto seria uma newsletter: um "não há nada a dizer" que existe
    # para não ter nada a dizer é ruído, e ruído é o que faz um produtor
    # deixar de ler.
    if out.get("resposta") and not out.get("needs_confirm"):
        try:
            from app.ia import copiloto

            if intent_nome in copiloto.INTENTS_DE_TEMPO:
                _props = list(user.propriedades.all()[:1])
                if _props:
                    _achado = copiloto.sugerir(user, _props[0])
                    # Só oferece se houver dia para oferecer. Um "quer que eu
                    # remarque?" sem data proposta é uma pergunta que obriga a
                    # uma segunda volta, e a segunda volta é onde a maioria
                    # desiste — e sobra uma promessa que o sistema não pode
                    # cumprir.
                    if _achado and _achado.get("data_proposta"):
                        out["resposta"] = copiloto.frase_de_oferta(
                            _achado, out["resposta"]
                        )
                        # out["copiloto"] removido — campo morto, ninguém consome
                        _passo(ctx, t0, "copiloto", str(_achado.get("titulo"))[:80])

                        # A oferta É uma confirmação. Entra na máquina de
                        # estados normal, com `intent_pendente` e os dados já
                        # collected — assim o "sim" de amanhã é tratado pelo
                        # caminho que JÁ EXISTE e que tem testes, em vez de
                        # um segundo mecanismo inventado aqui.
                        #
                        # Sem isto, o copiloto fazia uma pergunta que não
                        # conseguia cumprir: o produtor dizia "sim" e o
                        # detector de intents não sabia o que aquilo queria
                        # dizer.
                        contexto.estado_atual = "AGUARDANDO_CONFIRMACAO"
                        contexto.intent_pendente = "remarcar_tarefa"
                        contexto.dados_coletados = {
                            "tarefa": _achado.get("tarefa_id"),
                            "data": _achado.get("data_proposta"),
                        }
                        contexto.save()
                        out["needs_confirm"] = True
                        out["confirmacao_de"] = "remarcar_tarefa"
        except Exception:  # noqa: BLE001 — o copiloto cala-se, a resposta serve
            pass

    for chave in ("resposta", "erro"):
        if out.get(chave):
            out[chave] = _limpar_voz(out[chave])

    # A COMPOSICAO, VALIDADE E CACHE JUNTOS.
    #
    # MEDIDO 2026-10-08. A Fase 1 do `docs/PLANO_WIDGET_DINAMICO.md` pede que o
    # resultado de um intent possa trazer `widget_composicao`: a lista de widgets
    # que a IA quer mostrar, e com que `config`. Sem isto a IA escreve texto e
    # fica a teletonto.
    #
    # Onde e' validado, e porque aqui e' so o copia
    # --------------------------------------------
    # A validacao e' feita pelo handler (ou por quem chama `palco.validar_estrutura`),
    # porque e' ai que se sabe o que cada widget sabe receber. Aqui o sandbox so
    # **normaliza o formato** e **recusa o que nao e' lista**. O sandbox nao sabe
    # o que e' um widget — e nao deve: `palco.py:57` e' o catalogo, e um intent
    # novo nao tem de mexer no sandbox para poder montar uma mesa.
    #
    # Por que aqui e' nao no handler
    # ------------------------------
    # Porque um handler nao devolve a composicao ao QUEIXA — devolve ao `dados`, e
    # o `dados` vai para o cache e para a `IAExecucao`. Um campo de topo e' o que
    # o browser le sem saber de que intent veio, e o que sobrevive ao cache sem
    # ter de dar ao produtor mais um sítio.
    composicao = out.pop("widget_composicao", None)
    if composicao is not None:
        normalizada = _normalizar_composicao(composicao)
        if normalizada is not None:
            out["widget_composicao"] = normalizada

    # A PEÇA RICA, NO MESMO LUGAR DA COMPOSICAO.
    #
    # Qualquer intent que traga `dados.serie` ganha peça de dashboard quando
    # o modo painel está ligado — sem mexer no handler. O chat desenha o
    # gráfico pelo cliente a partir da mesma série; aqui compõem-se
    # texto+grafico+tabela validados pelo servidor, com linhas recalculadas
    # pela fonte e carimbo MEDIDO. Nunca em `needs_confirm` (peça é
    # afirmação) e nunca sem `ok`: apresentar sem ter, nem pensar.
    serie = (out.get("dados") or {}).get("serie")
    if (
        out.get("ok")
        and not out.get("needs_confirm")
        and isinstance(serie, dict)
        and "painel" in (ctx.get("modos") or [])
    ):
        try:
            from app.ia import chamado as _chamado_peca

            peca = _chamado_peca.peca_de_serie(serie, out.get("resposta") or "")
            if peca.get("ok"):
                blocos = _chamado_peca.aplicar_fontes(user, peca["peca"]["blocos"])
                out.setdefault("dados", {})["peca"] = {
                    "nome": peca["peca"]["nome"],
                    "existe": True,
                    "estado": "",
                    "versao": 1,
                    "blocos": blocos,
                }
                _passo(ctx, t0, "peca", str(peca["peca"]["nome"])[:80])
        except Exception:  # noqa: BLE001 — apresentação não quebra resposta
            logger.warning("[ia.sandbox] peca da serie falhou; segue a prosa")

    if ttl and res.get("ok") and intent_nome not in INTENTS_NAO_CACHEAVEIS:
        a_guardar = {
            "ok": True,
            "resposta": res.get("resposta", ""),
            "dados": res.get("dados", {}),
            "artefato_id": artefato_obj.id if artefato_obj else None,
            "flags": out["flags"],
        }
        # MEDIDO 2026-10-08: a composicao entra no payload de cache. Sem esta
        # linha o browser recebe a oferta na 1a chamada e nao na 2a (o TTL pode
        # ser de minutos), e um produtor que repete a pergunta ve a mesa
        # desaparecer. E o mesmo defeito que a `needs_confirm` nao tem porque
        # `INTENTS_NAO_CACHEAVEIS` a retira da cache.
        if out.get("widget_composicao"):
            a_guardar["widget_composicao"] = out["widget_composicao"]
        cache.set(ck, a_guardar, ttl)
    return out


#: O que um handler pode trazer em `widget_composicao`, e o que o sandbox aceita.
#: A lista e' curta de proposito: um campo que aceita qualquer coisa e' um campo
#: que alguem vai usar para passar o que quiser.
_CHAVES_COMPOSICAO = ("tipo", "titulo", "config")
_TETO_COMPOSICAO = 8


def _normalizar_composicao(bruto: Any) -> list[dict[str, Any]] | None:
    """A `widget_composicao` de um handler, ou `None` se nao presta.

    Devolve `None` — e nao lista vazia — quando a coisa nao e' lista. A diferenca
    importa: uma lista vazia e' "a IA montou uma mesa sem widgets", que e' um
    resultado; `None` e' "isto nao era uma composicao", que e' um erro de
    formato. Um e' para mostrar, o outro e' para deitar fora.

    Nao valida o `tipo` contra o catalogo. Quem valida e' `palco.validar_estrutura`,
    no caminho que monta a tela, e essa validacao ja e' a fronteira de seguranca
    (`palco.py:198-259`). Duplicar aqui seria ter duas verdades, e a segunda
    diverge — que e' exactamente o que aconteceu com `CATALOGO_IA` quando foi
    montado a partir dos TITULOS do JavaScript (`palco.py:38-48`).
    """
    if isinstance(bruto, dict):
        bruto = bruto.get("widgets")
    if not isinstance(bruto, list):
        return None

    saida: list[dict[str, Any]] = []
    vistos: set[str] = set()
    for item in bruto[:_TETO_COMPOSICAO]:
        if not isinstance(item, dict):
            continue
        tipo = str(item.get("tipo") or item.get("type") or "").strip()
        if not tipo or tipo in vistos:
            continue
        vistos.add(tipo)
        widget: dict[str, Any] = {"tipo": tipo}
        titulo = str(item.get("titulo") or "").strip()
        if titulo:
            widget["titulo"] = titulo[:120]
        cfg = item.get("config")
        if isinstance(cfg, dict):
            widget["config"] = cfg
        saida.append({k: v for k, v in widget.items() if k in _CHAVES_COMPOSICAO})

    return saida or None


def catalogo():
    """Instruções da IA: o painel/IA lê aqui o que pode fazer e como."""
    return {
        nome: {
            "descricao": spec["descricao"],
            "exemplos": spec["exemplos"],
            "flags": spec["flags"],
        }
        for nome, spec in INTENTS.items()
    }
