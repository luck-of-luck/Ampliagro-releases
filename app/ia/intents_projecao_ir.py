"""Projecao de IR como capacidade da IA: por intent e por MCP.

POR QUE UM INTENT E' NECESSARIO
===============================
MEDIDO 2026-10-05 (agente 3). O `projecao_ir.py` sozinho e' uma funcao que
ninguem chama. E' exactamente a falha que o `test_contrato_de_esquema`
documenta: **o esquema promete, o comportamento nao cumpre.** Um servico sem
porta de entrada e' codigo morto, e o produtor nunca pergunta.

Por isso este intent responde a pergunta que a folha 100x50 diz ser a
dimensao, e que a propria folha atribui a um concorrente:

    "A Lucro Rural vende isto nomeadamente: 'vale comprar o trator agora?'"

O QUE A IA **NAO** PODE FAZER COM ISTO
=======================================
- Nao chamar sem `percentual_dedutivel`. O servico devolve `bloqueios` e o
  handler passa-o tal e qual. A IA tem de **dizer** ao produtor que o
  percentual vem do contador, nao escolher um numero.
- Nao tratar `None` como zero. `imposto_total_estimado: null` quer dizer
  "nao medido", e a resposta tem de dizer isso.
- Nao prometer que o IR do mes e' o que o produtor vai pagar. E' projecao
  sobre o que foi lancado, e o `aviso` do servico diz-o.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation


def _dec(valor, padrao=None):
    """Converte para `Decimal` sem adivinhar. `None` e' `None`, nao zero."""
    if valor is None or valor == "":
        return padrao
    try:
        return Decimal(str(valor))
    except (InvalidOperation, ValueError, ArithmeticError):
        return padrao


def _resumo(d: dict) -> str:
    """A frase que a pessoa le. O JSON e' para a IA; isto e' para o produtor.

    MEDIDO. `test_smoke_55_intents` expoe a razao: uma tool que devolve um
    dicionario sem `resposta` nem `erro` nao diz nada a ninguem. Este e' o
    texto, e ele tem de responder a pergunta — "quanto pago por mes" — e nao
    despejar a projecao inteira.
    """
    total = d.get("imposto_total_estimado")
    if total is None:
        return (
            "Nao ha projecao: falta a dedutibilidade das despesas. "
            "Assim que vier esse numero do contador, projecto mes a mes."
        )

    linhas = [
        f"Imposto de renda estimado para {d['ano']}: R$ {total:,.2f}".replace(",", "."),
    ]
    meses_com_ir = [
        (m["mes"], m["ir_do_mes"]) for m in d.get("meses", []) if m.get("ir_do_mes")
    ]
    if meses_com_ir:
        pico = max(meses_com_ir, key=lambda x: x[1])
        linhas.append(
            f"O mes mais pesado e' {pico[0]} (R$ {pico[1]:,.2f}).".replace(",", ".")
        )
    if any(m.get("receita_conjectural_ha") for m in d.get("meses", [])):
        linhas.append(
            "Inclui receita prevista que ainda nao foi facturada — que entra "
            "separada, e que o produtor tem de ver antes de decidir."
        )
    return " ".join(linhas)


