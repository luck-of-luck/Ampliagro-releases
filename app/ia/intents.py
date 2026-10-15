"""Catálogo de intents da IA local — instruções + handlers auditados.

Cada intent declara: o que entende (exemplos), quais FLAGS exige, quais
fontes pode tocar e como executa. O sandbox (`sandbox.py`) lê este catálogo:
nada executa fora daqui.
"""

from datetime import date

from app.ia import palco
from app.ia.fontes import fetch_permitido

# ---------------------------------------------------------------- helpers


def _prop(user, params):
    from app.models import Propriedade

    pid = params.get("propriedade_id")
    qs = Propriedade.objects.filter(user=user)
    if pid:
        return qs.filter(id=pid).first()
    nome = (params.get("propriedade") or "").strip()
    if nome:
        return qs.filter(nome__icontains=nome).first()
    return qs.first()


def _coords(user, prop, ctx, params=None):
    """Lat/lon em 3 níveis: (1) cidade arbitrária em params.cidade
    (ex: 'temperatura para Muzambinho'); (2) estação/GPS da propriedade;
    (3) geocode cidade/UF da fazenda. Tudo com cache."""
    from django.core.cache import cache

    from app.models import EstacaoMeteo

    params = params or {}
    cidade_livre = (params.get("cidade") or "").strip()
    if cidade_livre:
        ck = f"ia:geo:livre:{cidade_livre.lower()}"
        hit = cache.get(ck)
        if hit:
            ctx["fontes"].append("cache:geocode")
            return hit["lat"], hit["lon"], cidade_livre
        try:
            js, host = fetch_permitido(
                "https://geocoding-api.open-meteo.com/v1/search",
                user,
                prop,
                params={"name": cidade_livre, "country": "BR", "count": 1},
            )
            ctx["fontes"].append(f"padrao:{host}")
            if js.get("results"):
                r = js["results"][0]
                cache.set(ck, {"lat": r["latitude"], "lon": r["longitude"]}, 86400)
                return r["latitude"], r["longitude"], cidade_livre
        except Exception as e:
            ctx["fontes"].append(f"padrao:geocode_falhou:{e}")
            return None, None, None

    est = (
        EstacaoMeteo.objects.filter(propriedade=prop, ativa=True)
        .exclude(latitude=None)
        .first()
    )
    if est:
        ctx["fontes"].append("interna:estacao_meteo")
        return float(est.latitude), float(est.longitude), f"estação {est.nome}"
    if getattr(prop, "latitude", None) and getattr(prop, "longitude", None):
        ctx["fontes"].append("interna:propriedade_gps")
        return float(prop.latitude), float(prop.longitude), prop.nome
    if prop.cidade:
        ck = f"ia:geo:{(prop.cidade or '').lower()}:{(prop.uf or '').lower()}"
        hit = cache.get(ck)
        if hit:
            ctx["fontes"].append("cache:geocode")
            return hit["lat"], hit["lon"], prop.cidade
        url = "https://geocoding-api.open-meteo.com/v1/search"
        try:
            js, host = fetch_permitido(
                url,
                user,
                prop,
                params={"name": prop.cidade, "country": "BR", "count": 5},
            )
            ctx["fontes"].append(f"padrao:{host}")
            escolha = None
            for r in js.get("results", []):
                if not prop.uf or prop.uf.upper() in (r.get("admin1") or "").upper():
                    escolha = r
                    break
            escolha = escolha or (js.get("results", [None])[0])
            if escolha:
                cache.set(
                    ck,
                    {"lat": escolha["latitude"], "lon": escolha["longitude"]},
                    86400,
                )
                return escolha["latitude"], escolha["longitude"], prop.cidade
        except Exception as e:
            ctx["fontes"].append(f"padrao:geocode_falhou:{e}")
    return None, None, None


# ---------------------------------------------------------------- handlers


def h_clima_agora(user, params, ctx):
    from app.ia.fontes import fetch_permitido as _fp

    prop = _prop(user, params)
    if not prop:
        return {"ok": False, "erro": "nenhuma propriedade encontrada"}
    lat, lon, origem = _coords(user, prop, ctx, params)
    if lat is None:
        return {"ok": False, "erro": "sem coordenadas: cadastre estação ou cidade/UF"}
    js, host = _fp(
        "https://api.open-meteo.com/v1/forecast",
        user,
        prop,
        params={
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code",
            "timezone": "auto",
        },
    )
    ctx["fontes"].append(f"padrao:{host}")
    cur = (js or {}).get("current", {})
    local = origem if params.get("cidade") else f"{prop.nome} ({origem})"
    resposta = (
        f"Agora em {local}: {cur.get('temperature_2m')}°C, "
        f"umidade {cur.get('relative_humidity_2m')}%, chuva {cur.get('precipitation')} mm."
    )
    return {
        "ok": True,
        "resposta": resposta,
        "dados": {"propriedade": prop.nome, "origem": origem, "atual": cur},
        "artefato": (f"clima/{prop.id}", "clima"),
    }


def h_vai_chover(user, params, ctx):
    prop = _prop(user, params)
    if not prop:
        return {"ok": False, "erro": "nenhuma propriedade encontrada"}
    try:
        horas = min(max(int(params.get("horas", 24)), 1), 72)
    except (TypeError, ValueError):
        horas = 24
    lat, lon, origem = _coords(user, prop, ctx, params)
    if lat is None:
        return {"ok": False, "erro": "sem coordenadas: cadastre estação ou cidade/UF"}
    from app.ia.fontes import fetch_permitido as _fp

    js, host = _fp(
        "https://api.open-meteo.com/v1/forecast",
        user,
        prop,
        params={
            "latitude": lat,
            "longitude": lon,
            "hourly": "precipitation_probability,precipitation",
            "forecast_days": 3,
            "timezone": "auto",
        },
    )
    ctx["fontes"].append(f"padrao:{host}")
    hourly = (js or {}).get("hourly", {})
    probs = hourly.get("precipitation_probability") or []
    precs = hourly.get("precipitation") or []
    # strict=False explicito: sao arrays de API externa e o Open-Meteo nao
    # garante tamanho igual. Zip trunca no menor, que e o comportamento
    # desejado; strict=True levantaria e transformaria uma previsao
    # degradada em erro 500.
    janela = list(zip(probs, precs, strict=False))[:horas]
    pico = max([p or 0 for p, _ in janela], default=0)
    chuva_mm = round(sum([(v or 0) for _, v in janela]), 1)
    if pico >= 60:
        veredito = "vai chover"
    elif pico >= 30:
        veredito = "pode chover"
    else:
        veredito = "não deve chover"
    resposta = (
        f"{veredito.capitalize()} em {origem if params.get('cidade') else prop.nome} nas próximas {horas}h "
        f"(pico {pico}% de probabilidade, ~{chuva_mm} mm acumulados). Fonte: {origem}."
    )
    return {
        "ok": True,
        "resposta": resposta,
        "dados": {
            "propriedade": prop.nome,
            "horas": horas,
            "pico_prob": pico,
            "chuva_mm": chuva_mm,
            "veredito": veredito,
        },
        "artefato": (f"chuva/{prop.id}", "clima"),
    }


def _device_irrigacao(user, prop, params):
    from app.models import Device

    eui = (params.get("device_eui") or "").strip()
    if eui:
        return Device.objects.filter(propriedade=prop, device_eui__iexact=eui).first()
    nome = (params.get("nome") or "irrig").strip()
    return (
        Device.objects.filter(propriedade=prop, nome__icontains=nome).first()
        or Device.objects.filter(propriedade=prop, tipo="NIVEL").first()
    )


