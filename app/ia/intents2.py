"""Lote 2 de intents da IA local — leitura por domínio (só consulta, sem escrita).

Padrão obrigatório de todo handler aqui:
- escopo SEMPRE por `propriedade__user=user` (isolamento por tenant);
- `_prop2()` resolve a propriedade (params ou primeira do usuário);
- resposta curta (1-3 linhas), `dados` serializáveis, `artefato` quando útil;
- NUNCA HTTP externo (só banco local) — teste hermético garantido.
"""

from datetime import date

from app.ia.propriedade import resolver as _prop2

# A docstring do ficheiro falava em `_prop2()`, e `_prop2` continua a ser o
# nome que os 17 handlers daqui usam. O que mudou foi ONDE a função vive:
# era uma cópia byte-a-byte da que estava em `intents.py` e `intents3.py`.
# Três cópias de uma regra de tenant são três regras. Ver
# `app/ia.propriedade`.


def h_listar_maquinas(user, params, ctx):
    from app.models import Maquinario

    prop = _prop2(user, params)
    qs = Maquinario.objects.filter(propriedade__user=user, ativo=True)
    if prop:
        qs = qs.filter(propriedade=prop)
    nomes = [
        f"{m.nome} ({m.get_tipo_display()}, {float(m.horas_uso or 0):.0f} h)"
        for m in qs[:15]
    ]
    ctx["fontes"].append("interna:maquinario")
    if not nomes:
        return {
            "ok": True,
            "resposta": "Nenhuma máquina ativa cadastrada.",
            "dados": {},
        }
    return {
        "ok": True,
        "resposta": f"Máquinas ativas ({len(nomes)}): " + "; ".join(nomes),
        "dados": {"total": qs.count(), "maquinas": nomes},
        "artefato": ("maquinas/lista", "maquinario"),
    }


def h_revisao_maquinas(user, params, ctx):
    from app.models import ManutencaoMaquinario, Maquinario

    hoje = date.today()
    prop = _prop2(user, params)
    mq = Maquinario.objects.filter(propriedade__user=user, ativo=True)
    if prop:
        mq = mq.filter(propriedade=prop)
    vencidas = [
        f"{m.nome} (prevista {m.proxima_manutencao:%d/%m})"
        for m in mq
        if m.proxima_manutencao and m.proxima_manutencao <= hoje
    ][:10]
    ult = ManutencaoMaquinario.objects.filter(maquinario__propriedade__user=user)
    if prop:
        ult = ult.filter(maquinario__propriedade=prop)
    ult = [
        f"{m.maquinario.nome} {m.data:%d/%m} ({m.tipo})"
        for m in ult.order_by("-data")[:5]
    ]
    ctx["fontes"].append("interna:manutencao")
    partes = []
    partes.append(
        "Revisões vencidas: " + ("; ".join(vencidas) if vencidas else "nenhuma 🎉")
    )
    if ult:
        partes.append("Últimas feitas: " + "; ".join(ult))
    return {
        "ok": True,
        "resposta": ". ".join(partes) + ".",
        "dados": {"vencidas": vencidas, "ultimas": ult},
        "artefato": ("maquinas/revisao", "maquinario"),
    }


def h_listar_insumos(user, params, ctx):
    from app.models import Insumo

    prop = _prop2(user, params)
    qs = Insumo.objects.filter(propriedade__user=user)
    if prop:
        qs = qs.filter(propriedade=prop)
    itens = [f"{i.nome} ({float(i.quantidade or 0):g} {i.unidade})" for i in qs[:15]]
    ctx["fontes"].append("interna:insumo")
    if not itens:
        return {"ok": True, "resposta": "Nenhum insumo cadastrado.", "dados": {}}
    return {
        "ok": True,
        "resposta": f"Insumos ({qs.count()}): " + "; ".join(itens),
        "dados": {"total": qs.count(), "insumos": itens},
        "artefato": ("insumos/lista", "insumo"),
    }


