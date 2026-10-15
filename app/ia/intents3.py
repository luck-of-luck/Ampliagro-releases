"""Lote 3 de intents — escritas guiadas (state-machine + confirmação) e leituras
computadas (lucro por talhão, adubação, alerta fitossanitário, vacinas, LCDPR).

Regras:
- TODA escrita tem `required_fields` + `requires_confirmation` (humano confirma
  com "sim" antes de qualquer efeito; COLETANDO pergunta o que falta).
- Escopo SEMPRE por usuário; leitura computada nunca inventa número
  (sem dado → diz que não há dado).
"""

from datetime import date
from decimal import Decimal, InvalidOperation

from app.ia.propriedade import resolver as _prop3

# `_prop3` era a terceira cópia da mesma função. Ver `app.ia.propriedade`
# para o que a duplicação custava e porque é que uma regra de segurança não
# pode viver em três sítios.


def _num(txt):
    """Extrai o primeiro número de um texto livre ("1.200,50" -> 1200.50)."""
    import re

    if txt is None:
        return None
    if isinstance(txt, (int, float, Decimal)):
        return float(txt)
    t = str(txt).replace(".", "").replace(",", ".")
    m = re.search(r"[-+]?\d*\.\d+|\d+", t)
    try:
        return float(m.group(0)) if m else None
    except (TypeError, ValueError):
        return None


def _data(txt):
    from datetime import datetime

    if not txt:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(str(txt).strip()[:10], fmt).date()
        except ValueError:
            continue
    return None


# ── escritas guiadas ────────────────────────────────────────────────

_CAMPOS_SAFRA = {
    "area_plantada",
    "area_colhida",
    "producao_total",
    "produtividade",
    "receita_estimada",
    "ano",
    "safra_nome",
    "observacao",
    "data_plantio",
    "data_colheita",
}
_NUMERICOS_SAFRA = {
    "area_plantada",
    "area_colhida",
    "producao_total",
    "produtividade",
    "receita_estimada",
    "ano",
}


def _acha_safra(user, prop, alvo):
    from app.models import Safra

    qs = Safra.objects.filter(propriedade__user=user)
    if prop:
        qs = qs.filter(propriedade=prop)
    a = (alvo or "").strip()
    if not a:
        return qs.order_by("-ano").first()
    ano = _num(a)
    if ano and ano > 1900:
        s = qs.filter(ano=int(ano)).first()
        if s:
            return s
    return (
        qs.filter(safra_nome__icontains=a).first()
        or qs.filter(cultura__nome__icontains=a).first()
    )


def h_editar_safra(user, params, ctx):
    prop = _prop3(user, params)
    s = _acha_safra(user, prop, params.get("safra"))
    if not s:
        return {"ok": False, "erro": "safra não encontrada (informe ano ou nome)"}
    campo = (params.get("campo") or "").strip().lower()
    if campo not in _CAMPOS_SAFRA:
        return {
            "ok": False,
            "erro": f"campo inválido — editável: {', '.join(sorted(_CAMPOS_SAFRA))}",
        }
    bruto = params.get("valor")
    if campo in ("data_plantio", "data_colheita"):
        valor = _data(bruto)
        if not valor:
            return {"ok": False, "erro": "data inválida (use dd/mm/aaaa)"}
    elif campo in _NUMERICOS_SAFRA:
        valor = _num(bruto)
        if valor is None:
            return {"ok": False, "erro": "valor numérico inválido"}
    else:
        valor = (bruto or "").strip()[:100]
        if not valor:
            return {"ok": False, "erro": "valor vazio"}
    setattr(s, campo, valor)
    s.save(update_fields=[campo])
    ctx["fontes"].append("interna:safra")
    return {
        "ok": True,
        "resposta": f"Safra {s.ano} atualizada: {campo} = {valor}.",
        "dados": {"safra_id": s.id, "campo": campo, "valor": str(valor)},
        "artefato": (f"safra/{s.ano}", "safra"),
    }


def h_excluir_safra(user, params, ctx):
    from app.models import Safra

    prop = _prop3(user, params)
    s = _acha_safra(user, prop, params.get("safra"))
    if not s:
        return {"ok": False, "erro": "safra não encontrada (informe ano ou nome)"}
    rotulo = f"{s.cultura.nome if s.cultura else '?'} {s.ano}"
    n_vinc = s.safra_talhoes.count()
    tem_plano = Safra.objects.filter(pk=s.pk, plano__isnull=False).exists()
    sid, ano = s.id, s.ano
    s.delete()
    ctx["fontes"].append("interna:safra")
    extras = []
    if n_vinc:
        extras.append(f"{n_vinc} vínculo(s) talhão")
    if tem_plano:
        extras.append("plano + atividades")
    detalhe = f" (levou junto: {', '.join(extras)})" if extras else ""
    return {
        "ok": True,
        "resposta": f"Safra {rotulo} excluída{detalhe}.",
        "dados": {"safra_id": sid, "ano": ano},
    }


_TIPOS_MAQ = {
    "trator": "TRATOR",
    "colheitadeira": "COLHEITADEIRA",
    "colheita": "COLHEITADEIRA",
    "pulverizador": "PULVERIZADOR",
    "caminhao": "CAMINHAO",
    "caminhão": "CAMINHAO",
    "implemento": "IMPLEMENTO",
    "plantadeira": "PLANTADEIRA",
    "plantio": "PLANTADEIRA",
    "drone": "DRONE",
    "pivo": "IMPLEMENTO",
    "pivô": "IMPLEMENTO",
}


def h_cadastrar_maquina(user, params, ctx):
    from app.models import Maquinario

    prop = _prop3(user, params)
    if not prop:
        return {"ok": False, "erro": "nenhuma propriedade encontrada"}
    nome = (params.get("nome") or "").strip()[:100]
    if len(nome) < 2:
        return {"ok": False, "erro": "informe o nome da máquina"}
    tipo_txt = (params.get("tipo") or "").strip().lower()
    tipo = _TIPOS_MAQ.get(tipo_txt)
    if not tipo:
        return {
            "ok": False,
            "erro": "tipo inválido — use: trator, colheitadeira, pulverizador, caminhão, plantadeira, drone ou implemento",
        }
    horas = _num(params.get("horas")) or 0
    m = Maquinario.objects.create(
        propriedade=prop, nome=nome, tipo=tipo, horas_uso=horas
    )
    ctx["fontes"].append("interna:maquinario")
    return {
        "ok": True,
        "resposta": f"Máquina '{m.nome}' ({m.get_tipo_display()}) cadastrada!",
        "dados": {"maquina_id": m.id, "nome": m.nome, "tipo": tipo},
        "artefato": (f"maquina/{m.id}", "maquinario"),
    }