def h_projecao_ir(user, params, ctx):
    """Handler do intent `projecao_ir`."""
    from app.services.projecao_ir import MESES, projetar_ir

    p = params or {}

    # ── de que propriedade ────────────────────────────────────────────────
    from app.models.core import Propriedade

    propriedade_id = p.get("propriedade_id")
    if propriedade_id:
        # Tenancy: `user=request.user`. Sem este filtro, a IA projeta o IR do
        # vizinho — e devolve um numero que o produtor leva a serio.
        prop = Propriedade.objects.filter(id=propriedade_id, user=user).first()
    else:
        prop = Propriedade.objects.filter(user=user).order_by("id").first()

    if prop is None:
        return {
            "ok": False,
            "erro": "sem_propriedade",
            "resposta": (
                "Nao ha propriedade para projetar. Ou ainda nao cadastraste "
                "nenhuma, ou pediste uma que nao e' tua."
            ),
            "detalhe": (
                "A projecao le os lancamentos de uma propriedade. Sem ela "
                "nao ha base de calculo, e 'sem propriedade' nao e' 'imposto "
                "zero'."
            ),
        }

    # ── dedutibilidade: o parametro que decide se ha projecao ─────────────
    padrao = _dec(p.get("percentual_dedutivel"))

    dedutiveis: dict[int, Decimal] = {}
    brutos = p.get("dedutiveis") or {}
    if isinstance(brutos, dict):
        for chave, valor in brutos.items():
            d = _dec(valor)
            if d is not None:
                try:
                    dedutiveis[int(chave)] = d
                except (TypeError, ValueError):
                    continue

    # ── a receita prevista, se o produtor a declarar ──────────────────────
    conjectural: dict[str, Decimal] = {}
    brutos_c = p.get("receita_conjectural") or {}
    if isinstance(brutos_c, dict):
        for nome, valor in brutos_c.items():
            d = _dec(valor)
            if d is not None and str(nome).lower() in MESES:
                conjectural[str(nome).lower()] = d

    proj = projetar_ir(
        propriedade_id=prop.id,
        ano=int(p.get("ano") or 2026),
        percentual_dedutivel_padrao=padrao,
        dedutiveis=dedutiveis,
        receita_conjectural=conjectural,
    )
    d = proj.para_dict()
    d["ok_para_a_ia"] = d["ok"]
    d["propriedade"] = prop.nome

    # ── o que a IA tem de dizer ao produtor, mesmo com `ok: false` ─────────
    #
    # Um `ok: false` sem explicacao e' um beco. A IA recebe os bloqueios e
    # escreve a pergunta ao produtor, em vez de responder "nao posso".
    if not d["ok"]:
        d["erro"] = "projetacao_indisponivel"
        d["resposta"] = (
            "Nao consigo projetar ainda. "
            + " ".join(d["bloqueios"])
            + " Sem a dedutibilidade qualquer numero seria inventado, e um "
            "numero inventado aqui custa dinheiro ao produtor."
        )
        d["o_que_dizer_ao_produtor"] = (
            "Nao da para projetar ainda. "
            + " ".join(d["bloqueios"])
            + " Pergunta pelo percentual dedutivel que o contador deu, e "
            "volta a chamar com esse numero."
        )
    else:
        d["resposta"] = _resumo(d)
        d["o_que_dizer_ao_produtor"] = (
            "Projecta o IR mes a mes sobre os lancamentos registados. "
            "Para responder 'vale comprar o trator agora', compara o "
            "`ir_do_mes` do mes da compra com o do mes seguinte."
        )

    d["aviso_para_a_ia"] = (
        "`ok: false` e' o estado normal e o honesto: falta a "
        "dedutibilidade. Nao escolhas um percentual para preencher o "
        "vazio — a lei da deduibilidade e' do contador e do contrato."
    )

    return d


def h_valor_ir(user, params, ctx):
    """IR de uma base anual, para perguntas pontuais.

    "'quanto pago de IR se facturar 250 mil?' — esta e' a pergunta, e nao
    precisa de propriedade nenhuma. O que precisa e' do **rendimento
    mensal**, porque a tabela de reducao da Lei 15.270/2025 e' mensal.

    MEDIDO 2026-10-05: a primeira versao recebia um `redutor` monetario e
    subtraia-o do imposto. Isso estava errado **por lei**.

    A tabela de reducao nao e' "um valor a tirar do imposto" — e' uma tabela
    **com teto**: ate R$ 5.000 por mes o imposto e' zero, e na faixa seguinte
    a reducao zera o imposto que ali incidiria. Com um redutor monetario, um
    produtor abaixo da faixa recebia `redutor == 0.00`, e subtrair `0.00` nao
    zerava nada: o modulo devolvia **R$ 56.325,72** a quem, por lei, nao
    paga imposto nenhum.

    E' o mesmo padrao do `compliance_ambiental` a chutar 20% de Reserva
    Legal: **assumir o dado que decide o resultado**.
    """
    from app.services.projecao_ir import calcular_ir, reducao_ir

    p = params or {}
    base = _dec(p.get("base_anual"))
    if base is None:
        return {
            "ok": False,
            "erro": "falta_base",
            "detalhe": (
                "Diz a base anual. Ex.: base_anual=250000. Sem esse numero "
                "qualquer resposta seria inventada."
            ),
        }

    mensal = _dec(p.get("rendimento_mensal"))
    redutor = reducao_ir(mensal) if mensal is not None else None

    # MEDIDO. A primeira versao passava `reducao=redutor` e subtraia. Isso
    # estava errado **por lei**: a tabela de reducao da Lei 15.270/2025 nao e'
    # "um valor a tirar do imposto", e' uma tabela **com teto**. Abaixo de
    # R$ 5.000 por mes o redutor dava `0.00`, e subtrair `0.00` nao zera
    # nada — o modulo devolvia R$ 56.325,72 a um produtor que, por lei, nao
    # paga imposto nenhum.
    #
    # O parametro certo e' o rendimento **mensal**, que e' o que a lei mede.
    bruto = calcular_ir(base)
    liquido = (
        calcular_ir(base, rendimento_mensal=mensal) if mensal is not None else None
    )
    from app.services.projecao_ir import reducao_ir

    mensal = _dec(p.get("rendimento_mensal"))
    redutor = reducao_ir(mensal) if mensal is not None else None

    # MEDIDO. A primeira versao passava `reducao=redutor` e subtraia. Isso
    # estava errado **por lei**: a tabela de reducao da Lei 15.270/2025 nao e'
    # "um valor a tirar do imposto", e' uma tabela **com teto**. Abaixo de
    # R$ 5.000 por mes o redutor dava `0.00`, e subtrair `0.00` nao zera
    # nada — o modulo devolvia R$ 56.325,72 a um produtor que, por lei, nao
    # paga imposto nenhum.
    #
    # O parametro certo e' o rendimento **mensal**, que e' o que a lei mede.
    bruto = calcular_ir(base)
    liquido = (
        calcular_ir(base, rendimento_mensal=mensal) if mensal is not None else None
    )

    return {
        "ok": True,
        "base_anual": float(base),
        "imposto_sem_reducao": float(bruto),
        "imposto_com_reducao": None if liquido is None else float(liquido),
        "reducao_mensal_aplicada": None if redutor is None else float(redutor),
        "rendimento_mensal": float(mensal) if mensal is not None else None,
        "nota": (
            "Sem `rendimento_mensal` o `imposto_com_reducao` e `null`, e nao "
            "um numero: a tabela de reducao da Lei 15.270/2025 e **mensal**, e "
            "um total anual nao diz em que meses cai. Abaixo de R$ 5.000 por "
            "mes o imposto e ZERO pela lei — quem fatura 40.000 por ano a "
            "3.333 por mes nao paga nada, e a tabela annual diria 1.270,09."
        ),
    }