def h_estoque_baixo(user, params, ctx):
    from app.models import EstoqueItem, Insumo

    prop = _prop2(user, params)
    qi = Insumo.objects.filter(propriedade__user=user).exclude(estoque_minimo=None)
    if prop:
        qi = qi.filter(propriedade=prop)
    baixos = [
        f"{i.nome} ({float(i.quantidade or 0):g}/{float(i.estoque_minimo or 0):g} {i.unidade})"
        for i in qi
        if (i.quantidade or 0) < (i.estoque_minimo or 0)
    ]
    qe = EstoqueItem.objects.filter(propriedade__user=user)
    if prop:
        qe = qe.filter(propriedade=prop)
    baixos += [
        f"{e.nome} ({float(e.quantidade or 0):g}/{float(e.quantidade_minima or 0):g} {e.unidade})"
        for e in qe
        if (e.quantidade or 0) < (e.quantidade_minima or 0)
    ]
    ctx["fontes"].append("interna:estoque_baixo")
    if not baixos:
        return {
            "ok": True,
            "resposta": "Estoque OK — nada abaixo do mínimo. ✅",
            "dados": {},
        }
    return {
        "ok": True,
        "resposta": f"⚠️ Estoque baixo ({len(baixos)}): " + "; ".join(baixos[:12]),
        "dados": {"baixos": baixos},
        "artefato": ("estoque/baixo", "estoque"),
    }


def h_monitorar_pragas(user, params, ctx):
    from app.models import MonitoramentoPraga

    prop = _prop2(user, params)
    qs = MonitoramentoPraga.objects.filter(talhao__propriedade__user=user).order_by(
        "-data"
    )
    if prop:
        qs = qs.filter(talhao__propriedade=prop)
    itens = []
    for m in qs[:8]:
        alerta = " 🚨 ACIMA DO NÍVEL" if m.acima_controle else ""
        itens.append(
            f"{m.praga} no {m.talhao.nome} {m.data:%d/%m} ({float(m.nivel_infestacao):g}%){alerta}"
        )
    ctx["fontes"].append("interna:mip")
    if not itens:
        return {
            "ok": True,
            "resposta": "Nenhum monitoramento de praga registrado.",
            "dados": {},
        }
    return {
        "ok": True,
        "resposta": "MIP recente: " + "; ".join(itens),
        "dados": {"monitoramentos": itens},
        "artefato": ("mip/recente", "mip"),
    }


def h_calendario_sanitario(user, params, ctx):
    from app.models import EventoSanitario, ProtocoloSanitario

    hoje = date.today()
    qe = EventoSanitario.objects.filter(
        animal__propriedade__user=user, proxima_dose__gte=hoje
    ).order_by("proxima_dose")
    prox = []
    for e in qe[:8]:
        ident = e.animal.brinco or e.animal.nome or f"#{e.animal_id}"
        nome_prot = e.protocolo.nome if e.protocolo else e.tipo
        prox.append(f"{ident} — {nome_prot} em {e.proxima_dose:%d/%m}")
    n_prot = ProtocoloSanitario.objects.filter(propriedade__user=user).count()
    ctx["fontes"].append("interna:sanidade")
    if not prox:
        return {
            "ok": True,
            "resposta": f"Nenhuma dose futura agendada ({n_prot} protocolos cadastrados).",
            "dados": {"protocolos": n_prot},
        }
    return {
        "ok": True,
        "resposta": "Próximas doses: " + "; ".join(prox),
        "dados": {"proximas": prox, "protocolos": n_prot},
        "artefato": ("sanidade/calendario", "sanidade"),
    }


def h_producao_leite(user, params, ctx):
    from app.models import ProducaoAnimal

    qs = ProducaoAnimal.objects.filter(animal__propriedade__user=user).order_by("-data")
    itens = [
        f"{p.data:%d/%m}: {float(p.quantidade_produzida or 0):g} {p.unidade}"
        for p in qs[:8]
    ]
    ctx["fontes"].append("interna:producao_animal")
    if not itens:
        return {
            "ok": True,
            "resposta": "Nenhuma produção animal registrada.",
            "dados": {},
        }
    return {
        "ok": True,
        "resposta": "Produção recente: " + "; ".join(itens),
        "dados": {"producoes": itens},
        "artefato": ("pecuaria/producao", "pecuaria"),
    }


def h_piquetes(user, params, ctx):
    from app.models import Piquete

    prop = _prop2(user, params)
    qs = Piquete.objects.filter(propriedade__user=user)
    if prop:
        qs = qs.filter(propriedade=prop)
    itens = [
        f"{p.nome} ({float(p.area_hectare or 0):g} ha, {p.status})" for p in qs[:12]
    ]
    ctx["fontes"].append("interna:piquete")
    if not itens:
        return {"ok": True, "resposta": "Nenhum piquete cadastrado.", "dados": {}}
    return {
        "ok": True,
        "resposta": f"Piquetes ({qs.count()}): " + "; ".join(itens),
        "dados": {"total": qs.count(), "piquetes": itens},
        "artefato": ("pecuaria/piquetes", "pecuaria"),
    }