# ── Cadastro de FUNCIONÁRIO ─────────────────────────────────────────────
#
# Uma pessoa não é uma máquina. A diferença não é o campo — nome e nome —
# é o que se está a registar: um tratorista é uma pessoa com um salário, um
# trator é um activo com um tipo. A conversa que originou isto misturou os
# dois: "como se cadastrar" + "vaqueiro" acabou no wizard de camiões, e o
# sistema perguntou "informe: tipo" a alguém que queria dizer vaqueiro.
#
# O que faltava não era o handler. Era o dicionário de cargos com
# TOLERÂNCIA A ERRO DE DIGITAÇÃO. "faqueiro" — "vaqueiro" com a v trocada,
# um carácter, escrito com um dedo no telemóvel a caminho — foi rejeitado
# três vezes seguidas com a mesma mensagem, como se a pessoa estivesse a
# inventar uma palavra. Não estava.
#
# O `difflib` encontra "vaqueiro" com cutoff 0.6. Não é adivinhação: só
# aceita acima do cutoff, e devolve o termo canónico VERDADEIRO para
# mostrar — "entendi faqueiro como vaqueiro, é isso?" — em vez de gravar o
# que a pessoa escreveu. Assumir em silêncio seria inventar o cargo de
# alguém, e o cargo decide o salário.

_CARGOS = {
    "gerente": "GERENTE",
    "tratorista": "TRATORISTA",
    "diarista": "DIARISTA",
    "vaqueiro": "VAQUEIRO",
    "motorista": "MOTORISTA",
    "mecanico": "MECANICO",
    "caseiro": "CASEIRO",
    "tecnico agricola": "TECNICO_AGRICOLA",
    "técnico agrícola": "TECNICO_AGRICOLA",
    "tecnico": "TECNICO_AGRICOLA",
    "capataz": "GERENTE",
    "encarregado": "GERENTE",
    "auxiliar": "DIARISTA",
    "peao": "DIARISTA",
    "peão": "DIARISTA",
    "boiadeiro": "VAQUEIRO",
}

# O outro lado do mesmo bug: uma MÁQUINA não é um cargo. Sem esta lista,
# "trator" era aceite como função de alguém — e o produtor ficava com um
# trator na equipa.
_CARGOS_NAO_PESSOA = {
    "trator",
    "colheitadeira",
    "pulverizador",
    "caminhao",
    "caminhão",
    "implemento",
    "plantadeira",
    "drone",
    "pivo",
    "pivô",
    "maquina",
    "máquina",
    "bomba",
    "gerador",
    "ensiladeira",
    "rocadeira",
    "coletor",
    "carreta",
    "reboque",
    "semeadeira",
    "adubadeira",
}

_NOMES_CARGO = {
    "GERENTE": "gerente",
    "TRATORISTA": "tratorista",
    "DIARISTA": "diarista",
    "VAQUEIRO": "vaqueiro",
    "MOTORISTA": "motorista",
    "MECANICO": "mecânico",
    "CASEIRO": "caseiro",
    "TECNICO_AGRICOLA": "técnico agrícola",
}


def _nome_cargo(canonico):
    """'VAQUEIRO' -> 'vaqueiro'. Para o texto que o utilizador lê."""
    return _NOMES_CARGO.get(canonico, str(canonico or "").lower())


def _hoje():
    """Hoje, como `date`. Isolado para ser fácil de substituir em teste."""
    from django.utils import timezone as _tz

    return _tz.now().date()


def _corrigir_cargo(texto):
    """(canonico, perto) — perto=True significa "acho que quis dizer este".

    A distinção importa: aceitar e gravar sem perguntar seria inventar o
    cargo de alguém, e o cargo decide o salário. Então pergunta-se.
    """
    t = " ".join((texto or "").strip().lower().split())
    if not t:
        return None, False
    if t in _CARGOS:
        return _CARGOS[t], False
    if t in _CARGOS_NAO_PESSOA:
        return None, False
    from difflib import get_close_matches

    perto = get_close_matches(t, list(_CARGOS), n=1, cutoff=0.6)
    if perto:
        return _CARGOS[perto[0]], True
    return None, False


def _perguntar_salario(valor=None):
    """Pergunta única para os dois casos de salário — não tem dado, ou não
    se percebeu o que se escreveu."""
    if valor in (None, ""):
        return 'Qual é o salário em R$? (ou escreva "a combinar")'
    return (
        f"Não entendi '{valor}' como salário. Qual é o salário em R$? "
        '(ou escreva "a combinar")'
    )


def _para_numero(valor):
    """'R$ 2.000,00' -> 2000.0. None se não for número.

    O formato brasileiro usa ponto para milhares e vírgula para decimais —
    e um produtor escreve o que está no contracheque, não JSON.

    A distinção que faltava: ponto é separador de MILHAR, não decimal. Na
    primeira versão, "R$ 1.500" dava 1.5 — e um salário de 1 real e meio
    para o vaqueiro. Um número plausível e errado é pior que nenhum: passa
    a validação e ninguém repara.
    """
    if valor in (None, ""):
        return None
    try:
        limpo = str(valor).replace("R$", "").replace("reais", "").strip()
        if "," in limpo:
            # vírgula é decimal: os pontos são separadores de milhar
            limpo = limpo.replace(".", "").replace(",", ".")
        else:
            # só pontos: se houver mais de um, ou se o último grupo tiver
            # 3 dígitos, são separadores de milhar. "1.500" -> 1500.
            partes = limpo.split(".")
            if len(partes) > 2 or (
                len(partes) == 2 and len(partes[1]) == 3 and partes[0].lstrip("-")
            ):
                limpo = limpo.replace(".", "")
        return float(limpo)
    except (TypeError, ValueError):
        return None


