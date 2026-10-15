import csv
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db.models import Q, Sum
from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from app.api.serializers import (
    CentroCustoSerializer,
    CustoProducaoSerializer,
    LancamentoDetalhadoSerializer,
)
from app.models import (
    CentroCusto,
    CustoProducao,
    LancamentoDetalhado,
    LancamentoFinanceiro,
)


class CentroCustoViewSet(viewsets.ModelViewSet):
    serializer_class = CentroCustoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CentroCusto.objects.filter(
            propriedade__user=self.request.user
        ).select_related("propriedade")


class CustoProducaoViewSet(viewsets.ReadOnlyModelViewSet):
    """Somente leitura — recalculo via POST /recalcular/ ou signal."""

    serializer_class = CustoProducaoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CustoProducao.objects.filter(
            safra__propriedade__user=self.request.user
        ).select_related("safra", "talhao", "centro_custo")

    @action(detail=False, methods=["post"])
    def recalcular(self, request):
        """Recalcula CustoProducao para safra(s) informadas. Body: {safra_ids: [1,2]} ou {propriedade_id: 1}.

        MEDIDO 2026-10-04. Este endpoint so devolveva a lista de custos da
        **safra** (`talhao=None`), porque `recalcular_custos` so criava essa
        granularidade. A resposta parecia completa — N custos, todos da safra —
        e nao dizia nada sobre os talhoes que ficaram de fora.

        Agora devolve `por_talhao` com o mesmo conteudo de
        `_recalcular_por_talhao`, incluindo `talhoes_sem_detalhamento`. Um
        cliente que so le `custos` continua a ver o agregado, igual; um cliente
        que quizer saber o que o sistema **nao** sabe tem onde ler.
        """
        from app.services.custos import recalcular_custos

        safra_ids = request.data.get("safra_ids")
        propriedade_id = request.data.get("propriedade_id")
        if not safra_ids and not propriedade_id:
            return Response(
                {"detail": "Informe safra_ids ou propriedade_id."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        custos, por_safra = recalcular_custos(
            request.user, safra_ids=safra_ids, propriedade_id=propriedade_id
        )
        return Response(
            {
                "custos": CustoProducaoSerializer(custos, many=True).data,
                "por_talhao": por_safra,
                "nota": (
                    "'talhoes_sem_detalhamento' lista os talhoes desta safra "
                    "sem nenhum LancamentoDetalhado apontado. O custo deles "
                    "e' desconhecido — nao e' zero. Repartir o custo da safra "
                    "pela area seria inventar o numero."
                ),
            }
        )

    @action(detail=False, methods=["get"])
    def dre(self, request):
        """DRE simplificado por safra: receitas vs despesas agregadas por categoria_detalhada."""
        safra_id = request.query_params.get("safra")
        qs = self.get_queryset()
        if safra_id:
            qs = qs.filter(safra_id=safra_id)

        # Agregar via LancamentoDetalhado
        dets = LancamentoDetalhado.objects.filter(
            Q(lancamento__propriedade__user=request.user)
            | Q(_propriedade__user=request.user)
        )
        if safra_id:
            dets = dets.filter(safra_id=safra_id)

        dre: dict[str, float] = {}
        for d in dets.select_related("lancamento"):
            key = d.categoria_detalhada
            dre[key] = dre.get(key, 0) + float(d.valor_efetivo)

        # Incluir lançamentos sem detalhamento (usar categoria original)
        sem_det = LancamentoFinanceiro.objects.filter(
            propriedade__user=request.user, detalhamentos__isnull=True
        )
        if safra_id:
            sem_det = sem_det.filter(safra_id=safra_id)
        for lanc in sem_det:
            key = lanc.categoria
            # As receitas e as despesas sao acumuladas como VALOR POSITIVO e
            # separadas depois, por prefixo de categoria (ver as duas linhas
            # seguintes). O sinal nao tem onde actuar.
            #
            # O que estava aqui era `sinal = (1 if tipo == "RECEITA" else 1)`
            # — o mesmo valor nos dois ramos, portanto uma variavel que nunca
            # mudava o resultado. O comentario ao lado dizia o que a linha
            # pretendia, e o codigo nao fazia.
            dre[key] = dre.get(key, 0) + abs(float(lanc.valor))

        # Classificar receitas vs despesas pelos prefixos
        receitas_prefixos = ("VENDA_", "OUTRA_RECEITA")
        receitas_cats = ("VENDA_PROD", "VENDA_ANIMAL", "VENDA_LEITE")
        receitas = sum(
            v
            for k, v in dre.items()
            if k.startswith(receitas_prefixos) or k in receitas_cats
        )
        # Simplificado: despesas = soma de tudo o que nao e receita.
        sem_receita_keys = [
            k
            for k in dre
            if not (k.startswith(receitas_prefixos) or k in receitas_cats)
        ]
        despesas = sum(dre[k] for k in sem_receita_keys)

        return Response(
            {
                "dre": dre,
                "receitas": round(receitas, 2),
                "despesas": round(despesas, 2),
                "saldo": round(receitas - despesas, 2),
            }
        )

    @action(detail=False, methods=["get"])
    def budget_vs_realizado(self, request):
        """
        Compara CustoProducao (budget/previsto) vs soma de LancamentoDetalhado (realizado) por safra.
        GET /api/custos-producao/budget_vs_realizado/?safra=X
        """
        safra_id = request.query_params.get("safra")
        if not safra_id:
            return Response({"detail": "Parâmetro safra é obrigatório."}, status=400)

        custos = self.get_queryset().filter(safra_id=safra_id)
        if not custos.exists():
            return Response(
                {
                    "detail": "Nenhum CustoProducao encontrado para esta safra. Execute recalcular primeiro."
                },
                status=404,
            )

        # Budget = CustoProducao agregado
        budget = custos.aggregate(
            insumos=Sum("insumos"),
            maquina=Sum("maquina"),
            mao_de_obra=Sum("mao_de_obra"),
            embalagem=Sum("embalagem"),
            frete=Sum("frete"),
            impostos=Sum("impostos"),
            outros=Sum("outros"),
            custo_total=Sum("custo_total"),
            receita=Sum("receita"),
        )
        # Realizado = soma de LancamentoDetalhado por categoria
        dets = LancamentoDetalhado.objects.filter(
            Q(lancamento__propriedade__user=request.user)
            | Q(_propriedade__user=request.user),
            safra_id=safra_id,
        )
        # Mapear categoria_detalhada → campo budget
        #
        # Um `COMBUSTIVEL` map para `insumos` e outro para `maquina` estava
        # neste mapa. **Um dict Python descarta a chave repetida em silêncio**
        # e ficava a última — a linha dos `insumos` era código morto que
        # parecia vivo, e o próximo que editasse o mapa não teria como saber.
        # Combustível é custo de operação de máquina, não insumo: fica em
        # `maquina`, e há teste a impedir que volte a duplicar.
        cat_to_campo = {
            "COMPRA_SEMENTE": "insumos",
            "COMPRA_FERTILIZANTE": "insumos",
            "COMPRA_DEFENSIVO": "insumos",
            "COMPRA_CORRETIVO": "insumos",
            "COMPRA_RACAO": "insumos",
            "COMPRA_OUTRO_INSUMO": "insumos",
            # A *compra* de combustível é insumo comprado; o consumo é
            # operação de máquina. São duas coisas e por isso duas linhas —
            # uma vez cada, e não a mesma chave duas vezes.
            "COMPRA_COMBUSTIVEL": "insumos",
            "COMBUSTIVEL": "maquina",
            "MANUTENCAO": "maquina",
            "PECA": "maquina",
            "DEPRECIACAO": "maquina",
            "FOLHA_PAGAMENTO": "mao_de_obra",
            "DIARISTA": "mao_de_obra",
            "TERCEIRO": "mao_de_obra",
            "IMPOSTO": "impostos",
            "ENERGIA": "outros",
            "SEGURO": "outros",
            "FINANCEIRO": "outros",
            "OUTRA_DESPESA": "outros",
        }
        realizado: dict[str, float] = {
            k: 0
            for k in [
                "insumos",
                "maquina",
                "mao_de_obra",
                "embalagem",
                "frete",
                "impostos",
                "outros",
                "receita",
            ]
        }
        for det in dets:
            if (
                det.categoria_detalhada.startswith("VENDA_")
                or det.categoria_detalhada == "OUTRA_RECEITA"
            ):
                realizado["receita"] += float(det.valor_efetivo)
            else:
                campo = cat_to_campo.get(det.categoria_detalhada, "outros")
                realizado[campo] += float(det.valor_efetivo)

        budget_clean = {k: float(v or 0) for k, v in budget.items()}
        comparativo = {}
        for campo in [
            "insumos",
            "maquina",
            "mao_de_obra",
            "embalagem",
            "frete",
            "impostos",
            "outros",
            "custo_total",
            "receita",
        ]:
            b = budget_clean.get(campo, 0)
            r = (
                realizado.get(campo, 0)
                if campo != "custo_total"
                else sum(
                    realizado.get(k, 0)
                    for k in [
                        "insumos",
                        "maquina",
                        "mao_de_obra",
                        "embalagem",
                        "frete",
                        "impostos",
                        "outros",
                    ]
                )
            )
            if campo == "custo_total":
                b = budget_clean.get("custo_total", 0)

            # Budget zero com realizado > 0 **não** é "gastaste 100% do
            # previsto". É "não há previsto para comparar", e dizer 100%
            # afirma que o custo foi exactamente o planeado — que é
            # precisamente a leitura que um produtor usa para decidir se
            # estoura o custo da safra.
            #
            # Zero sobre zero é uma medição válida: a soma de um conjunto
            # vazio é zero, e 0% está certo. A confusão `0`/`None` aqui é
            # a mesma do DRE e a mesma regra: ausente ≠ medido.
            if b:
                percentual = round(r / b * 100, 1)
                percentual_motivo = None
            elif r:
                percentual = None
                percentual_motivo = (
                    "Sem custo previsto para esta safra, não há Percentage a "
                    "comparar. O realizado está medido e não tem contra o qual "
                    "ser medido."
                )
            else:
                percentual = 0.0
                percentual_motivo = None

            comparativo[campo] = {
                "budget": round(b, 2),
                "realizado": round(r, 2),
                "diferenca": round(r - b, 2),
                "percentual": percentual,
                "percentual_motivo": percentual_motivo,
            }

        return Response(
            {
                "safra": int(safra_id),
                "budget": budget_clean,
                "realizado": realizado,
                "comparativo": comparativo,
            }
        )


class LancamentoDetalhadoViewSet(viewsets.ModelViewSet):
    serializer_class = LancamentoDetalhadoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # PERF: _propriedade entra no select_related porque
        # LancamentoDetalhadoSerializer.get_propriedade_nome é SerializerMethodField
        # que acessa obj.propriedade -> 1 query por linha (58 numa página de 50).
        return LancamentoDetalhado.objects.filter(
            Q(lancamento__propriedade__user=self.request.user)
            | Q(_propriedade__user=self.request.user)
        ).select_related(
            "lancamento",
            "centro_custo",
            "safra",
            "talhao",
            "_propriedade",
        )

    @action(detail=False, methods=["get"])
    def export_lcdpr(self, request):
        """Baixa o TXT fiscal gerado pelo exportador compartilhado."""
        from app.services.lcdpr_http import responder_lcdpr
        return responder_lcdpr(request)

    @action(detail=False, methods=["get"])
    def diagnostico_lcdpr(self, request):
        """Pendências e totais do livro, sem gerar nem transmitir arquivo."""
        from app.services.lcdpr_http import responder_lcdpr
        return responder_lcdpr(request, diagnostico=True)

    @action(detail=False, methods=["post"])
    def conciliacao_upload(self, request):
        """
        Conciliação bancária — upload OFX ou CSV.
        POST /api/lancamentos-detalhados/conciliacao_upload/ (multipart file=arquivo)
        Suporta: OFX (SGML) e CSV (data,descricao,valor).
        Retorna lista de transações do extrato com sugestão de match por valor+data.
        """
        arquivo = request.FILES.get("arquivo")
        if not arquivo:
            return Response(
                {"detail": "Arquivo não enviado (campo arquivo)."}, status=400
            )

        nome = arquivo.name.lower()
        try:
            conteudo = arquivo.read().decode("utf-8", errors="replace")
        except Exception:
            return Response({"detail": "Falha ao ler arquivo."}, status=400)

        # MEDIDO 2026-10-04. A parsing vivia inteira dentro desta action — e
        # dentro da `importar_ofx` de `financeiro_banco.py`, que a repetia e
        # devolvia 200 sem gravar. Agora os dois chamam
        # `app/services/extrato.py`: um parser, uma regra para ler
        # "1.234,56" (que e' 1234.56 e nao 1.23456), uma dedupe por FITID.
        # Este endpoint mantem o contrato — devolve as transações com
        # sugestões de match, e o utilizador decide o que casar. Gravar e' o
        # `importar_ofx`.
        from app.services.extrato import ExtratoNaoReconhecido, ler_extrato

        try:
            brutas = ler_extrato(arquivo.read(), nome)
        except ExtratoNaoReconhecido as exc:
            return Response({"detail": str(exc)}, status=400)

        transacoes = [
            {
                "data": t["data"].isoformat() if t["data"] else "",
                "descricao": t["descricao"],
                "valor": float(t["valor"]),
                "tipo": t["tipo"],
                "fitid": t["fitid"],
            }
            for t in brutas
        ]

        # CSV sem coluna de data, ou data ilegível: diz-se. Uma transação sem
        # data não pode ser conciliada contra nada.
        sem_data = sum(1 for t in transacoes if not t["data"])

        # Sugerir matches com LancamentoFinanceiro existentes (mesmo valor absoluto ±1%, mesma data ±3 dias)
        lancamentos = LancamentoFinanceiro.objects.filter(
            propriedade__user=request.user
        ).select_related("safra")
        lanc_list = [
            {
                "id": l.id,
                "data": l.data,
                "valor": float(l.valor),
                "descricao": l.descricao or l.categoria,
                "tipo": l.tipo,
            }
            for l in lancamentos
        ]

        for t in transacoes:
            t["sugestoes"] = []
            try:
                t_val = abs(float(t["valor"]))
                t_date = date.fromisoformat(t["data"]) if t["data"] else None
            except (TypeError, ValueError):
                # MEDIDO 2026-10-05: era `except Exception`. Estreito
                # porque esta e' a UNICA coisa que pode falhar aqui —
                # `float()` e `date.fromisoformat()` levantam `TypeError`
                # ou `ValueError`, e nada mais.
                #
                # A DIFFERENCA NAO E' TEORICA. Com `Exception`, um
                # `OperationalError` da base (uma coluna em falta a meio
                # de uma migracao) era lido como "esta linha do extrato
                # nao tinha data" — e a transacao desaparecia da
                # reconciliacao sem ninguem saber. Com o `except`
                # estreito, o erro da base sobe, e o importador ve que
                # algo correu mal.
                #
                # `continue` aqui e' correcto: uma linha que nao se deixa
                # converter e' uma linha a ignorar, e o importador conta-as.
                continue
            for lanc in lanc_list:
                if abs(abs(lanc["valor"]) - t_val) / max(abs(lanc["valor"]), 1) > 0.01:
                    continue
                if t_date and lanc["data"]:
                    if abs((t_date - lanc["data"]).days) > 3:
                        continue
                t["sugestoes"].append(lanc)
                if len(t["sugestoes"]) >= 3:
                    break

        return Response(
            {
                "transacoes": transacoes,
                "total": len(transacoes),
                "formato": "ofx" if nome.endswith(".ofx") else "csv",
                # Ditto o que nao foi lido. Um extrato com 12 transacoes e 3
                # sem data devolvia 12 e nao dizia nada: o total estava certo
                # e a informação estava errada.
                "sem_data": sem_data,
                "nota": (
                    "Nada foi gravado: este endpoint mostra o que casaria. "
                    "Para gravar, use /api/contas-bancarias/<id>/importar_ofx/."
                ),
            }
        )