def h_apiario_resumo(user, params, ctx):
    from django.db.models import Sum

    from app.models import ApiarioColmeia, ProducaoApiario

    prop = _prop2(user, params)
    qc = ApiarioColmeia.objects.filter(propriedade__user=user, ativa=True)
    if prop:
        qc = qc.filter(propriedade=prop)
    qp = ProducaoApiario.objects.filter(colmeia__propriedade__user=user)
    if prop:
        qp = qp.filter(colmeia__propriedade=prop)
    mel = qp.aggregate(s=Sum("producao_mel_kg"))["s"] or 0
    ctx["fontes"].append("interna:apiario")
    return {
        "ok": True,
        "resposta": f"Apiário: {qc.count()} colmeias ativas, {float(mel):.1f} kg de mel extraídos no total.",
        "dados": {"colmeias": qc.count(), "mel_kg": float(mel)},
        "artefato": ("apiario/resumo", "apiario"),
    }


def h_contas_a_pagar(user, params, ctx):
    from django.db.models import Sum

    from app.models import LancamentoFinanceiro

    prop = _prop2(user, params)
    qs = LancamentoFinanceiro.objects.filter(
        propriedade__user=user, tipo="DESPESA", pago=False
    ).order_by("data")
    if prop:
        qs = qs.filter(propriedade=prop)
    total = qs.aggregate(s=Sum("valor"))["s"] or 0
    itens = [f"{l.data:%d/%m} R$ {float(l.valor):,.2f} ({l.categoria})" for l in qs[:8]]
    ctx["fontes"].append("interna:financeiro")
    if not itens:
        return {
            "ok": True,
            "resposta": "Nenhuma conta a pagar em aberto. ✅",
            "dados": {},
        }
    return {
        "ok": True,
        "resposta": f"A pagar: R$ {float(total):,.2f} em {qs.count()} lançamentos. Próximos: "
        + "; ".join(itens),
        "dados": {"total": float(total), "qtd": qs.count(), "proximos": itens},
        "artefato": ("financeiro/a_pagar", "financeiro"),
    }


def h_saldo_contas(user, params, ctx):
    from django.db.models import Sum

    from app.models import ContaBancaria

    prop = _prop2(user, params)
    qs = ContaBancaria.objects.filter(propriedade__user=user, ativa=True)
    if prop:
        qs = qs.filter(propriedade=prop)
    itens = [
        f"{c.banco} {c.conta}: R$ {float(c.saldo_atual or 0):,.2f}" for c in qs[:10]
    ]
    total = qs.aggregate(s=Sum("saldo_atual"))["s"] or 0
    ctx["fontes"].append("interna:contas")
    if not itens:
        return {"ok": True, "resposta": "Nenhuma conta bancária ativa.", "dados": {}}
    return {
        "ok": True,
        "resposta": f"Saldo total R$ {float(total):,.2f}. " + "; ".join(itens),
        "dados": {"total": float(total), "contas": itens},
        "artefato": ("financeiro/saldos", "financeiro"),
    }