def h_cadastrar_funcionario(user, params, ctx):
    """Cadastra uma PESSOA na equipa da propriedade."""
    from app.models.equipe import Funcionario

    prop = _prop3(user, params)
    if not prop:
        return {"ok": False, "erro": "nenhuma propriedade encontrada"}

    nome = (params.get("nome") or "").strip()[:120]
    if len(nome) < 2:
        return {"ok": False, "erro": "informe o nome do funcionário"}

    cargo_txt = (params.get("cargo") or "").strip()
    cargo, perto = _corrigir_cargo(cargo_txt)
    if cargo is None:
        return {
            "ok": False,
            "campo": "cargo",
            "erro": (
                f"Não reconheci a função '{cargo_txt}'. Funções: "
                + ", ".join(sorted(k for k in _CARGOS if len(k) > 3))
            ),
            "opcoes": sorted(set(_CARGOS.values())),
        }
    if perto:
        return {
            "ok": False,
            "campo": "cargo",
            "pergunta": f"Entendi '{cargo_txt}' como {_nome_cargo(cargo)}. É isso?",
            "sugestao": cargo,
            "needs_confirm": True,
        }

    salario = params.get("salario")
    salario_num = _para_numero(salario)
    if salario_num is None:
        # `salario` é NOT NULL. Pôr 0 seria pior que perguntar: 0 é um
        # salário, e um salário zero é uma afirmação sobre quanto alguém
        # ganha. Um None rebenta com IntegrityError, que é um 500 para
        # quem só queria cadastrar o Carlos.
        return {
            "ok": False,
            "campo": "salario",
            "pergunta": _perguntar_salario(salario),
            "needs_confirm": True,
        }

    admissao = _para_data(params.get("data_admissao")) or _hoje()

    func = Funcionario(
        user=user,
        propriedade=prop,
        nome=nome,
        cargo=cargo,
        salario=salario_num,
        data_admissao=admissao,
    )
    func.save()
    return {
        "ok": True,
        "funcionario": {
            "id": func.id,
            "nome": func.nome,
            "cargo": _nome_cargo(func.cargo),
            "salario": float(func.salario),
            "data_admissao": str(func.data_admissao),
        },
        "resposta": (
            f"✅ {func.nome} ({_nome_cargo(func.cargo)}) cadastrado em {prop.nome}."
        ),
    }


def _para_data(valor):
    """Aceita '2026-09-30', '30/09/2026', '30 do setembro de 2026' e um
    `date`. None se não perceber.

    A conversa traria "15 do nove de 2026" — o português do produtor, e o
    formato que a forma como se fala uma data. Rejeitar isso e pedir de novo seria
    chatear alguém que já respondeu.
    """
    if valor in (None, ""):
        return None
    from datetime import date as _date

    if isinstance(valor, _date):
        return valor
    texto = str(valor).strip()
    try:
        return _date.fromisoformat(texto[:10])
    except ValueError:
        pass
    try:
        d, m, a = texto.split("/")
        a = int(a)
        if a < 100:
            a += 2000
        return _date(a, int(m), int(d))
    except (ValueError, AttributeError):
        pass
    MESES = {
        "janeiro": 1,
        "fevereiro": 2,
        "marco": 3,
        "março": 3,
        "abril": 4,
        "maio": 5,
        "junho": 6,
        "julho": 7,
        "agosto": 8,
        "setembro": 9,
        "outubro": 10,
        "novembro": 11,
        "dezembro": 12,
        # Abreviaturas. "nove" entrou porque foi o que apareceu na conversa
        # real — "15 do nove de 2026". Rejeitar uma data que se percebe é
        # irritar quem já respondeu.
        "jan": 1,
        "fev": 2,
        "mar": 3,
        "abr": 4,
        "mai": 5,
        "jun": 6,
        "jul": 7,
        "ago": 8,
        "set": 9,
        "out": 10,
        "nov": 11,
        "dez": 12,
        "janie": 1,
        "fevr": 2,
        "abru": 4,
        "junh": 6,
        "julh": 7,
        "agost": 8,
        "setem": 9,
        "outub": 10,
        "novem": 11,
        "dezem": 12,
        # "nove" é o que apareceu na conversa real ("15 do nove de 2026").
        # Sem esta entrada, o mês não casa e a data é devolvida como None
        # — o que faz o sistema usar a data de hoje em vez da que a
        # pessoa respondeu.
        "nove": 9,
    }
    # "15 do nove de 2026", "15 de setembro de 2026", "15 setembro 2026"
    partes = re.split(r"\s+(?:de|do|da|d[oa]s?)\s+|\s+", texto.lower().strip())
    partes = [x for x in partes if x]
    if len(partes) == 3:
        dia, mes, ano = partes
        # O nome do mês tem de casar INTEIRO — e só o nome exacto ou uma
        # abreviatura declarada.
        #
        # A primeira versão usava `startswith` com as chaves ordenadas por
        # comprimento, e "nove" casava em "novembro" (que começa por "nov").
        # Uma data de setembro virava novembro — e a data de admissão de
        # alguém é um facto registado, não um campo de texto livre. Por
        # isso: correspondência exacta, e mais nada.
        mes_num = MESES.get(mes)
        if mes_num:
            try:
                a = int(ano)
                # "30/09/26" é 2026, não 26. Dois dígitos são este século;
                # ninguém escreve 26 como ano de admissão.
                if a < 100:
                    a += 2000
                return _date(a, mes_num, int(dia))
            except ValueError:
                return None
    return None


def h_registrar_manutencao(user, params, ctx):
    from app.models import ManutencaoMaquinario, Maquinario

    prop = _prop3(user, params)
    mq = Maquinario.objects.filter(propriedade__user=user)
    if prop:
        mq = mq.filter(propriedade=prop)
    nome = (params.get("maquina") or "").strip()
    m = mq.filter(nome__icontains=nome).first() if nome else mq.first()
    if not m:
        return {"ok": False, "erro": "máquina não encontrada (informe o nome)"}
    desc = (params.get("descricao") or "").strip()
    if len(desc) < 3:
        return {"ok": False, "erro": "descreva o serviço feito (mín 3 letras)"}
    custo = _num(params.get("custo")) or 0
    data = _data(params.get("data")) or date.today()
    man = ManutencaoMaquinario.objects.create(
        maquinario=m, descricao=desc[:500], custo=custo, data=data
    )
    m.horas_uso = _num(params.get("horimetro")) or m.horas_uso
    m.save(update_fields=["horas_uso"])
    ctx["fontes"].append("interna:manutencao")
    return {
        "ok": True,
        "resposta": f"Manutenção registrada: {m.nome} em {data:%d/%m} — {desc[:80]} (R$ {float(custo):,.2f}).",
        "dados": {"manutencao_id": man.id, "maquina": m.nome},
        "artefato": ("maquinas/revisao", "maquinario"),
    }


def h_registrar_vacina(user, params, ctx):
    from app.models import AnimalIndividual, EventoSanitario, ProtocoloSanitario

    brinco = (params.get("brinco") or "").strip()
    if not brinco:
        return {"ok": False, "erro": "informe o brinco do animal"}
    ind = AnimalIndividual.objects.filter(
        propriedade__user=user, brinco__iexact=brinco
    ).first()
    if not ind:
        return {"ok": False, "erro": f"animal de brinco {brinco} não encontrado"}
    produto = (params.get("produto") or "").strip()[:100]
    if len(produto) < 2:
        return {"ok": False, "erro": "informe o produto aplicado"}
    prot = ProtocoloSanitario.objects.filter(
        propriedade__user=user, nome__icontains=produto
    ).first()
    data = _data(params.get("data")) or date.today()
    ev = EventoSanitario.objects.create(
        animal=ind,
        protocolo=prot,
        tipo="vacina",
        produto=produto,
        dose=(params.get("dose") or "").strip()[:50],
        responsavel=(params.get("responsavel") or "").strip()[:100],
        data=data,
    )
    ctx["fontes"].append("interna:sanidade")
    return {
        "ok": True,
        "resposta": f"Vacina registrada: brinco {ind.brinco} — {produto} em {data:%d/%m}.",
        "dados": {"evento_id": ev.id, "brinco": ind.brinco},
        "artefato": ("sanidade/calendario", "sanidade"),
    }


