"""
Lote 4 — 8 intents automatizar_* (porte/meio) — 20 RegraAuto
Seeds em app/iot/regras_auto.py REGRAS_AUTO. Todos herméticos, escopo propriedade__user.
"""


def _semear_regra(user, regra_id, params=None, ctx=None):
    """Semeia UMA regra de REGRAS_AUTO na propriedade do produtor.

    O que esta função faz e o que ela NAO faz
    ------------------------------------------
    Ela cria a REGRA. A regra e' o que o `alert_engine` lê quando a telemetria
    chega; se a regra tiver `acao_fisica`, e' o motor que enfileira o comando
    na válvula. Esta função NAO abre nada, e NAO deve.

    Se abrisse a válvula agora, teríamos irrigação a disparar sem sensor
    nenhum — o pior arranjo possível, porque o produtor vê o pivô a deitar
    água e não há medição que justifique. O que se cria aqui e' a condição
    sob a qual o motor vai agir, e só ele age.

    TENANCY: a lista de propriedades vem de `user.propriedades`, que já é
    filtrada. NÃO usar `Propriedade.objects.first()` — isso devolveria a
    primeira fazenda do sistema, e um produtor configuraria a regra de outro.
    """
    from app.iot.regras_auto import REGRAS_AUTO, seed_regras_auto

    params = params or {}
    props = list(user.propriedades.all())
    if not props:
        return {
            "ok": True,
            "resposta": "Cadastre uma propriedade antes de configurar uma automação.",
        }

    pedida = str(params.get("propriedade_id") or "").strip()
    if pedida:
        prop = next((p for p in props if str(p.id) == pedida), None)
        if prop is None:
            return {
                "ok": False,
                "erro": f"propriedade {pedida} não existe ou não é sua",
            }
    else:
        prop = props[0]

    try:
        criadas, atualizadas = seed_regras_auto(prop, apenas=[regra_id])
    except ValueError as e:
        return {"ok": False, "erro": str(e)}

    regra = next(r for r in REGRAS_AUTO if r["id"] == regra_id)
    acao = regra.get("acao_fisica") or ""
    verbo = "Já estava configurada" if not criadas else "Configurada"

    if acao:
        extra = (
            " A válvula é comandada pelo motor quando a leitura confirmar "
            "o limite — não agora."
        )
    else:
        extra = " Quando o limite for atingido, o sistema cria a tarefa de ação."

    return {
        "ok": True,
        "resposta": (
            f"{verbo}: {regra['nome']} em {prop.nome}. {regra['titulo_tarefa']}.{extra}"
        ),
        "dados": {
            "regra_id": regra_id,
            "propriedade": prop.nome,
            "criadas": criadas,
            "atualizadas": atualizadas,
            "acao_fisica": acao,
        },
        "artefato": (f"automacao/{prop.id}/{regra_id}", "regra"),
    }


def _automatizar_regras_auto(user, params=None, ctx=None):
    from app.iot.regras_auto import REGRAS_AUTO
    from app.models.iot import RegraAlertaTelemetria

    # Compat: sandbox chama handler(user, params_dict, ctx). Chamadas legadas
    # passavam texto direto. Aceita os dois sem quebrar o smoke test.
    if isinstance(params, dict):
        texto = params.get("texto") or params.get("filtro") or params.get("porte") or ""
    else:
        texto = params or ""
    _ctx = ctx if isinstance(ctx, dict) else None

    props = (
        list(user.propriedades.all().values_list("id", flat=True))
        if hasattr(user, "propriedades")
        else []
    )
    if not props:
        return {
            "resposta": "Cadastre uma propriedade para ver automações.",
            "dados": {"total": 0},
        }
    qs = RegraAlertaTelemetria.objects.filter(propriedade_id__in=props)
    total = qs.count()
    ativas = qs.filter(ativa=True).count()
    # Filtro por texto: porte/meio/tela
    t = (texto or "").lower()
    filtradas = REGRAS_AUTO
    if any(k in t for k in ["familiar", "medio", "grande", "mega"]):
        porte = (
            "familiar"
            if "familiar" in t
            else "medio"
            if "medio" in t
            else "grande"
            if "grande" in t
            else "mega"
        )
        filtradas = [r for r in filtradas if r["porte"] == porte]
    elif any(
        k in t for k in ["agua", "terra", "maquina", "capital", "conhecimento", "gente"]
    ):
        meio = next(
            (
                k
                for k in [
                    "agua",
                    "terra",
                    "maquina",
                    "capital",
                    "conhecimento",
                    "gente",
                ]
                if k in t
            ),
            None,
        )
        if meio:
            filtradas = [r for r in filtradas if r["meio"] == meio]
    amostra = filtradas[:5]
    linhas = [
        f"• {r['nome']} — {r['tela']} ({r['porte']}/{r['meio']})" for r in amostra
    ]
    resp = f"Automação {ativas}/{total} ativas (20 mapeadas). Exemplos:\n" + "\n".join(
        linhas
    )
    if len(filtradas) < len(REGRAS_AUTO):
        resp += f"\nFiltro '{t.strip()}' → {len(filtradas)} regras."
    return {
        "resposta": resp,
        "dados": {
            "total": total,
            "ativas": ativas,
            "mapeadas": len(REGRAS_AUTO),
            "filtradas": len(filtradas),
        },
        "artefato": ("regras_auto", "lista"),
    }