def h_conciliar_banco(user, params, ctx):
    """Responde 'o que veio do extrato que eu nao registrei?'.

    MEDIDO 2026-10-06. `h_saldo_contas` existe e mostra o saldo guardado, mas
    nao diz nada sobre o movimento do banco. Sao perguntas diferentes, e a
    segunda e' a que dói: ha' dinheiro que saiu e o cadastro nao sabe.

    Este intent so' LE. Nao concilia nada - casar um movimento baixa uma
    conta a pago, e isso passa pelo caminho que exige confirmacao.
    """
    from app.models import ContaBancaria
    from app.services.conciliacao_proposta import resumo_para_ia, sugerir

    prop = _prop2(user, params)
    qs = ContaBancaria.objects.filter(propriedade__user=user, ativa=True)
    if prop:
        qs = qs.filter(propriedade=prop)

    contas = list(qs[:10])
    if not contas:
        return {
            "ok": True,
            "resposta": "Nenhuma conta bancaria ativa nesta propriedade.",
            "dados": {},
        }

    por_conta = []
    total_propostas = 0
    total_nao_casadas = 0
    transferencias = 0

    for c in contas:
        r = sugerir(user, c)
        por_conta.append(
            {
                "conta": f"{c.banco} {c.conta}",
                "conta_id": c.pk,
                "propostas": len(r.propostas),
                "nao_casadas": len(r.nao_casadas),
                "por_confianca": r.por_confianca,
                "total_proposto": float(r.total_proposto),
                "total_nao_casado": float(r.total_nao_casado),
                "transferencias": len(r.transferencias_suspeitas),
            }
        )
        total_propostas += len(r.propostas)
        total_nao_casadas += len(r.nao_casadas)
        transferencias += len(r.transferencias_suspeitas)

    ctx["fontes"].append("interna:conciliacao_bancaria")

    if total_propostas == 0 and total_nao_casadas == 0:
        return {
            "ok": True,
            "resposta": (
                "O extrato destas contas esta vazio, ou ja' esta tudo "
                "conciliado. Nada a fazer aqui."
            ),
            "dados": {"por_conta": por_conta},
        }

    texto = resumo_para_ia(sugerir(user, contas[0])) if len(contas) == 1 else None
    if texto is None:
        texto = (
            "Extrato de %d conta(s): %d movimento(s) com lancamento "
            "sugerido, %d sem correspondencia"
            % (len(contas), total_propostas, total_nao_casadas)
        )
        if transferencias:
            texto += (
                ", dos quais %d parecem transferencia entre contas da "
                "propria fazenda - essas nao sao receita nem despesa, e "
                "por isso ficam de fora" % transferencias
            )
        texto += (
            ". Nao fui conciliar nada: cada casamento precisa de "
            "confirmacao, porque baixar uma conta a pago sem perguntar "
            "faz voce perder a visao do que ainda deve."
        )

    return {
        "ok": True,
        "resposta": texto,
        "dados": {
            "por_conta": por_conta,
            "total_propostas": total_propostas,
            "total_nao_casadas": total_nao_casadas,
            "transferencias_suspeitas": transferencias,
        },
        "artefato": ("financeiro/conciliacao_bancaria", "financeiro"),
    }


def h_fretes_abertos(user, params, ctx):
    from app.models import Frete

    qs = Frete.objects.filter(
        romaneio__rota__propriedade__user=user, pago=False
    ).select_related("romaneio__rota")
    itens = [f"{f.romaneio.rota.nome}: R$ {float(f.valor or 0):,.2f}" for f in qs[:8]]
    ctx["fontes"].append("interna:frete")
    if not itens:
        return {"ok": True, "resposta": "Nenhum frete em aberto. ✅", "dados": {}}
    return {
        "ok": True,
        "resposta": f"Fretes em aberto ({qs.count()}): " + "; ".join(itens),
        "dados": {"total": qs.count(), "fretes": itens},
        "artefato": ("logistica/fretes", "logistica"),
    }


def h_ordens_compra(user, params, ctx):
    from app.models import OrdemCompra

    prop = _prop2(user, params)
    qs = OrdemCompra.objects.filter(
        propriedade__user=user, status__in=["RASCUNHO", "APROVADA", "PEDIDA"]
    ).order_by("-data_emissao")
    if prop:
        qs = qs.filter(propriedade=prop)
    itens = [
        f"#{o.id} {o.fornecedor or 's/fornecedor'} R$ {float(o.valor_total or 0):,.2f} ({o.status})"
        for o in qs[:8]
    ]
    ctx["fontes"].append("interna:ordem_compra")
    if not itens:
        return {
            "ok": True,
            "resposta": "Nenhuma ordem de compra em aberto.",
            "dados": {},
        }
    return {
        "ok": True,
        "resposta": f"Ordens em aberto ({qs.count()}): " + "; ".join(itens),
        "dados": {"total": qs.count(), "ordens": itens},
        "artefato": ("estoque/ordens", "estoque"),
    }