def h_criar_ordem_compra(user, params, ctx):
    from app.models import OrdemCompra

    prop = _prop3(user, params)
    if not prop:
        return {"ok": False, "erro": "nenhuma propriedade encontrada"}
    forn = (params.get("fornecedor") or "").strip()[:150]
    if len(forn) < 2:
        return {"ok": False, "erro": "informe o fornecedor"}
    valor = _num(params.get("valor"))
    if valor is None or valor <= 0:
        return {"ok": False, "erro": "informe o valor total da ordem"}
    o = OrdemCompra.objects.create(
        propriedade=prop, fornecedor=forn, valor_total=valor, status="RASCUNHO"
    )
    ctx["fontes"].append("interna:ordem_compra")
    return {
        "ok": True,
        "resposta": f"Ordem #{o.id} criada como RASCUNHO: {forn} R$ {float(valor):,.2f}.",
        "dados": {"ordem_id": o.id, "fornecedor": forn, "valor": float(valor)},
        "artefato": ("estoque/ordens", "estoque"),
    }


_CAMPOS_LANC = {"valor", "data", "categoria", "pago"}


def h_editar_lancamento(user, params, ctx):
    from app.models import LancamentoFinanceiro

    lid = _num(params.get("lancamento"))
    if not lid:
        return {"ok": False, "erro": "informe o id do lançamento"}
    lac = LancamentoFinanceiro.objects.filter(
        propriedade__user=user, id=int(lid)
    ).first()
    if not lac:
        return {"ok": False, "erro": f"lançamento #{int(lid)} não encontrado"}
    campo = (params.get("campo") or "").strip().lower()
    if campo not in _CAMPOS_LANC:
        return {"ok": False, "erro": "editável: valor, data, categoria, pago"}
    bruto = params.get("valor")
    if campo == "valor":
        valor = _num(bruto)
        if valor is None:
            return {"ok": False, "erro": "valor numérico inválido"}
    elif campo == "data":
        valor = _data(bruto)
        if not valor:
            return {"ok": False, "erro": "data inválida (use dd/mm/aaaa)"}
    elif campo == "pago":
        valor = str(bruto).strip().lower() in ("sim", "s", "true", "1", "pago", "yes")
    else:
        valor = (bruto or "").strip()[:20]
        if not valor:
            return {"ok": False, "erro": "valor vazio"}
    setattr(lac, campo, valor)
    lac.save(update_fields=[campo])
    ctx["fontes"].append("interna:financeiro")
    return {
        "ok": True,
        "resposta": f"Lançamento #{lac.id} atualizado: {campo} = {valor}.",
        "dados": {"lancamento_id": lac.id, "campo": campo, "valor": str(valor)},
    }


# ── leituras computadas ─────────────────────────────────────────────


def h_lucro_talhao(user, params, ctx):
    """Orcado x realizado por talhao.

    Este handler e' o que a tela "qual talhao da mais lucro" usava. Medido em
    2026-10-05, ele dizia tres coisas erradas sobre dinheiro:

    - contava **despesa nao paga** como custo (filtrava so por `tipo`);
    - **descartava** toda a despesa sem talhao, entao o lucro por talhao saia
      inflado sem nenhum aviso;
    - fazia **um aggregate por talhao** dentro de um `for` (N+1).

    A conta esta agora em `app/services/custo_talhao.py`, com tres consultas
    independentes do numero de talhoes. Este handler ficou como casca: le a
    conta e formata. O que o produtor ve e' o mesmo numero do painel.
    """
    from app.services.custo_talhao import custo_por_talhao, resumo_para_ia

    prop = _prop3(user, params)
    resultado = custo_por_talhao(user, propriedade=prop)
    ctx["fontes"].append("interna:financeiro")

    return {
        "ok": True,
        "resposta": resumo_para_ia(resultado),
        "dados": {
            "custo_por_talhao": resultado.as_dict(),
            # Mantido sob a chave antiga: ha consumidores que leem `ranking`.
            # Nomes novos, mesma verdade - o que mudou foi o que entra no
            # calculo, nao o formato.
            # `as_dict()` ja' devolve o quadro JSON-ready (com `Decimal`
            # convertido na fronteira). Reutilizo-o em vez de remontar a
            # linha aqui: duas listas de campos a divergir e' exactamente
            # como um `Decimal` chega ao `json.dumps` e rebenta o pedido.
            "ranking": [
                l.as_dict() for l in resultado.por_ordem_de_custo() if l.tem_dados
            ],
        },
        "detalhe_pendencias": _pendencias_custo(resultado),
        "artefato": ("financeiro/lucro_talhao", "financeiro"),
    }


def _pendencias_custo(resultado):
    """O que falta preencher, em numeros.

    O `as_dict()` limpo esconde as celulas em `None` - e `None` e' a leitura
    correcta para quem le o quadro, e a leitura errada para quem precisa de
    saber o que ha para preencher. Este bloco diz as duas coisas, para a tela
    poder mostrar "faltam 3 talhoes" em vez de uma coluna vazia.

    Cada chave esta aqui porque e' um `None` ou um zero que ia parecer um
    "nada a fazer" sem ser.
    """
    from decimal import Decimal as _D

    return {
        "nao_alocado_registros": resultado.nao_alocado_registros,
        "nao_alocado_receita": float(resultado.nao_alocado_receita),
        "nao_alocado_despesa": float(resultado.nao_alocado_despesa),
        "talhoes_sem_lancamento": resultado.talhoes_sem_lancamento,
        "comprometido_total": float(
            sum((l.comprometido_despesa for l in resultado.linhas), _D("0"))
        ),
        "talhoes_sem_orcado": [l.talhao for l in resultado.linhas if l.orcado is None],
    }


# Extração média de nutrientes por tonelada colhida (valores de referência
# agronômica — TABELA DE REFERÊNCIA, NÃO uma medição da lavoura).
# (N, P2O5, K2O) em kg/t.
_EXTRACAO = {
    "soja": (70, 35, 80),
    "milho": (25, 15, 30),
    "algodao": (60, 30, 70),
    "algodão": (60, 30, 70),
    "cafe": (50, 12, 55),
    "café": (50, 12, 55),
    "trigo": (30, 15, 25),
    "arroz": (22, 12, 28),
    "feijao": (55, 20, 50),
    "feijão": (55, 20, 50),
}