def h_irrigador(user, params, ctx, ligar=True):
    from app.ia.comandos import enfileirar_comando

    prop = _prop(user, params)
    if not prop:
        return {"ok": False, "erro": "nenhuma propriedade encontrada"}
    dev = _device_irrigacao(user, prop, params)
    if not dev:
        return {
            "ok": False,
            "erro": "irrigador não encontrado: informe device_eui ou cadastre o device",
        }
    if not params.get("confirm"):
        acao = "ligar" if ligar else "desligar"
        # Estado neutro (PENDING), NÃO erro: pedir confirmação de segurança
        # antes de acionar bomba física não é falha — não suja métricas.
        return {
            "ok": True,
            "needs_confirm": True,
            "resposta": f"confirme para {acao} o irrigador {dev.nome} (envie confirm=true)",
            "dados": {"device_eui": dev.device_eui, "device_nome": dev.nome},
        }
    comando = "valve_open" if ligar else "valve_close"
    try:
        cmd, criado = enfileirar_comando(dev, comando, {"via": "ia_sandbox"})
    except RuntimeError as e:
        return {"ok": False, "erro": str(e)}
    ctx["fontes"].append("interna:comando_device")
    acao = "ligado" if ligar else "desligado"
    detalhe = (
        f"(comando #{cmd.id} na fila)"
        if criado
        else f"(comando #{cmd.id} já estava na fila)"
    )
    return {
        "ok": True,
        "resposta": f"Irrigador {dev.nome} {acao} {detalhe}.",
        "dados": {"comando_id": cmd.id, "device": dev.nome, "acao": comando},
        "artefato": (f"irrigador/{dev.id}", "comando"),
    }


def h_associar_tarefa(user, params, ctx):
    from app.models import AtividadePlanejada, PlanoSafra, Propriedade, Safra

    titulo = (params.get("titulo") or params.get("tarefa") or "").strip()
    if len(titulo) < 3:
        return {"ok": False, "erro": "informe o título da tarefa (mín 3 letras)"}
    prop = _prop(user, params)
    plano = None
    if params.get("plano_id"):
        plano = PlanoSafra.objects.filter(
            id=params["plano_id"], safra__propriedade__user=user
        ).first()
    if not plano and prop:
        plano = PlanoSafra.objects.filter(safra__propriedade=prop).first()
    if not plano:
        plano = PlanoSafra.objects.filter(safra__propriedade__user=user).first()
    if not plano:
        # sem plano: cria um na safra mais recente em vez de travar
        safra = None
        if prop:
            safra = Safra.objects.filter(propriedade=prop).order_by("-ano").first()
        if not safra:
            safra = (
                Safra.objects.filter(propriedade__user=user).order_by("-ano").first()
            )
        if not safra:
            return {"ok": False, "erro": "crie uma safra antes de associar tarefas"}
        plano = PlanoSafra.objects.create(safra=safra)
    data_prev = params.get("data") or str(date.today())
    responsavel = (params.get("responsavel") or "").strip()[:100]
    func_obj = None
    cargo_alvo = ""
    # tenta achar um funcionário citado no título ("...para o João Gomes")
    from app.models import CARGOS
    from app.models import Funcionario as _Func
    from app.models import area_do_cargo as _area_do_cargo

    _tl = titulo.lower()
    if not responsavel:
        for _f in _Func.objects.filter(propriedade__user=user):
            if _f.nome and len(_f.nome) > 2 and _f.nome.lower() in _tl:
                responsavel = _f.nome
                func_obj = _f
                break
    # tenta achar uma PROFISSÃO citada ("...pro mecânico", "...o tratorista")
    if not cargo_alvo:
        for _key, _label in CARGOS:
            if _key in ("OUTRO",):
                continue
            _words = [_w.lower() for _w in _label.split() if len(_w) > 3]
            if any(_w in _tl for _w in _words) or _key.lower() in _tl.replace(" ", "_"):
                cargo_alvo = _key
                break
    if cargo_alvo and not func_obj:
        func_obj = (
            _Func.objects.filter(
                propriedade__user=user, cargo=cargo_alvo, ativo=True
            ).first()
            or _Func.objects.filter(propriedade__user=user, cargo=cargo_alvo).first()
        )
        if func_obj and not responsavel:
            responsavel = func_obj.nome
    setor = _area_do_cargo(cargo_alvo) if cargo_alvo else ""
    atv = AtividadePlanejada.objects.create(
        plano=plano,
        nome=titulo[:100],
        data_prevista=data_prev,
        custo_estimado=params.get("custo") or 0,
        responsavel=responsavel,
        cargo_alvo=cargo_alvo,
        setor=setor,
        funcionario=func_obj,
    )
    ctx["fontes"].append("interna:atividade_planejada")
    quem = responsavel or (cargo_alvo.lower().replace("_", " ") if cargo_alvo else "")
    return {
        "ok": True,
        "resposta": f"Tarefa '{atv.nome}' associada ao plano {plano} para {data_prev}."
        + (f" Responsável: {quem}." if quem else ""),
        "dados": {
            "atividade_id": atv.id,
            "plano": str(plano),
            "responsavel": responsavel,
            "cargo_alvo": cargo_alvo,
            "funcionario_id": func_obj.id if func_obj else None,
        },
        "artefato": (f"tarefa/{atv.id}", "tarefa"),
    }


def h_status_sensores(user, params, ctx):
    from django.db.models import Count

    from app.models import Device, TelemetryData

    prop = _prop(user, params)
    qs = Device.objects.filter(propriedade__user=user)
    if prop:
        qs = qs.filter(propriedade=prop)
    total = qs.count()
    por_tipo = list(qs.values("tipo").annotate(n=Count("id")))
    sem_push = qs.filter(ultimo_push=None).count()
    ctx["fontes"].append("interna:devices+telemetria")
    resposta = (
        f"{total} sensores"
        + (f" em {prop.nome}" if prop else "")
        + f" ({sem_push} sem nenhum push). "
        + ", ".join(f"{t['tipo']}: {t['n']}" for t in por_tipo)
    )
    return {
        "ok": True,
        "resposta": resposta,
        "dados": {"total": total, "por_tipo": por_tipo, "sem_push": sem_push},
        "artefato": ("sensores/resumo", "sensor"),
    }


def h_previsao_estendida(user, params, ctx):
    from app.ia.fontes import fetch_permitido as _fp

    prop = _prop(user, params)
    if not prop:
        return {"ok": False, "erro": "nenhuma propriedade encontrada"}
    lat, lon, origem = _coords(user, prop, ctx, params)
    if lat is None:
        return {"ok": False, "erro": "sem coordenadas: cadastre estação ou cidade/UF"}
    js, host = _fp(
        "https://api.open-meteo.com/v1/forecast",
        user,
        prop,
        params={
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum",
            "forecast_days": 3,
            "timezone": "auto",
        },
    )
    ctx["fontes"].append(f"padrao:{host}")
    daily = (js or {}).get("daily", {})
    dias = []
    for i, d in enumerate(daily.get("time", [])[:3]):
        dias.append(
            f"{d[5:]}: {daily['temperature_2m_min'][i]}–{daily['temperature_2m_max'][i]}°C, "
            f"chuva {daily['precipitation_probability_max'][i]}% ({daily['precipitation_sum'][i]} mm)"
        )
    return {
        "ok": True,
        "resposta": f"3 dias em {prop.nome} ({origem}): " + " | ".join(dias),
        "dados": {"propriedade": prop.nome, "dias": dias},
        "artefato": (f"previsao/{prop.id}", "clima"),
    }


def h_melhor_pulverizar(user, params, ctx):
    from app.ia.fontes import fetch_permitido as _fp

    prop = _prop(user, params)
    if not prop:
        return {"ok": False, "erro": "nenhuma propriedade encontrada"}
    lat, lon, origem = _coords(user, prop, ctx, params)
    if lat is None:
        return {"ok": False, "erro": "sem coordenadas: cadastre estação ou cidade/UF"}
    js, host = _fp(
        "https://api.open-meteo.com/v1/forecast",
        user,
        prop,
        params={
            "latitude": lat,
            "longitude": lon,
            "hourly": "wind_speed_10m,precipitation_probability",
            "forecast_days": 2,
            "timezone": "auto",
        },
    )
    ctx["fontes"].append(f"padrao:{host}")
    hourly = (js or {}).get("hourly", {})
    boas = []
    for t, v, p in zip(  # noqa: B905 - arrays de API externa, ver nota acima
        hourly.get("time", []),
        hourly.get("wind_speed_10m", []),
        hourly.get("precipitation_probability", []),
    ):
        if (v or 99) < 10 and (p or 99) < 30:
            boas.append(f"{t[5:].replace('T', ' ')}h (vento {v} km/h)")
        if len(boas) >= 3:
            break
    if boas:
        resposta = f"Melhores janelas p/ pulverizar em {prop.nome}: " + "; ".join(boas)
    else:
        resposta = f"Sem janela ideal (vento <10 km/h e chuva <30%) nas próximas 48h em {prop.nome}."
    return {
        "ok": True,
        "resposta": resposta,
        "dados": {"propriedade": prop.nome, "janelas": boas},
        "artefato": (f"pulverizar/{prop.id}", "clima"),
    }