def h_analise_solo(user, params, ctx):
    from app.models import AnaliseSolo

    prop = _prop2(user, params)
    qs = AnaliseSolo.objects.filter(talhao__propriedade__user=user).order_by(
        "-data_coleta"
    )
    if prop:
        qs = qs.filter(talhao__propriedade=prop)
    itens = []
    for a in qs[:5]:
        ph = f"pH {float(a.ph):.1f}" if a.ph is not None else "pH n/d"
        v = (
            f"V {float(a.saturacao_bases_v):.0f}%"
            if a.saturacao_bases_v is not None
            else ""
        )
        itens.append(f"{a.talhao.nome} {a.data_coleta:%m/%y}: {ph} {v}".strip())
    ctx["fontes"].append("interna:solo")
    if not itens:
        return {
            "ok": True,
            "resposta": "Nenhuma análise de solo registrada.",
            "dados": {},
        }
    return {
        "ok": True,
        "resposta": "Solo recente: " + "; ".join(itens),
        "dados": {"analises": itens},
        "artefato": ("campo/solo", "campo"),
    }


def h_alertas_telemetria(user, params, ctx):
    from app.models import AlertaTelemetria

    prop = _prop2(user, params)
    qs = AlertaTelemetria.objects.filter(
        propriedade__user=user, resolvido=False
    ).order_by("-timestamp")
    if prop:
        qs = qs.filter(propriedade=prop)
    itens = [
        f"[{a.severidade}] {a.metric}={float(a.valor):g} ({a.timestamp:%d/%m %H:%M})"
        for a in qs[:8]
    ]
    ctx["fontes"].append("interna:alertas")
    if not itens:
        return {
            "ok": True,
            "resposta": "Nenhum alerta de telemetria pendente. ✅",
            "dados": {},
        }
    return {
        "ok": True,
        "resposta": f"⚠️ Alertas pendentes ({qs.count()}): " + "; ".join(itens),
        "dados": {"total": qs.count(), "alertas": itens},
        "artefato": ("iot/alertas", "iot"),
    }


def h_listar_devices(user, params, ctx):
    from app.models import Device

    prop = _prop2(user, params)
    qs = Device.objects.filter(propriedade__user=user, ativo=True)
    if prop:
        qs = qs.filter(propriedade=prop)
    itens = [
        f"{d.nome} ({d.tipo}, bat {float(d.bateria_pct or 0):.0f}%)" for d in qs[:12]
    ]
    ctx["fontes"].append("interna:devices")
    if not itens:
        return {"ok": True, "resposta": "Nenhum device ativo.", "dados": {}}
    return {
        "ok": True,
        "resposta": f"Devices ativos ({qs.count()}): " + "; ".join(itens),
        "dados": {"total": qs.count(), "devices": itens},
        "artefato": ("iot/devices", "iot"),
    }


def h_ultimas_aplicacoes(user, params, ctx):
    from app.models import AplicacaoInsumo

    prop = _prop2(user, params)
    qs = AplicacaoInsumo.objects.filter(talhao__propriedade__user=user).order_by(
        "-data"
    )
    if prop:
        qs = qs.filter(talhao__propriedade=prop)
    itens = [
        f"{a.insumo.nome if a.insumo else '(s/insumo)'} {float(a.dose or 0):g} no {a.talhao.nome} {a.data:%d/%m}"
        for a in qs[:8]
    ]
    ctx["fontes"].append("interna:aplicacoes")
    if not itens:
        return {"ok": True, "resposta": "Nenhuma aplicação registrada.", "dados": {}}
    return {
        "ok": True,
        "resposta": "Últimas aplicações: " + "; ".join(itens),
        "dados": {"aplicacoes": itens},
        "artefato": ("campo/aplicacoes", "campo"),
    }


def h_racao_estoque(user, params, ctx):
    from app.models import Racao

    prop = _prop2(user, params)
    qs = Racao.objects.filter(propriedade__user=user)
    if prop:
        qs = qs.filter(propriedade=prop)
    itens = [
        f"{r.nome} ({float(r.quantidade or 0):g} kg"
        + (f", vence {r.data_validade:%d/%m}" if r.data_validade else "")
        + ")"
        for r in qs[:12]
    ]
    ctx["fontes"].append("interna:racao")
    if not itens:
        return {"ok": True, "resposta": "Nenhuma ração em estoque.", "dados": {}}
    return {
        "ok": True,
        "resposta": f"Ração ({qs.count()}): " + "; ".join(itens),
        "dados": {"total": qs.count(), "racoes": itens},
        "artefato": ("pecuaria/racao", "pecuaria"),
    }