def _automatizar_piquete(user, params=None, ctx=None):
    return _semear_regra(user, "pecuaria_leite_piquete_30d", params, ctx)


def _automatizar_pivo(user, params=None, ctx=None):
    return _semear_regra(user, "grao_bme280_pivo_40mm", params, ctx)


def _automatizar_aerador(user, params=None, ctx=None):
    return _semear_regra(user, "tilapia_pele_566pct_aerador", params, ctx)


def _automatizar_hedge(user, params=None, ctx=None):
    return _semear_regra(user, "grao_hedge_chicago_5pct", params, ctx)


def _automatizar_moba(user, params=None, ctx=None):
    return _semear_regra(user, "avicultura_moba_9_5_descarte", params, ctx)


def _automatizar_bigbrother(user, params=None, ctx=None):
    return _semear_regra(user, "avicultura_bigbrother_12_balancas", params, ctx)


def _automatizar_spd(user, params=None, ctx=None):
    return _semear_regra(user, "grao_spd_mo_2_para_3_4", params, ctx)


def _automatizar_sap(user, params=None, ctx=None):
    return _semear_regra(user, "erp_sap_jbs_10m", params, ctx)


INTENTS4 = {
    "automatizar_regras": {
        "descricao": "Lista automações 20 RegraAuto por porte/meio — use para ver o que automatiza sozinho.",
        "exemplos": [
            "quais automações",
            "o que automatiza",
            "regras auto",
            "automatizar fazenda",
        ],
        "flags": ["iot.read"],
        "handler": _automatizar_regras_auto,
    },
    "automatizar_piquete": {
        # Pecuária. "rotacao de piquete" e "15 L/vaca" na descrição: é gado de
        # leite. `aplica_a` é "animal", não "aves" — a regra serve a qualquer
        # ruminante, e a projecao fala de L/vaca.
        "aplica_a": "animal",
        "requires_confirmation": True,
        "prompt_confirmacao": (
            "Quer que eu passe o gado de pasto a cada 30 dias e crie "
            "a tarefa de mudar a cerca?"
        ),
        "descricao": "Configura o alerta de rotacao de piquete: a cada 30 dias marca tarefa de cerca para o gado de leite (15 L/vaca). A regra avisa e cria a tarefa; nao move o gado.",
        "exemplos": [
            "automatizar piquete",
            "cerca virtual leite",
            "piquete 30 dias",
            "rotacionar piquete",
        ],
        "flags": ["pecuaria.read", "iot.read", "iot.write"],
        "handler": _automatizar_piquete,
    },
    "automatizar_pivo": {
        "descricao": "Configura a regra que abre o pivô 40mm quando a umidade do solo (BME280) cair abaixo de 60%. A valvula e comandada pelo motor quando a leitura confirmar o limite — o handler so cria a regra.",
        "exemplos": [
            "automatizar pivô",
            "ligar pivô automatico",
            "BME280 pivô",
            "umidade solo irrigar",
        ],
        "flags": ["iot.read", "iot.comando"],
        "requires_confirmation": True,
        "prompt_confirmacao": (
            "Quer que eu abra o pivô sozinho quando a umidade do solo "
            "cair abaixo de 60%? A válvula pode abrir sem ninguém mandar."
        ),
        "handler": _automatizar_pivo,
    },
    "automatizar_aerador": {
        # `aplica_a` diz a que grupo de cultura esta pergunta pertence. Ver
        # `app/cultures/filtro.py::widget_aplicavel` — e o mesmo filtro corta
        # o catálogo de widgets E o de capacidades da IA.
        #
        # A atribuição sai da descrição que está logo abaixo: "o mormaco da
        # tilapia" não admite leitura alternativa. Uma pergunta de aquicultura
        # oferecida a quem planta soja não é uma pergunta a mais — é a IA a
        # sugerir um aerador a uma fazenda que não tem tanque.
        "aplica_a": "aquatica",
        "descricao": "Configura a regra que liga o aerador quando o mormaco da tilapia passar de 30 °C, reduzindo a temperatura 5 °C. Protege a pele, que vale muito mais do que o filete.",
        "exemplos": [
            "automatizar aerador",
            "tilápia mormaco aerador",
            "ligar aerador tilápia",
        ],
        "flags": ["iot.read", "iot.comando"],
        "requires_confirmation": True,
        "prompt_confirmacao": (
            "Quer que eu ligue o aerador sozinho quando o mormaço passar "
            "de 30 graus? Ele liga sem ninguém mandar."
        ),
        "handler": _automatizar_aerador,
    },
    "automatizar_hedge": {
        # Vegetal, e commodity de exportação. A descrição nomeia soja e
        # Chicago/B3 — o hedge de preço existe para grão que negoceia em bolsa,
        # não para café de quintal nem para peixe. Deixado sem marca, a IA
        # oferecia proteção de Chicago a quem produze alface.
        "aplica_a": "vegetal",
        "requires_confirmation": True,
        "prompt_confirmacao": (
            "Quer que eu sugira a proteção quando o Chicago cair 5%?"
        ),
        "descricao": "Configura o alerta de hedge para soja V0-R8: Chicago a -5% em 1 dia sugere 65 sc de protecao. A regra SUGERE a operacao na tarefa — nao trava posicao financeira nenhuma.",
        "exemplos": [
            "automatizar hedge",
            "travar hedge automatico",
            "hedge chicago automatizar",
        ],
        "flags": ["fin.read", "campo.read", "iot.write"],
        "handler": _automatizar_hedge,
    },
    "automatizar_moba": {
        # Aves. "ajustar o bico" e "debicagem" são de avicultura — não existe
        # bico em nenhuma outra cultura do catálogo. AProjection de R$660k na
        # descrição é de uma regra que só faz sentido numa granja.
        "aplica_a": "aves",
        "requires_confirmation": True,
        "prompt_confirmacao": (
            "Quer que eu crie a tarefa de ajuste do bico quando o descarte "
            "passar de 9,5%?"
        ),
        "descricao": "Configura o alerta de moba: quando o descarte passar de 9,5% numa semana, cria tarefa para ajustar o bico a 4%. O ganho de R$660k e a projecao da regra — a regra nao ajusta o bico sozinha.",
        "exemplos": [
            "automatizar moba",
            "debicagem automatica",
            "moba 9,5 automatizar",
        ],
        "flags": ["pecuaria.read", "iot.write"],
        "handler": _automatizar_moba,
    },
    "automatizar_bigbrother": {
        # Aves. "2,8 kg por ave" e "a regra nao pesa frango" — a própria
        # descrição diz duas vezes que é de frango.
        "aplica_a": "aves",
        "requires_confirmation": True,
        "prompt_confirmacao": (
            "Quer que eu avise da previsão de peso nas 12 balancas?"
        ),
        "descricao": "Configura o alerta de peso nas 12 balancas do BigBrother, com previsao de 2,8 kg por ave. O ganho de R$192k e projecao da regra; a regra nao pesa frango.",
        "exemplos": [
            "automatizar big brother",
            "balança automatica frango",
            "prever peso frango",
        ],
        "flags": ["iot.read", "iot.write"],
        "handler": _automatizar_bigbrother,
    },
    "automatizar_spd": {
        "requires_confirmation": True,
        "prompt_confirmacao": (
            "Quer que eu avise quando a matéria orgânica do solo precisar de análise?"
        ),
        "descricao": "Configura o alerta de materia organica do solo (SPD): quando o MO cair de 2% para 3,4% de MO, mais uma, cria tarefa de analise. A regra nao aplica adubo.",
        "exemplos": [
            "automatizar SPD",
            "plantio direto automatizar",
            "MO solo automatizar",
        ],
        "flags": ["campo.read", "iot.write"],
        "handler": _automatizar_spd,
    },
    "automatizar_sap": {
        "requires_confirmation": True,
        "prompt_confirmacao": (
            "Quer que eu avise quando a ligação com o PROTHEUS cair?"
        ),
        "descricao": "Configura o alerta de integracao SAP ERP (JBS, 10M cabecas): avisa quando o sync com o PROTHEUS fica offline. A regra nao concilia nada sozinha.",
        "exemplos": [
            "automatizar SAP",
            "automatizar ERP",
            "integracao SAP automatizar",
            "conciliacao SAP",
        ],
        "flags": ["fin.read", "estoque.read", "iot.write"],
        "handler": _automatizar_sap,
    },
}

# TTLs — lazy para evitar circular import (sandbox importa INTENTS)
try:
    from app.ia.sandbox import CACHE_TTL as _TTL

    _TTL.update(
        {
            "automatizar_regras": 60,
            "automatizar_piquete": 60,
            "automatizar_pivo": 60,
            "automatizar_aerador": 60,
            "automatizar_hedge": 60,
            "automatizar_moba": 60,
            "automatizar_bigbrother": 60,
            "automatizar_spd": 60,
            "automatizar_sap": 60,
        }
    )
except Exception:
    pass