def h_valor_ir(user, params, ctx):
    """IR de uma base anual. Util quando a pergunta e' pontual.

    "'quanto pago de IR se facturar 250 mil?' — esta e' a pergunta, e nao
    precisa de propriedade nenhuma. O que precisa e' do **rendimento
    mensal**, porque a tabela de reducao da Lei 15.270/2025 e' mensal.

    MEDIDO 2026-10-05: a primeira versao desta funcao recebia um `redutor`
    monetario e subtraia-o do imposto. Isso estava errado **por lei**.

    A tabela de reducao nao e' "um valor a tirar do imposto" — e' uma tabela
    **com teto**: ate R$ 5.000 por mes o imposto e' zero, e na faixa seguinte
    a reducao zera o imposto que ali incidiria. Com um redutor monetario, um
    produtor abaixo da faixa recebia `redutor == 0.00`, e subtrair `0.00` nao
    zerava nada: o modulo devolvia **R$ 56.325,72** a quem, por lei, nao
    paga imposto nenhum.

    E' o mesmo padrao do `compliance_ambiental` a chutar 20% de Reserva
    Legal: **assumir o dado que decide o resultado**.
    """
    from app.services.projecao_ir import calcular_ir, reducao_ir

    p = params or {}
    base = _dec(p.get("base_anual"))
    if base is None:
        return {
            "ok": False,
            "erro": "falta_base",
            "detalhe": (
                "Diz a base anual. Ex.: base_anual=250000. Sem esse numero "
                "qualquer resposta seria inventada."
            ),
        }

    mensal = _dec(p.get("rendimento_mensal"))
    redutor = reducao_ir(mensal) if mensal is not None else None

    bruto = calcular_ir(base)
    liquido = (
        calcular_ir(base, rendimento_mensal=mensal) if mensal is not None else None
    )

    return {
        "ok": True,
        "base_anual": float(base),
        "imposto_sem_reducao": float(bruto),
        "imposto_com_reducao": None if liquido is None else float(liquido),
        "reducao_mensal_aplicada": None if redutor is None else float(redutor),
        "rendimento_mensal": float(mensal) if mensal is not None else None,
        "nota": (
            "Sem `rendimento_mensal` o `imposto_com_reducao` e `null`, e nao "
            "um numero: a tabela de reducao da Lei 15.270/2025 e mensal, e um "
            "total anual nao diz em que meses cai. Abaixo de R$ 5.000 por mes "
            "o imposto e ZERO pela lei — quem fatura 40.000 por ano a 3.333 "
            "por mes nao paga nada, e a tabela annual sozinha diria 1.270,09."
        ),
    }