INTENTS2 = {
    "listar_maquinas": {
        "descricao": "INSTRUÇÃO IA: use para 'quais máquinas/tratores tenho', 'lista meu maquinário'. Só leitura.",
        "exemplos": [
            "quais máquinas eu tenho",
            "lista meus tratores",
            "mostra o maquinário da fazenda",
            "quais colheitadeiras tenho",
        ],
        "flags": ["maquinario.read"],
        "handler": h_listar_maquinas,
    },
    "revisao_maquinas": {
        "descricao": "INSTRUÇÃO IA: use para 'revisão vencida', 'manutenção pendente', 'quando revisar o trator'. Só leitura.",
        "exemplos": [
            "alguma revisão vencida",
            "manutenção pendente das máquinas",
            "quando devo revisar o trator",
            "últimas manutenções feitas",
        ],
        "flags": ["maquinario.read"],
        "handler": h_revisao_maquinas,
    },
    "listar_insumos": {
        "descricao": "INSTRUÇÃO IA: use para 'quais insumos tenho', 'estoque de defensivos/adubo'. Só leitura.",
        "exemplos": [
            "quais insumos eu tenho",
            "mostra o estoque de defensivos",
            "quanto de adubo tenho",
            "lista os insumos",
            "diesel no tanque",
            "consumo de combustível",
            "estoque de diesel",
            "abastecimento",
        ],
        "flags": ["insumo.read"],
        "handler": h_listar_insumos,
    },
    "estoque_baixo": {
        "descricao": "INSTRUÇÃO IA: use para 'o que está acabando', 'estoque baixo', 'falta insumo'. Só leitura.",
        "exemplos": [
            "o que está acabando no estoque",
            "algum insumo em falta",
            "estoque baixo",
            "o que preciso comprar",
        ],
        "flags": ["insumo.read"],
        "handler": h_estoque_baixo,
    },
    "monitorar_pragas": {
        "descricao": "INSTRUÇÃO IA: use para 'como estão as pragas', 'monitoramento MIP', 'infestação'. Só leitura.",
        "exemplos": [
            "como estão as pragas",
            "último monitoramento de pragas",
            "alguma infestação acima do nível",
            "relatório do MIP",
        ],
        "flags": ["mip.read"],
        "handler": h_monitorar_pragas,
    },
    "calendario_sanitario": {
        "descricao": "INSTRUÇÃO IA: use para 'próximas vacinas', 'calendário sanitário', 'quando vacinar'. Só leitura.",
        "exemplos": [
            "próximas vacinas do rebanho",
            "calendário sanitário",
            "quando devo vacinar",
            "doses a vencer do gado",
        ],
        "flags": ["sanidade.read"],
        "handler": h_calendario_sanitario,
    },
    "producao_leite": {
        # Pecuária. A descrição e a flag `pecuaria.read` dizem o mesmo:
        # leite e ovos são de rebanho, não de tanque nem de talhão.
        "aplica_a": "animal",
        "descricao": "INSTRUÇÃO IA: use para 'quanto leite produzi', 'produção de ovos', 'produção animal'. Só leitura.",
        "exemplos": [
            "quanto leite produzimos",
            "última produção de leite",
            "produção de ovos",
            "quanto o rebanho produziu",
        ],
        "flags": ["pecuaria.read"],
        "handler": h_producao_leite,
    },
    "piquetes": {
        "descricao": "INSTRUÇÃO IA: use para 'quais piquetes tenho', 'ocupação dos pastos'. Só leitura.",
        "exemplos": [
            "quais piquetes eu tenho",
            "lista os piquetes",
            "pastagens da fazenda",
            "tamanho dos piquetes",
        ],
        "flags": ["pecuaria.read"],
        "handler": h_piquetes,
    },
    "apiario_resumo": {
        "descricao": "INSTRUÇÃO IA: use para 'como estão as abelhas', 'produção de mel', 'colmeias'. Só leitura.",
        "exemplos": [
            "quantas colmeias ativas",
            "produção de mel",
            "como está o apiário",
            "quanto mel extraímos",
        ],
        "flags": ["apiario.read"],
        "handler": h_apiario_resumo,
    },
    "contas_a_pagar": {
        "descricao": "INSTRUÇÃO IA: use para 'o que tenho a pagar', 'contas vencidas', 'boletos'. Só leitura.",
        "exemplos": [
            "o que tenho a pagar",
            "contas a vencer",
            "boletos em aberto",
            "quanto devo pagar este mês",
        ],
        "flags": ["fin.read"],
        "handler": h_contas_a_pagar,
    },
    # --- contas: a tabela que o `contas_intents.py` deixou de ter ---
    #
    # Os HANDLERS vivem em `app/ia/contas_intents.py` (e os testes, em
    # `app/ia/tests_contas.py`). A TABELA e' esta, como todas as outras.
    #
    # `contas` e' o intent que o produtor usa sem dizer a palavra "conta":
    # responde a "quanto entra", "tenho algo atrasado" e "o que eu devo".
    "contas": {
        "descricao": (
            "INSTRUÇÃO IA: use para 'o que tenho a pagar', 'o que devo receber', "
            "'contas vencidas', 'boletos', 'valores que entram'. Le as contas "
            "com vencimento e diz quantas estao vencidas."
        ),
        "exemplos": [
            "o que tenho a pagar",
            "o que devo receber",
            "contas vencidas",
            "boletos em aberto",
            "quanto entra este mês",
            "tenho alguma conta atrasada?",
        ],
        "flags": ["fin.read"],
        # `None` ate ao fim do modulo: ver `_ligar_handlers_de_contas`.
        "handler": None,
    },
    # `registar_conta` e `pagar_conta` ESCREVEM dinheiro, e por isso trazem
    # `requires_confirmation`. Sem isto, a `descricao` do `pagar_conta`
    # prometia "Confirma antes." e o mecanismo nao confirmava — que e'
    # exactamente o modo de falha que este projecto chama pelo nome: a
    # sistema a afirmar que age quando nao tem permissao medida.
    #
    # E `pagar_conta` SEM `id` baixa a conta ABERTA mais antiga
    # (`order_by("vencimento").first()`). Isso e' commodode — "ja paguei o
    # boleto", sem numero, e' o caso comum — e e' perigoso. A correccao NAO e'
    # proibir o fallback: e' o prompt NOMEAR a conta, com valor e vencimento,
    # para o produtor ver antes de o dinheiro mexer.
    "registar_conta": {
        "descricao": (
            "INSTRUÇÃO IA: use para registar uma conta a pagar ou a receber, "
            "com valor e vencimento. NUNCA invente a data de vencimento: "
            "pergunta-a ao produtor se ele nao a deu."
        ),
        "exemplos": [
            "regista uma conta a pagar de 1200 para dia 15",
            "anota que recebo 3000 do gado em 10 de março",
            "cria uma conta a receber",
        ],
        "flags": ["fin.write"],
        "required_fields": ["descricao", "valor", "vencimento"],
        "requires_confirmation": True,
        "prompt_confirmacao": (
            "Vou registar esta conta. Confirma o valor e a data de vencimento "
            "antes de gravar?"
        ),
        "handler": None,
    },
    "pagar_conta": {
        "descricao": (
            "INSTRUÇÃO IA: use quando o produtor disser que pagou uma conta. "
            "Escreve o lancamento contabil que o LCDPR le. Confirma antes."
        ),
        "exemplos": [
            "paguei a conta do fertilizante",
            "ja paguei o boleto",
            "baixa a conta de dia 15",
        ],
        "flags": ["fin.write"],
        "required_fields": ["id"],
        "requires_confirmation": True,
        "prompt_confirmacao": (
            "Vou baixar uma conta a pagar. O prompt diz qual conta, o valor e "
            "o vencimento antes de mexer no dinheiro — confirma?"
        ),
        "handler": None,
    },
    "saldo_contas": {
        "descricao": "INSTRUÇÃO IA: use para 'saldo das contas', 'quanto tenho no banco'. Só leitura.",
        "exemplos": [
            "saldo das contas bancárias",
            "quanto tenho no banco",
            "mostra meus saldos",
            "saldo atual",
        ],
        "flags": ["fin.read"],
        "handler": h_saldo_contas,
    },
    "conciliar_banco": {
        "descricao": "INSTRUÇÃO IA: use para 'o que veio no extrato e não "
        "está registado', 'o que não concilia', 'faltou lançar alguma "
        "coisa do banco', 'dinheiro que saiu e não achei', 'extrato da "
        "conta'. Lê e sugere casamentos, NÃO concilia. Devolve também o "
        "que NÃO casou, que é a resposta que o produtor procura.",
        "exemplos": [
            "o que veio no extrato que eu não registrei",
            "o que não concilia no banco",
            "faltou lançar alguma coisa do extrato",
            "dinheiro que saiu e não achei",
            "extrato da conta",
            "tem coisa no banco que não tá no sistema",
        ],
        "flags": ["fin.read"],
        "handler": h_conciliar_banco,
    },
    "fretes_abertos": {
        "descricao": "INSTRUÇÃO IA: use para 'fretes em aberto', 'romaneios a pagar'. Só leitura.",
        "exemplos": [
            "fretes em aberto",
            "romaneios não pagos",
            "quanto devo de frete",
            "lista os fretes",
        ],
        "flags": ["logistica.read"],
        "handler": h_fretes_abertos,
    },
    "ordens_compra": {
        "descricao": "INSTRUÇÃO IA: use para 'ordens de compra', 'pedidos em aberto'. Só leitura.",
        "exemplos": [
            "ordens de compra em aberto",
            "pedidos feitos ao fornecedor",
            "compras pendentes",
            "o que já pedi para comprar",
            "cota preço de adubo",
            "recebimento de semente",
            "acompanha entrega do calcário",
            "orçamentos de defensivo",
            "menor preço",
            "requisição de materiais",
            "status do pedido",
        ],
        "flags": ["estoque.read"],
        "handler": h_ordens_compra,
    },
    "analise_solo": {
        "descricao": "INSTRUÇÃO IA: use para 'análise de solo', 'pH do talhão', 'fertilidade'. Só leitura.",
        "exemplos": [
            "última análise de solo",
            "qual o pH do talhão",
            "fertilidade do solo",
            "resultado da análise de terra",
        ],
        "flags": ["campo.read"],
        "handler": h_analise_solo,
    },
    "alertas_telemetria": {
        "descricao": "INSTRUÇÃO IA: use para 'alertas dos sensores', 'alarmes disparados'. Só leitura.",
        "exemplos": [
            "algum alerta disparado",
            "alarmes dos sensores",
            "alertas de telemetria",
            "o que os sensores acusaram",
        ],
        "flags": ["iot.read"],
        "handler": h_alertas_telemetria,
    },
    "listar_devices": {
        "descricao": "INSTRUÇÃO IA: use para 'quais sensores tenho', 'devices instalados', 'bateria dos sensores'. Só leitura.",
        "exemplos": [
            "quais sensores eu tenho",
            "devices instalados",
            "bateria dos sensores",
            "lista os equipamentos IoT",
        ],
        "flags": ["iot.read"],
        "handler": h_listar_devices,
    },
    "ultimas_aplicacoes": {
        "descricao": "INSTRUÇÃO IA: use para 'últimas aplicações', 'o que foi pulverizado'. Só leitura.",
        "exemplos": [
            "últimas aplicações de defensivo",
            "o que foi pulverizado",
            "quando apliquei adubo",
            "histórico de pulverização",
        ],
        "flags": ["campo.read"],
        "handler": h_ultimas_aplicacoes,
    },
    "racao_estoque": {
        "descricao": "INSTRUÇÃO IA: use para 'estoque de ração', 'quanta ração tenho'. Só leitura.",
        "exemplos": [
            "quanta ração tenho",
            "estoque de ração",
            "ração disponível",
            "ração vencendo",
        ],
        "flags": ["pecuaria.read"],
        "handler": h_racao_estoque,
    },
}


# ────────────────────────────────────────────────────────────────────────────
# Os HANDLERS de contas vivem em `app/ia/contas_intents.py`; a TABELA e' a de
# cima, como todas as outras.
#
# O import e' AQUI, e nao no topo do ficheiro, por um motivo medido. Com
# `from app.ia.contas_intents import ...` no topo, `contas_intents` ainda nao
# tinha acabado de carregar quando este modulo o importava, e o catalogo
# caia de 86 intents para 36:
#
#     ImportError: cannot import name 'INTENTS_CONTAS'
#     saude() -> integro=False, catalogos=7/9
#
# porque o registo descobre `intents2` e `intents` ANTES de `contas_intents`, e
# a importacao fecha o ciclo a meio. Aqui o import acontece DEPOIS do corpo do
# modulo, quando ja nao ha nada a definir.
def _ligar_handlers_de_contas():
    from app.ia.contas_intents import listar_contas, pagar_conta, registar_conta

    return listar_contas, registar_conta, pagar_conta


_lc, _rc, _pc = _ligar_handlers_de_contas()
INTENTS2["contas"]["handler"] = _lc
INTENTS2["registar_conta"]["handler"] = _rc
INTENTS2["pagar_conta"]["handler"] = _pc