#: Fontes que podem ser uma produtividade REAL, por palavra. Sem esta lista, o
#: `or 4.0` de antes aceitava qualquer coisa como número de lavoura.
_FONTES_PRODUTIVIDADE = (
    "produtividade_t_ha",
    "produtividade_t",
    "prod_t_ha",
    "produtividade",
    "t_ha",
)


def _produtividade_real(params) -> float | None:
    """A produtividade que o produtor deu, ou `None` — nunca um número inventado.

    Isto existia como `or 4.0`: quando o produtor perguntava "quanto de ureia vai
    na safrinha" sem dizer a produtividade, o sistema assumia 4 t/ha e
    multiplicava pela tabela. Medido: a mesma lavoura com e sem o número dava
    280 kg N/ha e 70 kg N/ha — uma diferença de 4x, causada só por o produtor
    não ter dito o número. E o carimbo de proveniência dizia `interna:solo`,
    o que faz a análise de solo parecer responsável por um número que ela não
    mediu.
    """
    for chave in _FONTES_PRODUTIVIDADE:
        v = _num(params.get(chave))
        if v and v > 0:
            return float(v)
    return None


def h_recomendacao_adubacao(user, params, ctx):
    from app.models import AnaliseSolo, Talhao

    prop = _prop3(user, params)
    nome_t = (params.get("talhao") or "").strip()
    qt = Talhao.objects.filter(propriedade__user=user)
    if prop:
        qt = qt.filter(propriedade=prop)
    talhao = qt.filter(nome__icontains=nome_t).first() if nome_t else None
    qa = AnaliseSolo.objects.filter(talhao__propriedade__user=user).order_by(
        "-data_coleta"
    )
    if prop:
        qa = qa.filter(talhao__propriedade=prop)
    if talhao:
        qa = qa.filter(talhao=talhao)
    a = qa.first()
    if not a:
        return {
            "ok": False,
            "erro": "Não há análise de solo registrada. Cadastre a análise antes de pedir recomendação.",
        }
    cultura = (params.get("cultura") or "").strip().lower()
    prod_t = _produtividade_real(params)
    ext = _EXTRACAO.get(cultura)
    partes = [f"Base: {a.talhao.nome} ({a.data_coleta:%m/%y})"]
    if a.saturacao_bases_v is not None and a.ctc:
        v = float(a.saturacao_bases_v)
        if v < 60:
            nc = (60 - v) * float(a.ctc) / 100
            partes.append(f"Calagem: ~{nc:.1f} t/ha de calcário (V {v:.0f}% → 60%)")
        else:
            partes.append(f"Calagem dispensada (V {v:.0f}%)")
    elif a.ph is not None and float(a.ph) < 5.5:
        partes.append(
            f"pH {float(a.ph):.1f}: considere calagem (sem CTC/V não dá para dosar)"
        )
    if ext and prod_t:
        n, p, k = (x * prod_t for x in ext)
        partes.append(
            f"Reposição p/ {prod_t:g} t/ha de {cultura}: ~{n:.0f} kg N, ~{p:.0f} kg P2O5, ~{k:.0f} kg K2O"
        )
        partes.append(
            "Dose por TONELADA x a produtividade que você informou, com valores de "
            "extração de referência. É o caminho, não a conta fechada."
        )
    elif ext and not prod_t:
        # A cultura é conhecida, mas a produtividade não foi dita. A dose é
        # TANTO x produtividade: sem o segundo número, o primeiro não é nada.
        # O código antigo assumia 4 t/ha e dizia o número com toda a certeza.
        partes.append(
            f"Não dou a dose de NPK para {cultura} sem a produtividade da lavoura: "
            "a reposição é por tonelada colhida, e 1 t/ha ou 4 t/ha muda a dose "
            "em 4x. Diga a produtividade (em t/ha) que eu calculo."
        )
    else:
        partes.append(
            "Informe a cultura (soja, milho, algodão, café, trigo, arroz, feijão) para a dose de NPK"
        )
    if ext and not prod_t:
        # Devolve o que falta, para a próxima volta do produtor responder só isso.
        return {
            "ok": False,
            "pergunta": f"Qual a produtividade esperada da {cultura} em t/ha?",
            "campo": "produtividade_t_ha",
            "resposta": "Adubação: " + ". ".join(partes),
            "dados": {"talhao": a.talhao.nome, "recomendacao": partes},
            "artefato": ("campo/adubacao", "campo"),
        }
    partes[-1] = partes[-1].rstrip(".")
    partes.append("Valide com o agrônomo antes de comprar ou aplicar.")
    ctx["fontes"].append("interna:solo")
    if prod_t:
        # A calagem vem da análise de solo; a reposição NÃO — vem da tabela de
        # extração vezes uma produtividade que o produtor disse. Marcar tudo
        # como `interna:solo` é dizer que a análise mediu uma coisa que não mediu.
        ctx["fontes"].append("referencia:extracao_npk")
    return {
        "ok": True,
        "resposta": "Adubação: " + ". ".join(partes),
        "dados": {"talhao": a.talhao.nome, "recomendacao": partes},
        "artefato": ("campo/adubacao", "campo"),
    }


def h_alerta_pragas(user, params, ctx):
    from app.models import MonitoramentoPraga

    prop = _prop3(user, params)
    qs = MonitoramentoPraga.objects.filter(talhao__propriedade__user=user).order_by(
        "-data"
    )
    if prop:
        qs = qs.filter(talhao__propriedade=prop)
    criticos = [m for m in qs[:30] if m.acima_controle][:8]
    ctx["fontes"].append("interna:mip")
    if not criticos:
        return {
            "ok": True,
            "resposta": "Nenhuma praga acima do nível de controle. ✅",
            "dados": {},
        }
    itens = []
    for m in criticos:
        base = f"🚨 {m.praga} no {m.talhao.nome} ({float(m.nivel_infestacao):g}% > controle {float(m.nivel_controle or 0):g}%)"
        if m.acao_recomendada:
            base += f" — ação: {m.acao_recomendada[:100]}"
        itens.append(base)
    return {
        "ok": True,
        "resposta": "Alerta fitossanitário: " + "; ".join(itens),
        "dados": {"alertas": itens},
        "artefato": ("mip/alerta", "mip"),
    }