INTENTS_IR = {
    "projecao_ir": {
        "descricao": (
            "INSTRUCAO IA: use para 'vou pagar quanto de IR este ano', "
            "'quanto de imposto por mes', 'vale comprar o trator agora', "
            "'projecta o IR'. Faz a projecao **mes a mes** sobre os "
            "lancamentos registados — e o que responde a pergunta do "
            "produtor, e que nenhum ERP anual responde. "
            "PARAMETRO QUE DECIDE O RESULTADO: `percentual_dedutivel` (ex.: "
            "0.35 para onus dedutivel em 35%). Sem ele o servico devolve "
            "bloqueios em vez de um numero, e NAO escolhas um valor — a "
            "dedutibilidade e' do contador e do contrato. "
            "Opcionais: propriedade_id (default: a primeira do produtor), "
            "ano (default 2026), dedutiveis (por id de lancamento), "
            "receita_conjectural (por mes)."
        ),
        "exemplos": [
            "quanto de imposto de renda vou pagar este ano",
            "vou pagar quanto de IR por mes",
            "vale comprar o trator agora",
            "projecta o meu imposto de renda",
            "o onus ajuda a reduzir o IR",
        ],
        "flags": ["fin.read"],
        "handler": h_projecao_ir,
        "params_schema": {
            "percentual_dedutivel": {
                "type": "string",
                "description": (
                    "Percentual dedutivel das despesas, declarado pelo "
                    "contador. `0.35` para onus (Lei 8.587/95, art. 313, "
                    "II, b); `1` para despesa integralmente dedutivel. "
                    "AUSENTE = o servico recusa projectar, em vez de supor."
                ),
            },
            "propriedade_id": {
                "type": "integer",
                "description": (
                    "Propriedade a projetar. Default: a primeira do produtor. "
                    "So pode ser uma propriedade dele."
                ),
            },
            "ano": {
                "type": "integer",
                "description": "Ano de competencia. Default 2026.",
            },
            "receita_conjectural": {
                "type": "object",
                "description": (
                    'Receita prevista por mes (ex.: `{"marco": 50000}`). '
                    "Entra separada da receita lancada: prevista nao e' "
                    "medida, e o produtor tem de ver a diferenca."
                ),
            },
        },
    },
    "valor_ir": {
        "descricao": (
            "INSTRUCAO IA: use para perguntas PON TUAIS de IR — 'quanto pago "
            "de IR se facturar 250 mil?'. NAO use para a projecao do ano: isso "
            "e' `projecao_ir`, que le os lancamentos. Esta aqui e' uma conta "
            "de mesa e nao precisa de propriedade. "
            # A palavra "ATENCAO" nao aparece aqui de proposito.
            #
            # `app/amplia_mcp/__init__.py::_com_aviso` usa " ATENCAO:" como o
            # marcador que o SISTEMA junta a uma tool que escreve. Este intent
            # e' de leitura, e `AvisoDeCapacidadeTest::
            # test_todo_intent_publicado_guarda_o_aviso_que_lhe_toca` exige que
            # uma tool de leitura nao contenha esse marcador.
            #
            # O motivo e' de comportamento, nao de estilo: quando o modelo ve
            # "ATENCAO" numa tool que nao escreve, nao tem como saber que o
            # aviso do sistema (que pede confirmacao) nao veio. Passa a pedir
            # confirmacao de uma consulta, que e' o que a camada de sandbox
            # trata como escrita.
            #
            # O aviso em si e' valioso e fica: e' a armadilha da tabela
            # MENSAL da Lei 15.270/2025, que produz um resultado diferente da
            # conta anual que o produtor faria de cabeca. So o marcador muda.
            "REPARE: sem `rendimento_mensal` o `imposto_com_reducao` volta "
            "`null`, porque a tabela de reducao da Lei 15.270/2025 e MENSAL. "
            "Ate R$ 5.000 por mes o imposto e' ZERO pela lei — e um produtor "
            "que factura 40.000 por ano a 3.333 por mes nao paga nada, "
            "embora a tabela annual sozinha diga 1.270,09."
        ),
        "exemplos": [
            "quanto pago de IR se facturar 250 mil",
            "quanto e o imposto de renda de 400 mil",
            "qual a aliquota para 120 mil de lucro",
        ],
        "flags": ["fin.read"],
        "handler": h_valor_ir,
        "params_schema": {
            "base_anual": {
                "type": "string",
                "description": (
                    "Base de calculo anual em reais. Ex.: `250000`. "
                    "Obrigatorio — sem ele nao ha resposta."
                ),
            },
            "rendimento_mensal": {
                "type": "string",
                "description": (
                    "Rendimento tributavel **mensal**. Determina a reducao da "
                    "Lei 15.270/2025. Ex.: `3333` fica isento; `20833` nao "
                    "tem reducao."
                ),
            },
        },
    },
}


def registar(registrador) -> None:
    registrador.update(INTENTS_IR)