def h_resumo_safra(user, params, ctx):
    from django.db.models import Count, Sum
    from django.utils import timezone as _tz

    from app.models import Safra

    prop = _prop(user, params)
    qs = Safra.objects.filter(propriedade__user=user)
    if prop:
        qs = qs.filter(propriedade=prop)
    try:
        ano = int(params.get("ano", _tz.now().year))
    except (TypeError, ValueError):
        ano = _tz.now().year
    qs = qs.filter(ano=ano)
    agg = qs.aggregate(
        n=Count("id"),
        area=Sum("area_plantada"),
        prod=Sum("producao_total"),
        rec=Sum("receita_estimada"),
    )
    ctx["fontes"].append("interna:safra")
    nome = prop.nome if prop else "todas as propriedades"
    resposta = (
        f"Safra {ano} ({nome}): {agg['n'] or 0} safras, "
        f"{float(agg['area'] or 0):.1f} ha plantados, "
        f"{float(agg['prod'] or 0):.1f} produção total, "
        f"R$ {float(agg['rec'] or 0):,.2f} receita estimada."
    )
    return {
        "ok": True,
        "resposta": resposta,
        "dados": {"ano": ano, "total": agg["n"], "area": float(agg["area"] or 0)},
        "artefato": (f"safra/{ano}", "safra"),
    }


def h_resumo_financeiro(user, params, ctx):
    from django.db.models import Sum
    from django.utils import timezone as _tz

    from app.models import LancamentoFinanceiro

    prop = _prop(user, params)
    qs = LancamentoFinanceiro.objects.filter(propriedade__user=user)
    if prop:
        qs = qs.filter(propriedade=prop)
    hoje = _tz.now().date()
    try:
        mes = int(params.get("mes", hoje.month))
        ano = int(params.get("ano", hoje.year))
    except (TypeError, ValueError):
        mes, ano = hoje.month, hoje.year
    qs = qs.filter(data__year=ano, data__month=mes)
    rec = qs.filter(tipo="RECEITA").aggregate(s=Sum("valor"))["s"] or 0
    des = qs.filter(tipo="DESPESA").aggregate(s=Sum("valor"))["s"] or 0
    apagar = qs.filter(tipo="DESPESA", pago=False).aggregate(s=Sum("valor"))["s"] or 0
    ctx["fontes"].append("interna:financeiro")
    return {
        "ok": True,
        "resposta": (
            f"Financeiro {mes:02d}/{ano}: receitas R$ {float(rec):,.2f}, "
            f"despesas R$ {float(des):,.2f}, saldo R$ {float(rec - des):,.2f}, "
            f"a pagar R$ {float(apagar):,.2f}."
        ),
        "dados": {"receitas": float(rec), "despesas": float(des)},
        "artefato": (f"fin/{ano}-{mes:02d}", "financeiro"),
    }


def h_consultar_estoque(user, params, ctx):
    from app.models import EstoqueItem, Insumo

    prop = _prop(user, params)
    nome = (params.get("item") or params.get("nome") or "").strip()
    linhas, criticos = [], []
    # 1) Itens do estoque (almoxarifado)
    qe = EstoqueItem.objects.filter(propriedade__user=user)
    if prop:
        qe = qe.filter(propriedade=prop)
    if nome:
        qe = qe.filter(nome__icontains=nome)
    for i in qe.order_by("nome")[:10]:
        linhas.append(f"{i.nome}: {i.quantidade} {i.unidade}")
        if float(i.quantidade_minima or 0) and float(i.quantidade) < float(
            i.quantidade_minima
        ):
            criticos.append(i.nome)
    # 2) Insumos agrícolas
    qi = Insumo.objects.filter(propriedade__user=user)
    if prop:
        qi = qi.filter(propriedade=prop)
    if nome:
        qi = qi.filter(nome__icontains=nome)
    for i in qi.order_by("nome")[:10]:
        linhas.append(f"{i.nome}: {i.quantidade} {i.unidade}")
        if i.estoque_minimo and float(i.quantidade) < float(i.estoque_minimo):
            criticos.append(i.nome)
    ctx["fontes"].append("interna:estoque+insumo")
    if not linhas:
        return {
            "ok": True,
            "resposta": "Nada no estoque para esse filtro.",
            "dados": {},
        }
    extra = ""
    if criticos:
        extra = " Abaixo do mínimo: " + ", ".join(sorted(set(criticos))) + "."
    return {
        "ok": True,
        "resposta": "Estoque: " + "; ".join(linhas) + "." + extra,
        "dados": {"itens": linhas, "criticos": sorted(set(criticos))},
        "artefato": ("estoque/resumo", "estoque"),
    }


def h_listar_tarefas(user, params, ctx):
    from app.models import AtividadePlanejada

    qs = AtividadePlanejada.objects.filter(
        plano__safra__propriedade__user=user, concluida=False
    ).order_by("data_prevista")[:10]
    ctx["fontes"].append("interna:atividade_planejada")
    if not qs:
        return {
            "ok": True,
            "resposta": "Nenhuma tarefa pendente. Tudo em dia!",
            "dados": {},
        }
    linhas = [
        f"#{t.id} {t.nome} ({t.data_prevista})"
        + (f" — {t.responsavel}" if t.responsavel else "")
        for t in qs
    ]
    return {
        "ok": True,
        "resposta": "Tarefas pendentes: " + "; ".join(linhas),
        "dados": {"tarefas": linhas},
    }


def h_concluir_tarefa(user, params, ctx):
    from app.models import AtividadePlanejada

    qs = AtividadePlanejada.objects.filter(
        plano__safra__propriedade__user=user, concluida=False
    )
    t = None
    if params.get("id"):
        t = qs.filter(id=params["id"]).first()
    elif params.get("titulo"):
        t = qs.filter(nome__icontains=params["titulo"]).first()
    if not t:
        return {"ok": False, "erro": "tarefa não encontrada (informe id ou título)"}
    t.concluida = True
    t.save(update_fields=["concluida"])
    ctx["fontes"].append("interna:atividade_planejada")
    return {
        "ok": True,
        "resposta": f"Tarefa '{t.nome}' concluída!",
        "dados": {"atividade_id": t.id},
        "artefato": (f"tarefa/{t.id}", "tarefa"),
    }


def h_contar_animais(user, params, ctx):
    from django.db.models import Sum

    from app.models import Animal

    prop = _prop(user, params)
    qs = Animal.objects.filter(propriedade__user=user)
    if prop:
        qs = qs.filter(propriedade=prop)
    total = qs.aggregate(s=Sum("quantidade"))["s"] or 0
    por_esp = list(qs.values("especie").annotate(n=Sum("quantidade")))
    ctx["fontes"].append("interna:animal")
    detalhe = ", ".join(f"{e['especie']}: {e['n']}" for e in por_esp) or "nenhum lote"
    return {
        "ok": True,
        "resposta": f"Rebanho: {total} cabeças ({detalhe}).",
        "dados": {"total": int(total)},
        "artefato": ("pecuaria/resumo", "pecuaria"),
    }


def h_resumo_aquatico(user, params, ctx):
    from django.db.models import Sum

    from app.models import Despesca, LoteAquatico

    prop = _prop(user, params)
    qs = LoteAquatico.objects.filter(propriedade__user=user)
    if prop:
        qs = qs.filter(propriedade=prop)
    total = qs.aggregate(s=Sum("quantidade"))["s"] or 0
    por_esp = list(qs.values("especie").annotate(n=Sum("quantidade")))
    desp = Despesca.objects.filter(lote__propriedade__user=user)
    if prop:
        desp = desp.filter(lote__propriedade=prop)
    kg = desp.aggregate(s=Sum("quantidade_kg"))["s"] or 0
    ctx["fontes"].append("interna:aquatico")
    return {
        "ok": True,
        "resposta": f"Aquático: {total} indivíduos em {qs.count()} lotes, {float(kg):.1f} kg despescados no total.",
        "dados": {
            "total": int(total),
            "lotes": qs.count(),
            "kg": float(kg),
            "por_especie": por_esp,
        },
        "artefato": ("aquatico/resumo", "aquatico"),
    }