def h_relatorio_vacinacao(user, params, ctx):
    from django.db.models import Count, Max

    from app.models import EventoSanitario

    qs = EventoSanitario.objects.filter(animal__propriedade__user=user, tipo="vacina")
    por_prod = list(
        qs.values("produto")
        .annotate(n=Count("id"), ult=Max("data"))
        .order_by("-ult")[:10]
    )
    ctx["fontes"].append("interna:sanidade")
    if not por_prod:
        return {"ok": True, "resposta": "Nenhuma vacinação registrada.", "dados": {}}
    itens = [
        f"{p['produto'] or '(s/produto)'}: {p['n']} doses (últ {p['ult']:%d/%m})"
        for p in por_prod
    ]
    return {
        "ok": True,
        "resposta": f"Vacinação ({qs.count()} registros): " + "; ".join(itens),
        "dados": {
            "total": qs.count(),
            "por_produto": [
                {
                    "produto": p["produto"],
                    "doses": p["n"],
                    "ultima": p["ult"].isoformat(),
                }
                for p in por_prod
            ],
        },
        "artefato": ("sanidade/vacinas", "sanidade"),
    }


def h_simular_cenario(user, params, ctx):
    from app.models import Talhao
    from app.services import simulacao as sim

    prop = _prop3(user, params)
    area = _num(params.get("area_ha"))
    nome_t = (params.get("talhao") or "").strip()
    if not area and nome_t:
        qt = Talhao.objects.filter(propriedade__user=user)
        if prop:
            qt = qt.filter(propriedade=prop)
        t = qt.filter(nome__icontains=nome_t).first()
        if t:
            area = float(t.area_hectare or 0)
    if not area:
        return {"ok": False, "erro": "informe a área (ha) ou o talhão"}
    # Preço, produtividade e custo NÃO TÊM DEFAULT.
    #
    # Eram `or 60`, `or 150`, `or 380` — e a resposta dizia
    # "Simulação 10 ha (60 sc/ha a R$ 150): base R$ 34.000...". Três
    # números inventados, apresentados como se o produtor os tivesse dito.
    #
    # Isto não é como o `umidade: 50`: um número de humidade no canto de
    # um cartão pode ignorar-se. Uma simulação de lucro é uma decisão de
    # plantar ou não plantar. Quem lê "60 sc/ha a R$ 150" e não percebe que
    # foram escolhidos por um `or` decide plantar com números inventados,
    # e o resultado tem o aspecto de um cálculo.
    #
    # A área continua a ser preciso — o produtor deu-a. O resto ou vem
    # dele, ou o simulador diz que não sabe.
    assumidos = []

    def _primeiro(*chaves):
        # Sem `or`: `_num("0")` devolve 0.0, que é falsy, e o `or`
        # passaria ao valor seguinte — transformando um zero que o
        # produtor deu na ausência dele. Um custo de R$ 0/ha é uma
        # informação; None é uma ausência.
        for chave in chaves:
            v = _num(params.get(chave))
            if v is not None:
                return v
        return None

    prod = _primeiro("produtividade", "produtividade_sc_ha")
    if prod is None:
        assumidos.append("produtividade (sc/ha)")

    preco = _primeiro("preco", "preco_sc")
    if preco is None:
        assumidos.append("preço (R$/sc)")

    custo = _primeiro("custo_ha")
    if custo is None:
        assumidos.append("custo (R$/ha)")

    if assumidos:
        return {
            "ok": False,
            "erro": (
                "para simular preciso de: "
                + ", ".join(assumidos)
                + ". Não assumo valores — uma simulação com números que você "
                "não deu parece um cálculo e decide-se o plantio por ela."
            ),
            "faltam": assumidos,
        }

    base = {
        "area_ha": area,
        "produtividade_sc_ha": prod,
        "preco_sc": preco,
        "custo_ha": custo,
    }
    cen = sim.cenarios(base)
    eq = sim.ponto_equilibrio(custo, preco)
    b, p, o = cen["base"], cen["pessimista"], cen["otimista"]
    ctx["fontes"].append("interna:simulacao")
    return {
        "ok": True,
        "resposta": (
            f"Simulação {area:g} ha ({prod:g} sc/ha a R$ {preco:g}): "
            f"base R$ {b['lucro']:,.2f}; pessimista R$ {p['lucro']:,.2f}; "
            f"otimista R$ {o['lucro']:,.2f}. Equilíbrio: {eq['produtividade_equilibrio_sc_ha']} sc/ha."
        ),
        "dados": {"base": b, "cenarios": cen, "equilibrio": eq},
        "artefato": ("simulacao/cenario", "simulacao"),
    }


def h_gerar_lcdpr(user, params, ctx):
    from django.utils import timezone as _tz

    # MEDIDO 2026-10-05: importava `LCDPRGenerator` (`app/services/lcdpr.py`),
    # que e' o gerador INCOMPLETO — nao escreve o 0030, que e' o cadastro do
    # produtor rural pessoa fisica declarante. O botao do ecra usa
    # `LCDPRExporter`. O mesmo produtor, a mesma propriedade e o mesmo ano
    # recebiam ficheiros diferentes conforme perguntassem ao ecra ou ao
    # copiloto. Ver `tests/test_lcdpr_um_ficheiro.py`.

    prop = _prop3(user, params)
    if not prop:
        return {"ok": False, "erro": "nenhuma propriedade encontrada"}
    try:
        ano = int(params.get("ano", _tz.now().year))
    except (TypeError, ValueError):
        ano = _tz.now().year
    try:
        from app.services.lcdpr_export import (
            LCDPRDadosIncompletos,
            LCDPRExporter,
        )

        conteudo = LCDPRExporter(prop, ano).gerar_arquivo()
    except LCDPRDadosIncompletos as e:
        # Falta um dado que o produtor tem de preencher. Nao e' uma avaria, e
        # dizer "falha ao gerar LCDPR" esconde o que fazer.
        return {"ok": False, "erro": str(e)}
    except Exception as e:
        return {"ok": False, "erro": f"falha ao gerar LCDPR: {e}"}
    ctx["fontes"].append("interna:lcdpr")
    # MEDIDO 2026-10-05. Este intent dizia ao produtor
    #   "LCDPR {ano} de {nome} gerado: {caminho}"
    # com `caminho` a ser o resultado de `gerar_arquivo()` — que devolve o
    # **conteudo** do ficheiro, uma string. Nao ha ficheiro em disco: a
    # variable chamava-se `caminho`, o `dados["arquivo"]` levava texto, e o
    # produtor recebia o LCDPR inteiro colado na conversa, com `ok: True` e
    # a palavra "gerado". O sistema afirmava um ficheiro que nao existe — o
    # inverso exacto do que `validators.py:40` permite.
    #
    # O ficheiro real e' descarregado em `/api/exportar-lcdpr/`, que e' o
    # caminho que o botao do ecra usa. Aponta-se para la em vez de inventar
    # um caminho.
    n_linhas = conteudo.count("\r\n") + conteudo.count("\n") - 1
    return {
        "ok": True,
        "resposta": (
            f"LCDPR {ano} de {prop.nome} preparado: {n_linhas} registos. "
            f"Para descarregar o ficheiro, use "
            f"/api/exportar-lcdpr/?propriedade_id={prop.id}&ano={ano}. "
            "Eu não escrevo ficheiros em disco — quem o faz é o ecrã de "
            "Financeiro, no separador Exportar."
        ),
        "dados": {
            "ano": ano,
            "propriedade_id": prop.id,
            "registos": n_linhas,
            "download": f"/api/exportar-lcdpr/?propriedade_id={prop.id}&ano={ano}",
        },
        "artefato": (f"lcdpr/{ano}", "financeiro"),
    }


