"""
Management command: gerar_alertas
Gera notificações automáticas baseadas em regras de negócio.
Uso: python manage.py gerar_alertas
Cron sugerido: 0 6 * * * cd /path/to/ampliagro && python manage.py gerar_alertas
"""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from app.models import (
    REGRAS_ALERTA,
    AlertaConfig,
    ApiarioColmeia,
    AtividadePlanejada,
    ContaBancaria,
    Device,
    EstoqueItem,
    EventoSanitario,
    Insumo,
    LancamentoFinanceiro,
    Maquinario,
    MonitoramentoPraga,
    Notificacao,
    OrdemCompra,
    Parcelamento,
    Propriedade,
    Racao,
    Safra,
    Talhao,
)


class Command(BaseCommand):
    help = "Gera alertas automáticos (manutenção, estoque, safra, financeiro)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Limpar alertas não lidos antigos (>7 dias)",
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Mostrar alertas sem criar"
        )

    def handle(self, *args, **options):
        hoje = date.today()
        trinta_dias = hoje + timedelta(days=30)
        total_criados = 0

        users = User.objects.filter(is_active=True)
        if options["clear"]:
            limpeza = Notificacao.objects.filter(
                lida=True, criado_em__lt=timezone.now() - timedelta(days=7)
            ).delete()
            self.stdout.write(
                self.style.SUCCESS(f"Limpos {limpeza[0]} alertas antigos")
            )
            return

        for user in users:
            propriedades = Propriedade.objects.filter(user=user)
            for prop in propriedades:
                alertas = self._verificar_propriedade(user, prop, hoje, trinta_dias)

                for alerta in alertas:
                    if options["dry_run"]:
                        self.stdout.write(
                            f"  [{alerta['nivel'].upper()}] {alerta['titulo']}: {alerta['mensagem']}"
                        )
                        total_criados += 1
                        continue

                    # Evitar duplicatas nas últimas 24h
                    existe = Notificacao.objects.filter(
                        user=user,
                        titulo=alerta["titulo"],
                        criado_em__gte=timezone.now() - timedelta(hours=24),
                    ).exists()

                    if not existe:
                        Notificacao.objects.create(
                            user=user,
                            titulo=alerta["titulo"],
                            mensagem=alerta["mensagem"],
                            nivel=alerta["nivel"],
                            link=alerta.get("link", ""),
                        )
                        total_criados += 1

        acao = "simulados" if options["dry_run"] else "criados"
        self.stdout.write(self.style.SUCCESS(f"{total_criados} alertas {acao}"))

    def _cfg(self, user, regra):
        """Config do usuário p/ a regra (linha ou defaults, sem criar no banco)."""
        try:
            return AlertaConfig.objects.get(user=user, regra=regra)
        except AlertaConfig.DoesNotExist:
            return AlertaConfig(user=user, regra=regra, ativo=True)

    def _on(self, user, regra):
        """True se a regra está ativa p/ o usuário (default: ativa)."""
        return self._cfg(user, regra).ativo

    def _verificar_propriedade(self, user, prop, hoje, trinta_dias):
        alertas = []

        # 1. Manutenção de maquinário
        dias_aviso = self._cfg(user, "manutencao").get_dias() or 15
        for m in Maquinario.objects.filter(propriedade=prop, ativo=True):
            if m.proxima_manutencao:
                dias = (m.proxima_manutencao - hoje).days
                if dias < 0:
                    alertas.append(
                        {
                            "regra": "manutencao",
                            "titulo": f"Manutenção atrasada: {m.nome}",
                            "mensagem": f"A manutenção de {m.nome} ({m.get_tipo_display()}) está {abs(dias)} dias atrasada.",
                            "nivel": "critical",
                            "link": "/maquinarios/",
                        }
                    )
                elif dias <= dias_aviso:
                    alertas.append(
                        {
                            "regra": "manutencao",
                            "titulo": f"Manutenção próxima: {m.nome}",
                            "mensagem": f"Manutenção de {m.nome} agendada para {m.proxima_manutencao.strftime('%d/%m/%Y')} ({dias} dias).",
                            "nivel": "warning",
                            "link": "/maquinarios/",
                        }
                    )

        # 2. Estoque baixo ou vencido
        dias_val = self._cfg(user, "estoque_validade").get_dias() or 30
        lim_val = hoje + timedelta(days=dias_val)
        for item in EstoqueItem.objects.filter(propriedade=prop):
            if item.data_validade and item.data_validade < hoje:
                alertas.append(
                    {
                        "regra": "estoque_validade",
                        "titulo": f"Item vencido: {item.nome}",
                        "mensagem": f"{item.nome} ({item.quantidade} {item.unidade}) venceu em {item.data_validade.strftime('%d/%m/%Y')}.",
                        "nivel": "critical",
                        "link": "/estoque/geral/",
                    }
                )
            elif item.data_validade and item.data_validade <= lim_val:
                dias = (item.data_validade - hoje).days
                alertas.append(
                    {
                        "regra": "estoque_validade",
                        "titulo": f"Item proximo do vencimento: {item.nome}",
                        "mensagem": f"{item.nome} vence em {dias} dias ({item.data_validade.strftime('%d/%m/%Y')}).",
                        "nivel": "warning",
                        "link": "/estoque/geral/",
                    }
                )

            # Estoque zerado
            if item.quantidade <= 0:
                alertas.append(
                    {
                        "regra": "estoque_zero",
                        "titulo": f"Estoque zerado: {item.nome}",
                        "mensagem": f"{item.nome} esta com estoque zerado.",
                        "nivel": "warning",
                        "link": "/estoque/geral/",
                    }
                )

        # 3. Safra - plantio atrasado
        for s in Safra.objects.filter(propriedade=prop, data_plantio__isnull=False):
            if s.data_colheita and s.data_colheita < hoje and not s.producao_total:
                alertas.append(
                    {
                        "regra": "colheita",
                        "titulo": f"Colheita pendente: {s.safra_nome}",
                        "mensagem": f"A safra {s.safra_nome} ({s.cultura.nome if s.cultura else '-'}) deveria ter sido colhida. Producao nao registrada.",
                        "nivel": "warning",
                        "link": "/simulador/colheita/",
                    }
                )

        # 4. Despesas altas do mês
        despesas_mes = sum(
            l.valor
            for l in LancamentoFinanceiro.objects.filter(
                propriedade=prop,
                tipo="DESPESA",
                data__month=hoje.month,
                data__year=hoje.year,
            )
        )
        receitas_mes = sum(
            l.valor
            for l in LancamentoFinanceiro.objects.filter(
                propriedade=prop,
                tipo="RECEITA",
                data__month=hoje.month,
                data__year=hoje.year,
            )
        )
        if despesas_mes > 0 and receitas_mes > 0:
            pct = self._cfg(user, "financeiro_mes").get_limite() or 20
            if despesas_mes > receitas_mes * (1 + pct / 100):
                alertas.append(
                    {
                        "regra": "financeiro_mes",
                        "titulo": "Despesas acima da receita",
                        "mensagem": f"Despesas do mes (R$ {despesas_mes:,.2f}) superam receitas (R$ {receitas_mes:,.2f}) em mais de {pct:g}%.",
                        "nivel": "warning",
                        "link": "/cadastro/financeiro/",
                    }
                )

        # 5. Colmeias inativas
        inativas = ApiarioColmeia.objects.filter(propriedade=prop, ativa=False).count()
        if inativas > 0:
            alertas.append(
                {
                    "regra": "colmeias",
                    "titulo": f"{inativas} colmeia(s) inativa(s)",
                    "mensagem": f"{inativas} colmeia(s) estao marcadas como inativas no apiario.",
                    "nivel": "info",
                    "link": "/apiario/",
                }
            )

        # 6. Insumos abaixo do mínimo
        baixos = [
            i
            for i in Insumo.objects.filter(propriedade=prop).exclude(
                estoque_minimo=None
            )
            if (i.quantidade or 0) < (i.estoque_minimo or 0)
        ]
        if baixos:
            nomes = ", ".join(i.nome for i in baixos[:5])
            alertas.append(
                {
                    "regra": "insumos_min",
                    "titulo": f"{len(baixos)} insumo(s) abaixo do mínimo",
                    "mensagem": f"Repor: {nomes}{'...' if len(baixos) > 5 else ''}.",
                    "nivel": "warning",
                    "link": "/estoque/insumos/",
                }
            )

        # 7. Ração vencida ou vencendo em 30 dias
        # (lim_rac nunca foi definida -> NameError na 1ª ração que
        #  chegasse a este ramo; era F821 do ruff, virava 500 do cron)
        lim_rac = hoje + timedelta(days=30)
        for r in Racao.objects.filter(propriedade=prop).exclude(data_validade=None):
            if r.data_validade < hoje:
                alertas.append(
                    {
                        "regra": "racao",
                        "titulo": f"Ração vencida: {r.nome}",
                        "mensagem": f"{r.nome} venceu em {r.data_validade.strftime('%d/%m/%Y')}.",
                        "nivel": "critical",
                        "link": "/pecuaria/racoes/",
                    }
                )
            elif r.data_validade <= lim_rac:
                alertas.append(
                    {
                        "regra": "racao",
                        "titulo": f"Ração vencendo: {r.nome}",
                        "mensagem": f"{r.nome} vence em {(r.data_validade - hoje).days} dias.",
                        "nivel": "warning",
                        "link": "/pecuaria/racoes/",
                    }
                )

        # 8. Contas a pagar.
        #
        # MEDIDO 2026-10-05 (agente 9). Isto usava
        #     LancamentoFinanceiro.objects.filter(..., data__lt=hoje)
        # e chamava-lhe "vencida". `data` e' quando a despesa ACONTECEU, nao
        # quando e' para pagar: uma compra de janeiro de 2024 nunca paga
        # aparecia como atraso, em cima, todos os meses, com o valor dela no
        # total. E' um alerta `critical` que mente sobre a mesma coisa durante
        # anos — que e' o que faz um produtor desligar as notificacoes.
        #
        # Agora sao DOIS sinais, porque sao DUAS coisas:
        #
        #   VENCIDAS  vem de `ContaAPagar.vencimento`, que e' o campo que
        #             existe para isto.dinheiro que nao saiu quando devia.
        #   SEM DATA  vem das despesas em aberto sem conta associada. Nao
        #             sabemos quando vencem, e a mensagem diz isso em vez de
        #             inventar um atraso.
        from app.models.contas import ContaAPagar

        vencidas = ContaAPagar.objects.filter(
            propriedade=prop, estado="ABERTA", vencimento__lt=hoje
        )
        n_venc = vencidas.count()
        if n_venc:
            total_venc = sum((c.valor or 0) for c in vencidas)
            mais_atraso = max(vencidas, key=lambda c: c.vencimento)
            atraso = (hoje - mais_atraso.vencimento).days
            alertas.append(
                {
                    "regra": "contas_vencidas",
                    "titulo": f"{n_venc} conta(s) vencida(s)",
                    "mensagem": (
                        f"R$ {float(total_venc):,.2f} em contas vencidas não pagas. "
                        f"A mais antiga venceu em {mais_atraso.vencimento:%d/%m/%Y} "
                        f"({atraso} dias)."
                    ),
                    "nivel": "critical",
                    "link": "/cadastro/financeiro/",
                }
            )

        # Despesas em aberto SEM data de vencimento. `conta_origem__isnull=True`
        # e' o que impede a mesma despesa de aparecer aqui e na regra de cima:
        # depois de `liquidar`, a conta tem `lancamento` apontado para ela.
        sem_data = LancamentoFinanceiro.objects.filter(
            propriedade=prop,
            tipo="DESPESA",
            pago=False,
            conta_origem__isnull=True,
        )
        n_sem = sem_data.count()
        if n_sem:
            total_sem = sum((l.valor or 0) for l in sem_data)
            alertas.append(
                {
                    "regra": "contas_sem_vencimento",
                    "titulo": f"{n_sem} despesa(s) sem data de vencimento",
                    "mensagem": (
                        f"R$ {float(total_sem):,.2f} em despesas registadas que "
                        f"ainda não foram pagas e **não têm data de vencimento**. "
                        f"Não sabemos se estão atrasadas — registe a data para o "
                        f"alerta de atraso funcionar."
                    ),
                    "nivel": "warning",
                    "link": "/cadastro/financeiro/",
                }
            )

        # 9. Parcelas vencidas não pagas nem canceladas
        parc = Parcelamento.objects.filter(
            propriedade=prop,
            data_pagamento__isnull=True,
            data_cancelamento__isnull=True,
            data_vencimento__lt=hoje,
        )
        n_parc = parc.count()
        if n_parc:
            total_parc = sum((p.valor_parcela or 0) for p in parc)
            alertas.append(
                {
                    "regra": "parcelas_vencidas",
                    "titulo": f"{n_parc} parcela(s) vencida(s)",
                    "mensagem": f"R$ {float(total_parc):,.2f} em parcelas vencidas.",
                    "nivel": "critical",
                    "link": "/cadastro/financeiro/",
                }
            )

        # 10. MIP acima do nível de controle
        criticas = [
            m
            for m in MonitoramentoPraga.objects.filter(
                talhao__propriedade=prop
            ).order_by("-data")[:30]
            if m.acima_controle
        ]
        if criticas:
            m0 = criticas[0]
            alertas.append(
                {
                    "regra": "mip",
                    "titulo": f"MIP crítico: {m0.praga} no {m0.talhao.nome}",
                    "mensagem": f"{len(criticas)} monitoramento(s) acima do controle. Ação: {(m0.acao_recomendada or 'verificar')[:100]}.",
                    "nivel": "critical",
                    "link": "/mip/",
                }
            )

        # 11. Vacinas atrasadas (próxima dose passou)
        atrasadas = EventoSanitario.objects.filter(
            animal__propriedade=prop,
            proxima_dose__lt=hoje,
        ).count()
        if atrasadas:
            alertas.append(
                {
                    "regra": "vacinas",
                    "titulo": f"{atrasadas} dose(s) de vacina atrasada(s)",
                    "mensagem": f"{atrasadas} dose(s) com data passada. Verifique o calendário sanitário.",
                    "nivel": "warning",
                    "link": "/pecuaria/sanidade/",
                }
            )

        # 12. Devices com bateria baixa
        pct_bat = self._cfg(user, "bateria").get_limite()
        pct_bat = pct_bat if pct_bat is not None else 20
        fracos = Device.objects.filter(
            propriedade=prop, ativo=True, bateria_pct__lt=pct_bat
        ).count()
        if fracos:
            alertas.append(
                {
                    "regra": "bateria",
                    "titulo": f"{fracos} sensor(es) com bateria baixa",
                    "mensagem": f"{fracos} device(s) abaixo de {pct_bat:g}% de bateria.",
                    "nivel": "warning",
                    "link": "/iot/devices/",
                }
            )

        # 13. Tarefas atrasadas não concluídas
        atr = AtividadePlanejada.objects.filter(
            plano__safra__propriedade=prop,
            concluida=False,
            data_prevista__lt=hoje,
        ).count()
        if atr:
            alertas.append(
                {
                    "regra": "tarefas",
                    "titulo": f"{atr} tarefa(s) atrasada(s)",
                    "mensagem": f"{atr} atividade(s) com data passada sem conclusão.",
                    "nivel": "warning",
                    "link": "/tarefas/",
                }
            )

        # 14. Saldo bancário abaixo do ponto
        ponto_saldo = self._cfg(user, "saldo_contas").get_limite()
        ponto_saldo = ponto_saldo if ponto_saldo is not None else 1000
        for c in ContaBancaria.objects.filter(propriedade=prop, ativa=True):
            if (c.saldo_atual or 0) < ponto_saldo:
                alertas.append(
                    {
                        "regra": "saldo_contas",
                        "titulo": f"Saldo baixo: {c.banco}",
                        "mensagem": f"Conta {c.conta} com R$ {float(c.saldo_atual or 0):,.2f} (ponto R$ {float(ponto_saldo):,.2f}).",
                        "nivel": "warning",
                        "link": "/cadastro/financeiro/",
                    }
                )

        # 15. Devices offline (sem push há N dias)
        dias_off = self._cfg(user, "devices_offline").get_dias() or 2
        corte = timezone.now() - timedelta(days=dias_off)
        off = (
            Device.objects.filter(propriedade=prop, ativo=True)
            .filter(
                Q(ultimo_push__lt=corte)
                | Q(ultimo_push__isnull=True, criado_em__lt=corte)
            )
            .count()
        )
        if off:
            alertas.append(
                {
                    "regra": "devices_offline",
                    "titulo": f"{off} sensor(es) offline",
                    "mensagem": f"{off} device(s) sem push há mais de {dias_off} dia(s).",
                    "nivel": "warning",
                    "link": "/iot/devices/",
                }
            )

        # 16. Contas a vencer
        dias_cv = self._cfg(user, "contas_a_vencer").get_dias() or 7
        a_vencer = LancamentoFinanceiro.objects.filter(
            propriedade=prop,
            tipo="DESPESA",
            pago=False,
            data__gte=hoje,
            data__lte=hoje + timedelta(days=dias_cv),
        )
        n_cv = a_vencer.count()
        if n_cv:
            tot_cv = sum((l.valor or 0) for l in a_vencer)
            alertas.append(
                {
                    "regra": "contas_a_vencer",
                    "titulo": f"{n_cv} conta(s) a vencer",
                    "mensagem": f"R$ {float(tot_cv):,.2f} vencendo nos próximos {dias_cv} dias.",
                    "nivel": "warning",
                    "link": "/cadastro/financeiro/",
                }
            )

        # 17. Parcelas a vencer
        dias_pv = self._cfg(user, "parcelas_a_vencer").get_dias() or 7
        p_vencer = Parcelamento.objects.filter(
            propriedade=prop,
            data_pagamento__isnull=True,
            data_cancelamento__isnull=True,
            data_vencimento__gte=hoje,
            data_vencimento__lte=hoje + timedelta(days=dias_pv),
        )
        n_pv = p_vencer.count()
        if n_pv:
            tot_pv = sum((p.valor_parcela or 0) for p in p_vencer)
            alertas.append(
                {
                    "regra": "parcelas_a_vencer",
                    "titulo": f"{n_pv} parcela(s) a vencer",
                    "mensagem": f"R$ {float(tot_pv):,.2f} vencendo nos próximos {dias_pv} dias.",
                    "nivel": "warning",
                    "link": "/cadastro/financeiro/",
                }
            )

        # 18. Ordens de compra paradas em rascunho
        dias_op = self._cfg(user, "ordens_paradas").get_dias() or 30
        paradas = OrdemCompra.objects.filter(
            propriedade=prop,
            status="RASCUNHO",
            data_emissao__lt=hoje - timedelta(days=dias_op),
        ).count()
        if paradas:
            alertas.append(
                {
                    "regra": "ordens_paradas",
                    "titulo": f"{paradas} ordem(ns) parada(s)",
                    "mensagem": f"{paradas} ordem(ns) em RASCUNHO há mais de {dias_op} dias.",
                    "nivel": "info",
                    "link": "/estoque/ordens/",
                }
            )

        # 19. Talhões sem safra no ano
        ano = hoje.year
        com_safra = set(
            Safra.objects.filter(propriedade=prop, ano=ano).values_list(
                "talhao_id", flat=True
            )
        ) | set(
            Talhao.objects.filter(propriedade=prop, safras_m2m__ano=ano).values_list(
                "id", flat=True
            )
        )
        sem_safra = (
            Talhao.objects.filter(propriedade=prop)
            .exclude(id__in=com_safra or [0])
            .count()
        )
        if sem_safra:
            alertas.append(
                {
                    "regra": "talhoes_sem_safra",
                    "titulo": f"{sem_safra} talhão(ões) sem safra em {ano}",
                    "mensagem": f"{sem_safra} talhão(ões) sem safra planejada para {ano}.",
                    "nivel": "info",
                    "link": "/safras/",
                }
            )

        # Respeita o on/off por regra configurado pelo usuário
        return [a for a in alertas if self._on(user, a["regra"])]