def h_resumo_talhoes(user, params, ctx):
    from django.db.models import Sum

    from app.models import Talhao

    prop = _prop(user, params)
    qs = Talhao.objects.filter(propriedade__user=user, ativo=True)
    if prop:
        qs = qs.filter(propriedade=prop)
    area = qs.aggregate(s=Sum("area_hectare"))["s"] or 0
    culturas = sorted(
        {
            t.cultura_atual.nome
            for t in qs.select_related("cultura_atual")
            if t.cultura_atual
        }
    )
    ctx["fontes"].append("interna:talhao")
    return {
        "ok": True,
        "resposta": f"{qs.count()} talhões ativos, {float(area):.1f} ha. Culturas: {', '.join(culturas) or 'nenhuma'}.",
        "dados": {"talhoes": qs.count(), "area": float(area)},
        "artefato": ("talhoes/resumo", "campo"),
    }


def h_ultima_leitura(user, params, ctx):
    from app.models import Device, TelemetryData

    eui = (params.get("device_eui") or "").strip()
    metric = (params.get("metric") or "").strip()
    qs = TelemetryData.objects.filter(device__propriedade__user=user).select_related(
        "device"
    )
    if eui:
        qs = qs.filter(device__device_eui__iexact=eui)
    if metric:
        qs = qs.filter(metric=metric)
    r = qs.order_by("-timestamp").first()
    ctx["fontes"].append("interna:telemetria")
    if not r:
        # Resultado vazio é estado neutro (200 com lista vazia), NÃO erro.
        return {
            "ok": True,
            "resposta": "sem leituras para esse filtro",
            "dados": {},
        }
    dev = r.device.nome if r.device else "—"
    return {
        "ok": True,
        "resposta": f"Última leitura {r.metric} em {dev}: {r.value} {r.unit} ({r.timestamp:%d/%m %H:%M}).",
        "dados": {"metric": r.metric, "value": float(r.value)},
    }


def h_listar_funcionarios(user, params, ctx):
    import unicodedata

    from django.db.models import Q

    from app.models import Funcionario

    def norm(s):
        return "".join(
            c
            for c in unicodedata.normalize("NFD", str(s or "").lower())
            if unicodedata.category(c) != "Mn"
        )

    prop = _prop(user, params)
    qs = Funcionario.objects.filter(propriedade__user=user, ativo=True)
    if prop:
        qs = qs.filter(propriedade=prop)
    setor = norm(
        params.get("setor") or params.get("cargo") or params.get("funcao") or ""
    )
    # extrai "setor x" da frase? o bridge já manda; aqui filtra
    if setor:
        toks = [w for w in setor.split() if len(w) > 3]
        q = Q()
        for tok in toks:
            variantes = {tok, tok.rstrip("s")} if tok.endswith("s") else {tok}
            for v in variantes:
                q |= Q(cargo__icontains=v) | Q(nome__icontains=tok)
        qs = qs.filter(q)
    lista = list(qs.order_by("nome")[:20])
    ctx["fontes"].append("interna:funcionario")
    if not lista:
        return {
            "ok": True,
            "resposta": "Nenhum funcionário encontrado para esse filtro.",
            "dados": {},
        }
    linhas = [f"{f.nome} ({f.get_cargo_display()})" for f in lista]
    return {
        "ok": True,
        "resposta": f"Funcionários ({len(linhas)}): " + "; ".join(linhas),
        "dados": {"total": len(linhas), "funcionarios": linhas},
        "artefato": ("equipe/resumo", "equipe"),
    }


def h_dados_propriedade(user, params, ctx):
    from app.models import Cultura, Safra, Talhao

    prop = _prop(user, params)
    if not prop:
        return {"ok": False, "erro": "nenhuma propriedade encontrada"}
    n_tal = Talhao.objects.filter(propriedade=prop, ativo=True).count()
    n_cul = Cultura.objects.filter(
        id__in=Safra.objects.filter(propriedade=prop).values("cultura_id")
    ).count()
    ctx["fontes"].append("interna:propriedade")
    return {
        "ok": True,
        "resposta": (
            f"{prop.nome} ({prop.cidade}/{prop.uf}): {prop.area_total} ha, "
            f"{n_tal} talhões, {n_cul} culturas com safra."
        ),
        "dados": {"nome": prop.nome, "cidade": prop.cidade, "uf": prop.uf},
        "artefato": (f"propriedade/{prop.id}", "propriedade"),
    }


def h_listar_culturas(user, params, ctx):
    from django.utils import timezone as _tz

    from app.models import Safra

    prop = _prop(user, params)
    qs = Safra.objects.filter(propriedade__user=user).select_related("cultura")
    if prop:
        qs = qs.filter(propriedade=prop)
    try:
        ano = int(params.get("ano", _tz.now().year))
    except (TypeError, ValueError):
        ano = _tz.now().year
    nomes = sorted({s.cultura.nome for s in qs.filter(ano=ano) if s.cultura})
    ctx["fontes"].append("interna:safra+cultura")
    if not nomes:
        return {
            "ok": True,
            "resposta": f"Nenhuma cultura plantada em {ano}.",
            "dados": {},
        }
    return {
        "ok": True,
        "resposta": f"Culturas em {ano}: " + ", ".join(nomes),
        "dados": {"ano": ano, "culturas": nomes},
        "artefato": (f"culturas/{ano}", "culturas"),
    }


def h_ajuda(user, params, ctx):
    return {
        "ok": True,
        "resposta": (
            "Sou a AmplIA 🌱 Posso: cadastrar safra, rebanho, peixe, talhão, funcionário e tarefa (passo a passo); "
            "consultar clima, safras, tarefas, estoque, equipe e sensores; "
            "ligar/desligar o irrigador; e mostrar histórico do talhão. "
            "Ex: 'cadastrar safra', 'vai chover?', 'mostra minhas safras', 'quais tarefas temos?'."
        ),
        "dados": {"intents": sorted(INTENTS.keys())},
    }


def h_historico_talhao(user, params, ctx):
    from app.models import AplicacaoInsumo, Safra, Talhao

    nome = (params.get("talhao") or "").strip()
    qs = Talhao.objects.filter(propriedade__user=user)
    t = qs.filter(nome__icontains=nome).first() if nome else qs.first()
    if not t:
        return {"ok": False, "erro": "nenhum talhão encontrado"}
    safras = Safra.objects.filter(talhao=t).order_by("-ano")[:5]
    aplic = AplicacaoInsumo.objects.filter(talhao=t).order_by("-data")[:5]
    partes = [
        f"{t.nome} ({t.area_hectare} ha"
        + (f", {t.cultura_atual.nome}" if t.cultura_atual else "")
        + ")"
    ]
    partes.append(
        "Safras: "
        + (
            "; ".join(
                f"{s.cultura.nome if s.cultura else '(sem cultura)'} {s.ano} ({s.area_plantada} ha)"
                for s in safras
            )
            or "nenhuma"
        )
    )
    partes.append(
        "Aplicações: "
        + (
            "; ".join(
                f"{a.insumo.nome if a.insumo else '(sem insumo)'} em {a.data}"
                for a in aplic
            )
            or "nenhuma"
        )
    )
    ctx["fontes"].append("interna:talhao+safra+insumo")
    return {
        "ok": True,
        "resposta": "Histórico — " + ". ".join(partes) + ".",
        "dados": {"talhao": t.nome},
        "artefato": (f"talhao/{t.id}", "campo"),
    }


def h_criar_lembrete(user, params, ctx):
    return {
        "ok": True,
        "resposta": (
            "Ainda não sei criar lembretes automáticos — está na lista das próximas funções. "
            "Posso mostrar a previsão agora ou ajudar em outra coisa."
        ),
        "dados": {},
    }


def h_cadastrar_talhao(user, params, ctx):
    from app.models import Talhao

    prop = _prop(user, params)
    if not prop:
        return {
            "ok": False,
            "erro": "Nenhuma propriedade encontrada para este usuário.",
        }

    nome = params.get("nome")
    area_str = params.get("area")

    try:
        # Pega apenas números flutuantes do texto (ex: "tem 45 hectares" -> 45.0)
        import re

        numeros = re.findall(r"[-+]?\d*\.\d+|\d+", str(area_str).replace(",", "."))
        area = float(numeros[0]) if numeros else 0.0
    except (TypeError, ValueError):
        area = 0.0

    if area <= 0:
        return {"ok": False, "erro": "Área inválida."}

    t = Talhao.objects.create(
        propriedade=prop, nome=nome[:100], area_hectare=area, ativo=True
    )

    ctx["fontes"].append("interna:talhao")
    return {
        "ok": True,
        "resposta": f"Talhão '{t.nome}' com {t.area_hectare} ha cadastrado com sucesso!",
        "dados": {"talhao_id": t.id, "nome": t.nome},
        "artefato": (f"talhao/{t.id}", "campo"),
    }