# ---------------------------------------------------------------------------
# Helpers para cadastro de funcionários (usados em h_cadastrar_funcionario)
# ---------------------------------------------------------------------------

import re

INTENTS3 = {
    "editar_safra": {
        "prompt_confirmacao": (
            "Alterar esta safra? Preciso da safra, do campo e do novo valor."
        ),
        "descricao": "INSTRUÇÃO IA: use para 'muda/edita/corrige a safra' (área, produção, datas, nome). Coleta safra+campo+valor e pede confirmação.",
        "exemplos": [
            "muda a data de início da safra",
            "corrige a área plantada da safra de milho",
            "edita a expectativa de colheita",
            "altera a variedade plantada no talhão",
            "atualiza o custo estimado da safra",
            "muda o nome da safra",
            "ajusta os dados do plantio",
            "objetivo de produtividade",
        ],
        "flags": ["safra.write"],
        "required_fields": ["safra", "campo", "valor"],
        "requires_confirmation": True,
        "handler": h_editar_safra,
    },
    "excluir_safra": {
        "prompt_confirmacao": (
            "Apagar esta safra, com as tarefas e aplicações dela? Não dá para desfazer."
        ),
        "descricao": "INSTRUÇÃO IA: use para 'deleta/apaga/cancela a safra'. SEMPRE pede confirmação e avisa o que vai junto.",
        "exemplos": [
            "deleta a safra de feijão que criei errado",
            "apaga o registro da safrinha",
            "cancela a safra 2025 no sistema",
            "remove a safra duplicada",
            "exclui aquela safra teste",
            "plantio abortado",
        ],
        "flags": ["safra.write"],
        "required_fields": ["safra"],
        "requires_confirmation": True,
        "handler": h_excluir_safra,
    },
    "cadastrar_maquina": {
        "prompt_confirmacao": (
            "Registar esta máquina? Preciso do nome e do tipo (trator, colheitadeira, pulverizador…)."
        ),
        "descricao": "INSTRUÇÃO IA: use para 'cadastra trator/colheitadeira/máquina'. Coleta nome+tipo e pede confirmação.",
        "exemplos": [
            "cadastra um trator novo",
            "adiciona a colheitadeira no sistema",
            "cria o registro do pulverizador",
            "cadastra a plantadeira",
            "registra o drone de pulverização",
            "cadastra o pivô central novo",
            "registra a bomba de água nova",
            "cadastra o gerador de energia",
            "insere o caminhão na frota",
            "adiciona a ensiladeira",
            "cadastra a roçadeira",
        ],
        "flags": ["maquinario.create"],
        "required_fields": ["nome", "tipo"],
        "requires_confirmation": True,
        "handler": h_cadastrar_maquina,
    },
    "cadastrar_funcionario": {
        "prompt_confirmacao": (
            "Registar este trabalhador na equipe? Preciso do nome e da função."
        ),
        "descricao": (
            "INSTRUÇÃO IA: use para 'cadastra uma PESSOA — funcionário, "
            "tratorista, vaqueiro, diarista, mecânico, motorista'. "
            "Coleta nome+cargo e pede confirmação. NÃO use para "
            "máquinas: trator, colheitadeira e caminhão são "
            "'cadastrar_maquina'. A diferença entre pessoa e máquina é o "
            "campo — pessoa tem função (vaqueiro), máquina tem tipo "
            "(trator)."
        ),
        "exemplos": [
            "cadastra o vaqueiro Carlos",
            "adiciona um tratorista novo na equipe",
            "cria o registro do diarista",
            "cadastra o mecanico da fazenda",
            "registra a entrada do motorista",
            "cadastra a vaqueira Maria",
            "insere o gerente da propriedade",
            "contrata um tecnico agricola",
            "como se cadastrar um funcionario",
            "cadastra o caseiro",
        ],
        "flags": ["funcionario.create"],
        "required_fields": ["nome", "cargo"],
        "requires_confirmation": True,
        # Referência TARDA: o handler é definido mais abaixo neste módulo,
        # porque depende de `_CARGOS`. A ligação é feita em
        # `_ligar_cadastro_funcionario()`, no fim do ficheiro.
        "handler": None,
    },
    "registrar_manutencao": {
        "prompt_confirmacao": ("Registar esta manutenção na máquina?"),
        "descricao": "INSTRUÇÃO IA: use para 'registra troca de óleo/conserto/revisão feita'. Coleta máquina+descrição e confirma.",
        "exemplos": [
            "registra a troca de óleo do trator",
            "anota que arrumou o pneu da colheitadeira",
            "aponta a manutenção do caminhão",
            "registra a manutenção preventiva",
            "anota a troca de filtros",
            "registra a lubrificação geral",
            "anota o conserto do motor",
            "quando foi a última troca de correia",
            "histórico de manutenção da máquina",
            "registra a substituição da bateria",
            "custo de oficina do mês",
        ],
        "flags": ["maquinario.write"],
        "required_fields": ["maquina", "descricao"],
        "requires_confirmation": True,
        "handler": h_registrar_manutencao,
    },
    "registrar_vacina": {
        "prompt_confirmacao": ("Registar esta vacina no brinco do animal?"),
        "descricao": "INSTRUÇÃO IA: use para 'anota que vacinou / registra vacina do brinco X'. Coleta brinco+produto e confirma.",
        "exemplos": [
            "anota que o lote 3 foi vacinado",
            "registra a aplicação de vermífugo",
            "anota a dose de ivermectina",
            "lança a vacinação da bezerrada",
            "registra a vacina da clostridiose",
            "lança a vacinação das matrizes",
            "anota a vacinação do gado de leite",
            "quando revacina os bezerros",
            "protocolo sanitário cumprido",
        ],
        "flags": ["sanidade.write"],
        "required_fields": ["brinco", "produto"],
        "requires_confirmation": True,
        "handler": h_registrar_vacina,
    },
    "criar_ordem_compra": {
        "prompt_confirmacao": (
            "Criar um rascunho de pedido de compra? Fica pendente, para você rever antes de enviar."
        ),
        "descricao": "INSTRUÇÃO IA: use para 'gera pedido de compra / faz pedido de diesel/adubo'. Cria como RASCUNHO e confirma.",
        "exemplos": [
            "gera pedido de compra de glifosato",
            "faz o pedido de diesel",
            "gera a ordem de compra de calcário",
            "pede mais sal proteinado",
            "registra a compra de vacinas",
            "cotação da cooperativa",
            "pedido de embalagens",
            "compra de arame",
            "sementes híbridas",
        ],
        "flags": ["estoque.create"],
        "required_fields": ["fornecedor", "valor"],
        "requires_confirmation": True,
        "handler": h_criar_ordem_compra,
    },
    "editar_lancamento": {
        "prompt_confirmacao": (
            "Alterar este lançamento? Preciso do lançamento, do campo e do novo valor."
        ),
        "descricao": "INSTRUÇÃO IA: use para 'altera/corrige o lançamento/boleto/nota' (valor, data, categoria, pago). Pede confirmação.",
        "exemplos": [
            "altera o valor daquela nota fiscal",
            "muda a data de vencimento do boleto",
            "corrige o valor pago no diesel",
            "edita o lançamento do banco",
            "altera a categoria do gasto",
            "recibo do frete",
            "juros do empréstimo",
        ],
        "flags": ["fin.write"],
        "required_fields": ["lancamento", "campo", "valor"],
        "requires_confirmation": True,
        "handler": h_editar_lancamento,
    },
    "lucro_talhao": {
        "descricao": "INSTRUÇÃO IA: use para 'qual talhão deu mais lucro', 'rentabilidade por hectare', 'DRE por talhão'. Só leitura, calcula de lançamentos vinculados.",
        "exemplos": [
            "qual talhão deu mais lucro",
            "rentabilidade por hectare",
            "mostra o DRE do talhão",
            "qual área deu prejuízo",
            "margem bruta por cultura",
            "compara o lucro dos talhões",
            "rentabilidade da fazenda",
            "lucro bruto da colheita",
            "ponto de equilíbrio",
            "receita de cada talhão",
            "resultado operacional",
            "ROI da safrinha",
            "lucro por saco",
            "balanço do pivô",
            "viabilidade econômica",
            "gleba mais eficiente",
            "mapa de lucratividade",
            "retorno do plantio",
        ],
        "flags": ["fin.read"],
        "handler": h_lucro_talhao,
    },
    "recomendacao_adubacao": {
        "descricao": "INSTRUÇÃO IA: use para 'quanto de calcário/adubo/NPK', 'recomendação de adubação'. Lê análise de solo + tabela de extração. Estimativa — validar com agrônomo.",
        "exemplos": [
            "quanto eu jogo de calcário nesse talhão",
            "faz a recomendação de NPK",
            "lê a análise de solo e recomenda o adubo",
            "calcula a calagem",
            "recomenda adubação de plantio da soja",
            "quanto de ureia vai na safrinha",
            "adubação de cobertura",
            "gesso agrícola",
            "boro e zinco",
            "fertirrigação",
            "reposição de nutrientes",
            "fósforo pra plantar",
            "necessidade de nitrogênio",
            "cloreto de potássio",
            "momento ideal do nitrogênio",
        ],
        "flags": ["campo.read"],
        "handler": h_recomendacao_adubacao,
    },
    "alerta_pragas": {
        "descricao": "INSTRUÇÃO IA: use para 'tem alerta de ferrugem/lagarta', 'risco de praga', 'pressão de pragas'. Só leitura, do MIP interno + ação recomendada.",
        "exemplos": [
            "tem alerta de ferrugem",
            "qual a incidência de percevejo",
            "avisa se tiver foco de lagarta",
            "como tá a pressão de pragas",
            "tem alerta fitossanitário",
            "risco de pulgão essa semana",
            "alerta de broca e cigarrinha",
            "mosca branca e ácaro",
            "risco de bicudo",
            "nematoide na área",
            "lagarta do cartucho",
            "mancha alvo",
            "antracnose",
        ],
        "flags": ["mip.read"],
        "handler": h_alerta_pragas,
    },
    "relatorio_vacinacao": {
        "descricao": "INSTRUÇÃO IA: use para 'relatório de vacinação', 'quais animais faltam vacinar', 'status sanitário'. Só leitura.",
        "exemplos": [
            "relatório de vacinação contra aftosa",
            "quais vacinas foram aplicadas",
            "verifica o status sanitário do rebanho",
            "quando foi a última vacina",
            "gera o calendário sanitário",
            "campanha de vacinação",
            "custo da vacina por cabeça",
            "quais animais faltam vacinar",
            "bezerros não imunizados",
            "carência do antibiótico",
            "declaração de vacinação",
        ],
        "flags": ["sanidade.read"],
        "handler": h_relatorio_vacinacao,
    },
    "gerar_lcdpr": {
        "descricao": "INSTRUÇÃO IA: use para 'gera o LCDPR / livro caixa digital'. Só leitura, usa lançamentos do ano.",
        "exemplos": [
            "gera o livro caixa digital",
            "gera o LCDPR deste ano",
            "arquivo do produtor rural pra contabilidade",
            "valida o LCDPR do ano passado",
            "conciliação bancária",
            "extrato bancário",
            "imposto de renda da fazenda",
            "fechamento contábil do mês",
            "balancete de verificação",
            "depreciação de máquinas",
            "funrural",
            "notas fiscais pro contador",
            "faturamento pra contabilidade",
            "sistema contábil",
        ],
        "flags": ["fin.read"],
        "handler": h_gerar_lcdpr,
    },
    "simular_cenario": {
        "descricao": "INSTRUÇÃO IA: use para 'simula lucro/cenário', 'e se colher X', 'vale a pena plantar'. Calcula base/pessimista/otimista + equilíbrio.",
        "exemplos": [
            "simula o lucro da soja",
            "e se colher 70 sacas por hectare",
            "vale a pena plantar milho",
            "simula cenário pessimista",
            "qual o ponto de equilíbrio",
            "compara cenários de preço",
        ],
        "flags": ["simulacao.read"],
        "handler": h_simular_cenario,
    },
}


# ----------------------------------------------------------------------


# Liga o handler do cadastro de funcionario, definido acima mas depois do
# literal INTENTS3. Sem esta linha o intent EXISTE e devolve None sem erro
# nenhum — que e' a pior forma de falhar, porque parece que correu.
def _ligar_cadastro_funcionario():
    INTENTS3["cadastrar_funcionario"]["handler"] = h_cadastrar_funcionario


_ligar_cadastro_funcionario()