def h_feedback(user, params, ctx):
    from app.models import IAArtefato, IAExecucao

    gostou = params.get("gostou")
    if gostou is None:
        txt = (params.get("texto") or "").lower()
        # negativo PRIMEIRO: "não resolveu" contém "resolveu"
        if any(
            w in txt
            for w in [
                "errado",
                "não gostei",
                "nao gostei",
                "ruim",
                "não resolveu",
                "nao resolveu",
                "não funcionou",
                "nao funcionou",
            ]
        ):
            gostou = False
        elif any(
            w in txt
            for w in [
                "obrigado",
                "valeu",
                "resolveu",
                "perfeito",
                "ótimo",
                "otimo",
                "gostei",
                "isso mesmo",
            ]
        ):
            gostou = True
    if gostou is None:
        return {
            "ok": False,
            "erro": "diga se gostou (gostou=true/false) ou escreva 'obrigado'/'não gostei'",
        }
    ex = None
    if params.get("execucao_id"):
        ex = IAExecucao.objects.filter(id=params["execucao_id"], user=user).first()
    if ex:
        ex.satisfeito = bool(gostou)
        ex.save(update_fields=["satisfeito"])
    ctx["fontes"].append("interna:ml_feedback")
    if gostou:
        pergunta = params.get("pergunta", "")
        resposta = params.get("resposta", ex.resposta if ex else "")
        a, _ = IAArtefato.objects.update_or_create(
            user=user,
            chave=f"aprendizado/{(ex.intent if ex else 'geral')}",
            defaults={
                "tipo": "aprendizado",
                "dados": {
                    "pergunta": pergunta,
                    "resposta": resposta,
                    "intent": ex.intent if ex else "",
                },
                "origem": "ml_feedback",
            },
        )
        return {
            "ok": True,
            "resposta": "Aprendido! Registrei essa resposta como boa para usar de novo.",
            "dados": {"artefato_id": a.id},
            "artefato": (a.chave, "aprendizado"),
        }
    return {
        "ok": True,
        "resposta": "Entendido, marquei como insatisfatório para melhorar. Tente reformular a pergunta.",
        "dados": {},
    }


# ---------------------------------------------------------------- catálogo


#: A capacidade de leitura desta intent e' DECLARADA, nao presumida.
#: sandbox.somente_leitura devolve False para um intent sem flags — nao havendo
#: prova de que so le, presume-se que escreve. E' o default certo, e por isso
#: esta intent leva palco.read tal como clima_agora leva clima.read: montar
#: uma mesa nao age sobre o mundo, so desenha o que ja estava no ecrã.


def h_render_preset(user, params, ctx):
    """A IA pede uma mesa de operacao; o palco monta-se.

    Nao e' uma tool que "desenha": e' a mesma frase que o produtor fez, ja
    empacotada numa lista de widgets que o servidor VALIDA — e a seguir
    ENRIQUECE com numeros do banco.

    A validacao e' o que torna isto seguro para um modelo de 1B: um widget
    inventado e' descartado e a mesa e' montada com o resto, em vez de dar 500
    na pergunta mais importante do produto.

    O enriquecimento e' o que faz isto ser uma MESA e nao um esqueleto. Sem
    ele os cards mostravam titulos e nada mais, que e' o defeito que o
    produtor reportou. Cada numero vem da mesma agregacao que o dashboard usa,
    com o tenancy aplicado: a mesa de um produtor nunca sai do banco dele.

    Os widgets que tem endpoint proprio NAO sao enriquecidos aqui — vao ser
    buscados pelo browser, cada um no seu `/api/top-globais/<id>/`. Fazer os
    dois aqui seria pedir o mesmo numero por dois caminhos e acabar com dois
    valores diferentes na mesma tela.
    """
    from app.ia import palco
    from app.ia.palco_dados import enriquece

    intent = str(params.get("intent") or "").strip() or ctx.get("pergunta", "")
    talhao = params.get("talhao") or ""
    widgets, descartados = palco.validar_estrutura(params.get("widgets"))
    if not widgets:
        return {
            "ok": False,
            "erro": (
                "nenhum widget reconhecido. Use ids do catalogo: "
                + ", ".join(sorted(palco.CATALOGO_IA)[:6])
            ),
            "dados": {
                "palco": palco.SLUG_PALCO,
                "catalogo": sorted(palco.CATALOGO_IA),
            },
        }

    # Os que o servidor sabe preencher recebem numero AGORA. Os outros foram
    # declarados com `fonte: top_globais` e ficam para o browser.
    a_enriquecer = [w for w in widgets if w["tipo"] in palco.WIDGETS_SERVIDOR]
    if a_enriquecer:
        calcados = enriquece(user, a_enriquecer, talhao=talhao)
        por_tipo = {w["tipo"]: (w.get("config") or {}) for w in calcados}
        for w in widgets:
            if w["tipo"] in por_tipo:
                w["config"] = por_tipo[w["tipo"]]

    # A lista de "o que ficou sem número" é lida do `fonte_dado`, e não de
    # "o config está vazio". As duas coisas não são a mesma, e a diferença
    # anulava esta lista por completo:
    #
    #   - `_proveniencia` NUNCA devolve um config vazio. Mesmo sem medição
    #     nenhuma, escreve `fonte_dado: sem_dado`; mesmo com uma falha no
    #     cálculo, escreve o motivo. Logo, para os widgets de SERVIDOR, o
    #     `config` está sempre preenchido e a lista antiga era SEMPRE vazia —
    #     incluindo quando não havia um único número no ecrã.
    #   - Os widgets de `top_globais` são o caso inverso: ninguém os preenche
    #     aqui (o browser busca-os no endpoint deles), e portanto o config
    #     deles chega vazio à lista, que os dava como "sem dado" antes de
    #     alguém lhes pedir o valor.
    #
    # Ou seja: a lista dizia o contrário da verdade nos dois sentidos. E não
    # era só um campo morto — o `dados` volta ao modelo como contexto, e uma
    # lista vazia ensina-lhe que "não falta nada" numa mesa que está toda sem
    # número. A IA contava ao produtor uma tela cheia de vazio.
    sem_dado = [
        w["tipo"]
        for w in widgets
        if (w.get("config") or {}).get("fonte_dado") == palco.FONTE_SEM_DADO
    ]

    # A `resposta` é o ÚNICO texto que o produtor lê neste caminho: pelo
    # caminho governado (`ia-local.js`) o `r.resposta` do sandbox vai directo
    # para a tela, sem passar por nada que o reescreva. Escrever nela os ids
    # internos — "Mesa montada no preset Amplia: kpi-custo, kpi-area" — é
    # precisamente o defeito que esta camada existe para evitar: o produtor
    # lê sintaxe de máquina no lugar de uma resposta, e `kpi-roi` não lhe diz
    # nada sobre a safra dele.
    #
    # O `titulo` já estava à mão e já era legível: `validar_estrutura` garante
    # que vem do catálogo quando o modelo não o deu, e trunca-o a 120
    # caracteres. É o mesmo texto que os cartões mostram — a frase e a tela
    # passam a dizer a mesma coisa em vez de dizerem coisas diferentes.
    #
    # E o que ficou sem número é dito na frase, não só marcado no cartão. Um
    # produtor que só lê a resposta não pode ficar com a impressão de que a
    # mesa está vazia quando o que falta é o lançamento.
    titulos = [w["titulo"] for w in widgets]
    frase = "Mesa montada: " + ", ".join(titulos) + "."
    if sem_dado:
        n = len(sem_dado)
        frase += (
            f" ({n} de {len(widgets)} sem dado lançado ainda.)"
            if n != len(widgets)
            else " (Nenhum destes dados foi lançado ainda.)"
        )

    return {
        "ok": True,
        "resposta": frase,
        # `palco` e' o que o JS usa para se reconhecer no meio de qualquer
        # outra resposta do sandbox. Sem esta marca, o palco teria de adivinhar.
        "dados": {
            "palco": palco.SLUG_PALCO,
            "widgets": widgets,
            "layout": palco.normalizar_layout(params.get("layout")),
            "assinatura": palco.assinatura_do_intent(intent),
            "intent": intent,
            "descartados": descartados,
            # O que ficou sem numero. O produtor precisa de ver a diferenca
            # entre "a mesa esta vazia" e "a mesa esta cheia e os numeros nao
            # foram lancados" — sao situacoes opostas na vida dele.
            "sem_dado": sem_dado,
        },
    }


def h_editar_preset(user, params, ctx):
    """A IA edita uma mesa já salva, em vez de redesenhá-la do zero.

    render_preset SUBSTITUI a mesa inteira: o modelo manda a lista completa e a
    antiga é descartada. Isso é o que torna a edição impossível — não há como
    dizer "só mexe neste". Este handler aplica um PATCH PARCIAL: o modelo
    manda só as operações (add/remove/move/resize), e o servidor aplica sobre
    a mesa que já existe.

    Por que patch parcial e não reescrever tudo: o modelo é 1B. Um diff pequeno
    valida melhor do que a IA reescrever 8 widgets inteiros, e o produtor vê o
    que mudou. A regra é a mesma do validar_estrutura, aplicada ao patch:
    operação inválida é DESCARTADA, as válidas aplicam, e nunca 500.

    A mesa editada é SEMPRE do `user`. Não há campo para o cliente dizer de
    quem é — comparar a pertença é mais barato do que tentar provar a invenção.
    """
    from app.ia import palco
    from app.models import PresetPalco

    slug = str(params.get("slug") or "").strip()[:60]
    if not slug:
        return {"ok": False, "erro": "informe o slug do preset a editar"}

    preset = PresetPalco.objects.filter(user=user, slug=slug).first()
    if preset is None:
        return {"ok": False, "erro": f"preset '{slug}' não encontrado"}

    estrutura = preset.estrutura if isinstance(preset.estrutura, dict) else {}
    widgets_atuais = estrutura.get("widgets") or []
    if not isinstance(widgets_atuais, list):
        widgets_atuais = []

    novos, descartados = palco.aplicar_operacoes(
        widgets_atuais, params.get("operacoes")
    )

    # persiste só se algo mudou de verdade: um patch que só descartou operação
    # inválida não pode reescrever a mesa e fingir que editou
    if novos != widgets_atuais:
        estrutura["widgets"] = novos
        preset.estrutura = estrutura
        preset.save(update_fields=["estrutura"])

    return {
        "ok": True,
        "resposta": (
            f"Mesa '{preset.nome}' atualizada."
            if novos != widgets_atuais
            else "Nenhuma operação válida para aplicar."
        ),
        "dados": {
            "slug": preset.slug,
            "widgets": novos,
            "descartados": descartados,
            "alterou": novos != widgets_atuais,
        },
    }


INTENTS = {
    "render_preset": {
        "descricao": (
            "INSTRUÇÃO IA: use para perguntas ANALÍTICAS que pedem comparação, "
            "histórico, evolução ou resumo de números ('custo do talhão 2 este mês', "
            "'compare as safras', 'como evoluiu a produção'). Monta uma mesa de "
            "operação com gráficos e tabelas no preset Amplia, em vez de responder "
            "com texto. NÃO use para perguntas de SIM/NÃO ou valor único: para "
            "'vai chover' use clima_agora, e para 'qual a temperatura' também. "
            "Widgets: "
            + ", ".join(sorted(palco.CATALOGO_IA))
            + ". Só escolha widgets que respondam à pergunta; 2 a 5 chegam."
        ),
        "exemplos": [
            "custo do talhão 2 neste mês",
            "compare as safras",
            "como evoluiu a produção",
            "histórico do talhão 2",
            "resumo financeiro do ano",
            "mostra a evolução da produtividade",
        ],
        "flags": ["palco.read"],
        "handler": h_render_preset,
    },
    "editar_preset": {
        "descricao": (
            "INSTRUÇÃO IA: use quando o produtor quiser MUDAR uma mesa que já "
            "existe — adicionar, remover, mover ou redimensionar um widget. "
            "NÃO use para montar uma mesa nova do zero: para isso use "
            "render_preset. Aqui você manda só as operações que mudam, e o "
            "servidor aplica sobre a mesa salva. Operações: add, remove, move, "
            "resize. Cada uma com 'tipo' (o id do widget) e, para move/resize, "
            "'geom' com gridX/gridY/gridW/gridH."
        ),
        "exemplos": [
            "tira o gráfico de chuva da minha mesa",
            "aumenta o KPI de custo",
            "move o gráfico de safras para o topo",
            "adiciona o KPI de ROI na minha mesa",
        ],
        "flags": ["palco.edit"],
        "handler": h_editar_preset,
    },
    "clima_agora": {
        "descricao": "INSTRUÇÃO IA: use quando perguntarem 'qual o clima', 'como está o tempo', 'temperatura agora'. Exige propriedade (pede se faltar). Fonte: estação do usuário ou Open-Meteo (padrão).",
        "exemplos": [
            "qual o clima",
            "temperatura agora",
            "tá muito quente na fazenda",
            "tá sol ou nublado",
            "quantos graus tá fazendo",
            "tá abafado",
            "sensação térmica",
            "tá ventando muito",
            "umidade do ar agora",
            "tá frio",
            "céu tá limpo",
            "condições climáticas agora",
            "tempo lá fora",
            "boletim do tempo",
            "tempo na propriedade",
            "tempo virou",
            "como amanheceu",
        ],
        "flags": ["clima.read"],
        "handler": h_clima_agora,
    },
    "vai_chover": {
        "descricao": "INSTRUÇÃO IA: use para 'vai chover', 'vai chover hoje/amanhã', 'previsão de chuva'. Parâmetro horas (1-72, padrão 24). Nunca invente probabilidade: só a da API.",
        "exemplos": [
            "vai chover",
            "vai chover hoje",
            "previsão de chuva",
            "chove hoje",
            "se chove",
            "está chovendo",
            "chuva amanhã",
            "alerta de temporal",
            "risco de granizo",
            "vai cair pé d'água",
            "chuva passa de 20mm",
            "só garoa ou chuva grossa",
            "chuva vem forte",
            "chance de chuva amanhã",
        ],
        "flags": ["clima.read"],
        "handler": h_vai_chover,
    },
    "ligar_irrigador": {
        "descricao": "INSTRUÇÃO IA: use para 'ligue o irrigador/irrigação'. AÇÃO FÍSICA: primeiro responda pedindo confirmação (sem confirm=true o sandbox recusa). Com confirm, cria comando valve_open na fila do device.",
        "exemplos": [
            "ligue o irrigador",
            "ligar irrigação",
            "abrir válvula",
            "pode ligar o pivô",
            "aciona a bomba de água",
            "liga a fita de gotejo",
            "liga a aspersão",
            "liga a fertirrigação",
            "abre a eletroválvula",
            "pode molhar o pasto",
            "liga o setor de irrigação",
            "inicia a molhação",
        ],
        "flags": ["iot.comando"],
        "handler": lambda u, p, c: h_irrigador(u, p, c, ligar=True),
    },
    "desligar_irrigador": {
        "descricao": "INSTRUÇÃO IA: use para 'desligue o irrigador'. Mesma regra de confirmação do ligar (valve_close).",
        "exemplos": [
            "desligue o irrigador",
            "fechar válvula",
            "parar irrigação",
            "para o pivô",
            "desliga a bomba de água",
            "corta a água",
            "desliga a fita de gotejo",
            "fecha o registro",
            "desliga a aspersão",
            "desliga a fertirrigação",
            "fecha a eletroválvula",
            "chega de água por hoje",
            "corta a irrigação",
            "para a molhação",
        ],
        "flags": ["iot.comando"],
        "handler": lambda u, p, c: h_irrigador(u, p, c, ligar=False),
    },
    "associar_tarefa": {
        "descricao": "INSTRUÇÃO IA: use para 'associe uma tarefa a...', 'crie uma tarefa', 'agende ...'. Parâmetros: titulo (obrigatório), plano_id/data/custo (opcionais). Cria AtividadePlanejada no plano.",
        "exemplos": [
            "associe uma tarefa",
            "crie uma tarefa de pulverização",
            "criar tarefa de pulverizar",
            "manda pulverizar",
            "agende colheita",
            "consertar a cerca",
            "comprar adubo",
            "revisar o trator",
            "vacinar o gado",
            "plantar milho",
            "colher soja",
            "aplicar herbicida",
            "pagar o boleto",
            "arrumar a bomba",
            "revisar motor",
            "limpar o barracão",
            "entrega de sementes",
            "manutenção preventiva",
            "abastecer tratores",
            "vistoria no campo",
            "regular plantadeira",
            "avisa o João",
            "roçar o pasto",
            "aplicação de fungicida",
            "atividade no cronograma",
            "recolher embalagens",
        ],
        "flags": ["tarefa.create"],
        "handler": h_associar_tarefa,
    },
    "status_sensores": {
        "descricao": "INSTRUÇÃO IA: use para 'como estão os sensores', 'sensores online', 'resumo iot'. Só leitura do BD interno.",
        "exemplos": [
            "como estão os sensores",
            "resumo dos sensores",
            "sensores online",
            "tudo certo com a telemetria",
            "nós estão comunicando",
            "saúde dos dispositivos",
            "status da instrumentação",
            "estação transmitindo",
            "rede LoRa",
            "sensor fora do ar",
        ],
        "flags": ["iot.read"],
        "handler": h_status_sensores,
    },
    "previsao_estendida": {
        "descricao": "INSTRUÇÃO IA: use para 'previsão da semana', 'como fica o tempo nos próximos dias'. Retorna 3 dias (min/max/chuva).",
        "exemplos": [
            "previsão da semana",
            "tempo nos próximos dias",
            "previsão 3 dias",
            "tendência do clima",
            "frente fria chegando",
            "clima vai estabilizar",
            "previsão para o fim de semana",
            "vai ter geada",
            "previsão 5 dias",
            "boletim da semana",
            "meteorologistas da região",
        ],
        "flags": ["clima.read"],
        "handler": h_previsao_estendida,
    },
    "melhor_pulverizar": {
        "descricao": "INSTRUÇÃO IA: use para 'quando pulverizar', 'melhor horário para pulverizar'. Cruza vento<10km/h e chuva<30% nas 48h.",
        "exemplos": [
            "quando pulverizar",
            "melhor horário para aplicar",
            "pode pulverizar hoje",
            "janela de aplicação hoje",
            "quando aplico fungicida",
            "risco de deriva",
            "vento vai parar que horas",
            "melhor hora pra aplicar",
            "chuva vai lavar o veneno",
            "tempo propício pra pulverização",
        ],
        "flags": ["clima.read"],
        "handler": h_melhor_pulverizar,
    },
    "resumo_safra": {
        "descricao": "INSTRUÇÃO IA: use para 'resumo da safra', 'como está a safra'. Parâmetro ano opcional.",
        "exemplos": [
            "resumo da safra",
            "como está a safra",
            "produção deste ano",
            "minhas safras",
            "safras ativas",
            "mostra minhas safras",
            "quanto colhemos",
            "estimativa de colheita",
            "quanto vamos produzir",
            "expectativa de produtividade",
            "sacas por hectare",
            "desenvolvimento da lavoura",
            "status do plantio",
            "rendimento esperado",
            "parecer da lavoura",
            "fechamento da safra passada",
            "como tá indo a roça",
        ],
        "flags": ["safra.read"],
        "handler": h_resumo_safra,
    },
    "resumo_financeiro": {
        "descricao": "INSTRUÇÃO IA: use para 'resumo financeiro', 'como estão as contas'. Parâmetros mes/ano opcionais.",
        "exemplos": [
            "resumo financeiro",
            "lucro do mês",
            "fluxo de caixa",
            "quanto faturamos",
            "custo de produção",
            "despesas do mês",
            "saldo positivo",
            "DRE da fazenda",
            "margem de lucro",
            "boleto vencendo",
            "caixa da fazenda",
            "custo por hectare",
            "fazenda dando lucro",
            "posição financeira",
            "tão as contas",
            "muita conta pra pagar",
            "quanto a gente faturou",
            "gastou com insumo",
            "sobrou no fim das contas",
            "extrato da roça",
        ],
        "flags": ["fin.read"],
        "handler": h_resumo_financeiro,
    },
    "consultar_estoque": {
        "descricao": "INSTRUÇÃO IA: use para 'tem X no estoque', 'estoque baixo'. Parâmetro item opcional; avisa abaixo do mínimo.",
        "exemplos": [
            "tem ureia no estoque",
            "estoque baixo",
            "quanto de semente",
            "itens do estoque",
            "o que tem no estoque",
            "lista do estoque",
            "o que tem no galpão",
            "tem diesel",
            "inventário do galpão",
            "peça de reposição do trator",
            "grãos no silo",
            "tem calcário",
            "o que tem na prateleira",
            "sacaria vazia",
            "verifica o armazenado",
        ],
        "flags": ["estoque.read"],
        "handler": h_consultar_estoque,
    },
    "listar_tarefas": {
        "descricao": "INSTRUÇÃO IA: use para 'quais tarefas', 'tarefas pendentes'. Lista até 10 por data.",
        "exemplos": [
            "quais tarefas pendentes",
            "o que fazer hoje",
            "liste tarefas",
            "quais tarefas temos",
            "tarefas da fazenda",
            "tarefas de hoje",
            "terminaram a tarefa",
            "status da tarefa",
            "tarefa concluída",
            "quem está responsável",
            "o que tem pra fazer hoje",
            "lista de serviços",
            "ordens de serviço abertas",
            "programação da semana",
            "agenda de hoje",
            "atividades planejadas",
            "cronograma da safra",
            "programado pra amanhã",
            "afazeres da equipe",
            "fila de serviços",
            "tarefa atrasada",
            "painel de tarefas",
            "João tem que fazer",
            "OS de manutenção",
            "feito urgente",
            "peãozada",
        ],
        "flags": ["tarefa.read"],
        "handler": h_listar_tarefas,
    },
    "concluir_tarefa": {
        "descricao": "INSTRUÇÃO IA: use para 'concluí a tarefa X'. Parâmetros id ou titulo.",
        "exemplos": [
            "concluí a pulverização",
            "marcar tarefa como feita",
            "tarefa pronta",
            "cerca tá pronta",
            "terminamos de plantar",
            "dá baixa na OS",
            "colheita acabou",
            "tarefa terminada",
            "manutenção finalizada",
            "vistoria feita",
            "lida do gado terminada",
            "limpeza do silo",
            "plantio dado baixa",
            "herbicida foi aplicado",
            "compramos o adubo",
            "OS de lubrificação",
            "entregamos os grãos",
        ],
        "flags": ["tarefa.write"],
        "handler": h_concluir_tarefa,
    },
    "contar_animais": {
        "descricao": "INSTRUÇÃO IA: use para 'quantas cabeças', 'resumo do rebanho'.",
        "exemplos": [
            "quantas cabeças",
            "quantos bois tenho",
            "resumo do rebanho",
            "animais da fazenda",
            "quais animais temos",
            "conta o gado",
            "população do curral",
            "estoque de gado",
            "lotação do pasto",
            "números da boiada",
            "conta as matrizes",
            "censo animal",
            "tamanho da criação",
        ],
        "flags": ["pecuaria.read"],
        "handler": h_contar_animais,
    },
    "resumo_aquatico": {
        "descricao": "INSTRUÇÃO IA: use para 'como estão os peixes', 'resumo da piscicultura'.",
        "exemplos": [
            "como estão os peixes",
            "resumo da piscicultura",
            "despescas do mês",
            "quantos peixes no viveiro",
            "qualidade da água dos peixes",
            "peso médio dos peixes",
            "quando é a despesca",
            "status dos alevinos",
            "biomassa do tanque",
            "tudo certo nos viveiros",
            "resumo dos tanques",
            "biometria das tilápias",
            "números da aquicultura",
            "crescimento da tilápia",
        ],
        "flags": ["aquatico.read"],
        "handler": h_resumo_aquatico,
    },
    "resumo_talhoes": {
        "descricao": "INSTRUÇÃO IA: use para 'quantos talhões', 'área plantada'.",
        "exemplos": [
            "quantos talhões",
            "área total plantada",
            "resumo dos talhões",
            "área plantada total",
            "maior talhão",
            "talhões ativos",
            "nomes dos talhões",
            "talhões de soja",
            "área média dos talhões",
            "talhão em pousio",
            "lista meus talhões",
            "ocupação do solo",
            "mapeamento das áreas",
            "configuração das áreas",
        ],
        "flags": ["campo.read"],
        "handler": h_resumo_talhoes,
    },
    "ultima_leitura": {
        "descricao": "INSTRUÇÃO IA: use para 'última leitura de X'. Parâmetros device_eui e metric opcionais.",
        "exemplos": [
            "última leitura de temperatura",
            "quanto marca o sensor",
            "último dado do solo",
            "umidade do solo agora",
            "temperatura do silo",
            "quanto choveu no pluviômetro",
            "leitura do pivô",
            "pH do tanque",
            "radiação solar agora",
            "leitura instantânea",
            "nível da caixa d'água",
            "condutividade elétrica",
            "pressão atmosférica",
        ],
        "flags": ["iot.read"],
        "handler": h_ultima_leitura,
    },
    "ajuda": {
        "descricao": "INSTRUÇÃO IA: use para 'o que você sabe fazer', 'ajuda'. Lista capacidades.",
        "exemplos": [
            "o que você sabe fazer",
            "ajuda",
            "lista de opções",
            "como funciona esse chat",
            "o que o sistema faz",
            "suas funcionalidades",
            "dá pra fazer o que",
            "seu limite",
            "tuas habilidades",
            "tem manual",
            "como eu pergunto",
            "posso te pedir",
            "exemplo de pergunta",
        ],
        "flags": [],
        "handler": h_ajuda,
    },
    "feedback": {
        "descricao": "INSTRUÇÃO IA (ML): usuário satisfeito ('obrigado', 'resolveu') ou não ('errado', 'não gostei') → chame com texto ou gostou=true/false + execucao_id. O ML grava o aprendizado no artifactory.",
        "exemplos": ["obrigado", "resolveu", "não gostei", "errado"],
        "flags": ["ml.write"],
        "handler": h_feedback,
    },
    "listar_funcionarios": {
        "descricao": "INSTRUÇÃO IA: use para 'quais funcionários', 'quem trabalha aqui', 'mecânicos', 'funcionários do setor X'. Parâmetro setor/cargo opcional (filtra cargo__icontains, ex: 'mecanico' pega MECANICO_*).",
        "exemplos": [
            "quais funcionários",
            "funcionários da fazenda",
            "liste funcionários",
            "quem trabalha aqui",
            "funcionários do setor",
            "mecânicos",
            "profissionais mecânicos",
            "operadores",
            "usuários cadastrados",
            "quem são os usuários",
            "equipe da fazenda",
            "quem trabalha hoje",
            "quem tá de folga",
            "tratoristas",
            "quantas pessoas trabalham aqui",
            "tem alguém de férias",
            "quem tá escalado",
            "diaristas",
            "gerentes da fazenda",
            "vaqueiros",
            "peões",
            "mão de obra",
            "campeiros",
        ],
        "flags": ["equipe.read"],
        "handler": h_listar_funcionarios,
    },
    "listar_culturas": {
        "descricao": "INSTRUÇÃO IA: use para 'quais culturas', 'o que plantamos', 'culturas da fazenda'. Lista culturas com safra no ano (parâmetro ano opcional).",
        "exemplos": [
            "quais culturas",
            "culturas da fazenda",
            "o que plantamos",
            "plantação atual",
            "quais culturas temos",
            "o que estamos plantando",
            "o que tem no campo",
            "cultivos ativos",
            "tem milho plantado",
            "o que tem plantado",
            "portfólio de plantio",
            "grãos estamos produzindo",
            "tem feijão na safra",
            "o que tá vegetando",
            "verde aí",
            "variedade de soja",
            "na terra",
            "colhe esse ano",
            "foi semeado",
        ],
        "flags": ["campo.read"],
        "handler": h_listar_culturas,
    },
    "dados_propriedade": {
        "descricao": "INSTRUÇÃO IA: use para 'qual minha fazenda', 'dados da propriedade', 'onde estou'.",
        "exemplos": [
            "qual minha fazenda",
            "dados da propriedade",
            "onde estou",
            "minha propriedade",
            "resumo da fazenda",
            "tamanho da fazenda",
            "onde fica minha fazenda",
            "quantos hectares eu tenho",
            "área total",
            "município da fazenda",
            "área produtiva total",
            "reserva legal",
            "panorama da fazenda",
            "quantos talhões tem aqui",
            "perfil da fazenda",
            "cadastrado na fazenda",
            "culturas a gente roda",
            "de quem é",
            "localização exata",
            "cadastro rural",
        ],
        "flags": ["campo.read"],
        "handler": h_dados_propriedade,
    },
    "historico_talhao": {
        "descricao": "INSTRUÇÃO IA: use para 'histórico do talhão', 'o que foi feito no talhão X'. Parâmetro talhao (nome, opcional). Junta dados do talhão + últimas safras + aplicações.",
        "exemplos": [
            "histórico do talhão",
            "o que foi feito no talhão",
            "histórico do sul",
            "mostra o histórico",
            "o que foi plantado ano passado",
            "rotação de cultura",
            "último veneno no talhão",
            "histórico de manejo",
            "o que plantou na safra passada",
            "última calagem",
            "histórico de doenças",
            "cultura antecessora",
            "dossiê do talhão",
            "aplicamos lá recentemente",
            "colheu ali antes",
            "dados antigos da roça",
            "registros dessa gleba",
        ],
        "flags": ["campo.read"],
        "handler": h_historico_talhao,
    },
    "criar_lembrete": {
        "descricao": "INSTRUÇÃO IA: use para 'me lembra', 'lembrete', 'me avisa todo dia'. Hoje só responde com honestidade (automação ainda não existe).",
        "exemplos": [
            "me lembra",
            "criar lembrete",
            "lembrete",
            "todo dia",
            "me avisa",
        ],
        "flags": [],
        "handler": h_criar_lembrete,
    },
    "cadastrar_talhao": {
        "descricao": "INSTRUÇÃO IA: use para 'cadastrar talhão', 'novo talhão', 'criar roça'. Inicia o fluxo conversacional para criar um novo talhão pedindo nome e área.",
        "exemplos": [
            "cadastrar talhão",
            "novo talhão",
            "criar roça",
            "adicionar área de plantio",
        ],
        "flags": ["campo.write"],
        "required_fields": ["nome", "area"],
        "requires_confirmation": True,
        "handler": h_cadastrar_talhao,
    },
}

# Lote 2: intents de leitura por domínio (intents2.py) — mesmos padrões,
# escopo por tenant e higiene de catálogo valendo para todas.
from app.ia.intents2 import INTENTS2  # noqa: E402

INTENTS.update(INTENTS2)

# Lote 3: escritas guiadas + leituras computadas (intents3.py).
from app.ia.intents3 import INTENTS3  # noqa: E402

INTENTS.update(INTENTS3)

# Lote 4: automação porte/meio — 20 RegraAuto (intents4.py).
from app.ia.intents4 import INTENTS4  # noqa: E402

INTENTS.update(INTENTS4)

# BUILD 2: as Tools Divinas — a IA expandindo o sistema por metadados.
# `criar_entidade` / `inserir_registro` / `consultar_registros`.
from app.ia.dinamico_intents import INTENTS_DINAMICO  # noqa: E402

INTENTS.update(INTENTS_DINAMICO)

# BUILD 4: a Ponte IoT — a IA da as portas do mundo fisico.
# `provisionar_endpoint_iot` / `revogar_endpoint_iot` / `consultar_endpoints_iot`.
from app.ia.iot_intents import INTENTS_IOT  # noqa: E402

INTENTS.update(INTENTS_IOT)

# BUILD 4 (segunda metade): o Motor Proativo — as Asas.
# `emitir_alerta_proativo` / `ligar_proatividade` / `avaliar_cenario`.
from app.ia.proativo_intents import INTENTS_PROATIVO  # noqa: E402

INTENTS.update(INTENTS_PROATIVO)

# O Ledger: os serviços de dados construídos na auditoria, ligados à automação.
# `capacidade_pagamento` / `preco_referencia` / `zarc_safra` /
# `classificar_cfop` / `ibs_cbs` / `custo_producao`.
#
# Sem este bloco, os seis serviços existiam e eram INALCANÇÁVEIS pela IA —
# verified by `app/tests_automacao_completude.py`, que falhava com a lista
# completa dos seis. Um serviço que a IA não alcança é código morto, e a
# automação prometida não cobre o que foi construído.
from app.ia.intents_ledger_intents import INTENTS_LEDGER  # noqa: E402

INTENTS.update(INTENTS_LEDGER)
