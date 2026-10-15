from datetime import timedelta

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from app.api.serializers import (
    ConciliacaoBancariaSerializer,
    ContaBancariaSerializer,
    MovimentacaoBancariaSerializer,
    NotificacaoTemplateSerializer,
    ParcelamentoSerializer,
    PushSubscriptionSerializer,
)
from app.hierarquia import PodeVerFinanceiro, propriedades_financeiras
from app.models import (
    ConciliacaoBancaria,
    ContaBancaria,
    LancamentoFinanceiro,
    MovimentacaoBancaria,
    Notificacao,
    NotificacaoTemplate,
    Parcelamento,
    Propriedade,
    PushSubscription,
)
from app.services.extrato import TAMANHO_MAXIMO
from app.services.notificacoes import (
    CANAIS_DE_DISPOSITIVO,
    disparar_canais,
)


class ContaBancariaViewSet(viewsets.ModelViewSet):
    serializer_class = ContaBancariaSerializer
    permission_classes = [IsAuthenticated, PodeVerFinanceiro]

    def get_queryset(self):
        return ContaBancaria.objects.filter(
            propriedade__in=propriedades_financeiras(self.request.user)
        ).annotate(movimentacoes_count=Sum("movimentacoes__valor"))

    def perform_create(self, serializer):
        serializer.save()

    @action(detail=True, methods=["get"])
    def extrato(self, request, pk=None):
        conta = self.get_object()
        data_inicio = request.query_params.get("data_inicio")
        data_fim = request.query_params.get("data_fim")

        qs = conta.movimentacoes.all()
        if data_inicio:
            qs = qs.filter(data__gte=data_inicio)
        if data_fim:
            qs = qs.filter(data__lte=data_fim)

        qs = qs.order_by("data")
        from app.api.serializers import MovimentacaoBancariaSerializer

        serializer = MovimentacaoBancariaSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def importar_ofx(self, request, pk=None):
        """Importa movimentações de um extracto OFX ou CSV para a conta.

        MEDIDO 2026-10-04. Este endpoint era a pior mentira do repositório:
        validava a extensão, lia o ficheiro, importava `ElementTree` para
        uma linha a seguir nunca usar, e devolvia

            {"ok": True, "importadas": 0, "mensagem": "Parser OFX a implementar"}

        **HTTP 200 com `ok: true` e zero linhas gravadas.** O cliente lia
        "ok", fechava o ecrã, e acreditava que o extracto do banco estava
        carregado. Não estava. Um ERP que escreve "ok" sem escrever nada é
        pior do que um ERP que dá 500: o 500 é um bug que alguém reporta, o
        "ok" é um bug que aparece no saldo e na conciliação, meses depois.

        Agora grava. O parser vive em `app/services/extrato.py`, partilhado
        com `custos.py:397 conciliacao_upload`, e a deduplicação usa o
        `FITID` do banco — reenviar o mesmo extracto é a norma, não a
        exceção, e antes rebentava em `IntegrityError` a meio.
        """
        conta = self.get_object()
        arquivo = request.FILES.get("arquivo")
        if not arquivo:
            return Response(
                {"erro": "Arquivo OFX não enviado", "campo": "arquivo"}, status=400
            )
        tamanho = getattr(arquivo, "size", 0) or 0
        if tamanho > TAMANHO_MAXIMO:
            return Response(
                {
                    "erro": f"Arquivo maior que {TAMANHO_MAXIMO // (1024 * 1024)} MB",
                    "bytes": tamanho,
                },
                status=400,
            )

        from app.services.extrato import (
            ExtratoNaoReconhecido,
            gravar_movimentacoes,
            ler_extrato,
        )

        try:
            transacoes = ler_extrato(arquivo.read(), getattr(arquivo, "name", ""))
            resultado = gravar_movimentacoes(conta, transacoes)
        except ExtratoNaoReconhecido as exc:
            # 400 com o motivo: um formato que nao sabemos ler e' erro de quem
            # enviou, não 500 nosso. E 501 seria tentador e errado — 501 diz
            # "isto nao existe"; o parser existe e funciona.
            return Response({"erro": str(exc)}, status=400)

        # Um reenvio idêntico já conciliado também é sucesso, sem nova escrita.
        if not any(
            resultado[chave] for chave in ("criadas", "actualizadas", "preservadas")
        ):
            return Response(
                {
                    "ok": False,
                    "erro": (
                        "Nenhuma transação foi gravada. O ficheiro foi lido, "
                        "mas não tinha transações com data válida."
                    ),
                    **resultado,
                },
                status=422,
            )

        return Response(
            {
                "ok": True,
                **resultado,
                "mensagem": (
                    f"{resultado['criadas']} movimentação(ões) gravada(s)"
                    + (
                        f", {resultado['actualizadas']} já existente(s) actualizada(s)."
                        if resultado["actualizadas"]
                        else "."
                    )
                    + (
                        f" {resultado['preservadas']} conciliada(s) preservada(s)."
                        if resultado["preservadas"]
                        else ""
                    )
                    + (
                        " Há movimentos sem identificador bancário: confira transações "
                        "iguais em extratos de períodos sobrepostos."
                        if resultado["sem_identificador"]
                        else ""
                    )
                ),
            },
            status=201,
        )


class MovimentacaoBancariaViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, PodeVerFinanceiro]

    def get_queryset(self):
        from app.models import MovimentacaoBancaria

        return MovimentacaoBancaria.objects.filter(
            conta__propriedade__in=propriedades_financeiras(self.request.user)
        ).select_related("conta")

    def get_serializer_class(self):
        from app.api.serializers import MovimentacaoBancariaSerializer

        return MovimentacaoBancariaSerializer


class ParcelamentoViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, PodeVerFinanceiro]

    def get_queryset(self):
        from app.models import Parcelamento

        return Parcelamento.objects.filter(
            propriedade__in=propriedades_financeiras(self.request.user)
        ).select_related("lancamento", "propriedade")

    def get_serializer_class(self):
        from app.api.serializers import ParcelamentoSerializer

        return ParcelamentoSerializer

    def perform_create(self, serializer):
        serializer.save()

    @action(detail=True, methods=["post"])
    def marcar_pago(self, request, pk=None):
        parcelamento = self.get_object()
        if parcelamento.status != "ABERTA":
            return Response({"erro": "Parcelamento não está aberto"}, status=400)
        parcelamento.status = "PAGA"
        parcelamento.data_pagamento = timezone.now().date()
        parcelamento.save()
        return Response({"ok": True, "data_pagamento": parcelamento.data_pagamento})

    @action(detail=True, methods=["post"])
    def cancelar(self, request, pk=None):
        parcelamento = self.get_object()
        if parcelamento.status not in ["ABERTA", "VENCIDA"]:
            return Response(
                {"erro": "Não é possível cancelar parcelamento neste status"},
                status=400,
            )
        parcelamento.status = "CANCELADA"
        parcelamento.data_cancelamento = timezone.now().date()
        parcelamento.save()
        return Response({"ok": True})


def _entregues_no_dispositivo(resultados: list[dict]) -> int:
    """Quantas subscricoes receberam o aviso **no dispositivo**.

    So contam os canais de `CANAIS_DE_DISPOSITIVO`. Um registo no painel e'
    uma entrega ao ecra, nao ao telefone — e as duas coisas''')e' o que a
    palavra "enviado" esconde. Este campo existia com este sentido
    (`app/tests_notificacoes.py::test_a_resposta_diz_que_web_push_nao_esta_
    configurado`) e e' o que se preserva ao introduzir o despacho multicanal.
    """
    total = 0
    for r in resultados:
        por_canal = r.get("por_canal") or {}
        if any(
            por_canal.get(canal, {}).get("entregue") for canal in CANAIS_DE_DISPOSITIVO
        ):
            total += 1
    return total


class ConciliacaoBancariaViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, PodeVerFinanceiro]

    def get_queryset(self):
        from app.models import ConciliacaoBancaria

        return ConciliacaoBancaria.objects.filter(
            conta__propriedade__in=propriedades_financeiras(self.request.user)
        ).select_related("conta", "criado_por")

    def get_serializer_class(self):
        from app.api.serializers import ConciliacaoBancariaSerializer

        return ConciliacaoBancariaSerializer

    def perform_create(self, serializer):
        serializer.save(criado_por=self.request.user)

    @action(detail=True, methods=["post"])
    def fechar(self, request, pk=None):
        conciliacao = self.get_object()
        if conciliacao.status != "ABERTA":
            return Response({"erro": "Conciliacao não está aberta"}, status=400)

        saldo_sistema_fim = request.data.get("saldo_sistema_fim")
        saldo_banco_fim = request.data.get("saldo_banco_fim")

        if saldo_sistema_fim is None or saldo_banco_fim is None:
            return Response(
                {"erro": "Saldos final do sistema e do banco obrigatórios"}, status=400
            )

        conciliacao.saldo_sistema_fim = saldo_sistema_fim
        conciliacao.saldo_banco_fim = saldo_banco_fim
        conciliacao.diferenca = float(saldo_sistema_fim) - float(saldo_banco_fim)

        if conciliacao.diferenca != 0:
            conciliacao.status = "COM_DIFERENCA"
        else:
            conciliacao.status = "FECHADA"

        conciliacao.fechada_em = timezone.now()
        conciliacao.save()

        from app.api.serializers import ConciliacaoBancariaSerializer

        serializer = ConciliacaoBancariaSerializer(conciliacao)
        return Response(serializer.data)


class PushSubscriptionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from app.models import PushSubscription

        return PushSubscription.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        from app.api.serializers import PushSubscriptionSerializer

        return PushSubscriptionSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["post"])
    def desativar(self, request, pk=None):
        sub = self.get_object()
        sub.ativa = False
        sub.save()
        return Response({"ok": True})


class NotificacaoTemplateViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from app.models import NotificacaoTemplate

        return NotificacaoTemplate.objects.filter(ativa=True)

    def get_serializer_class(self):
        from app.api.serializers import NotificacaoTemplateSerializer

        return NotificacaoTemplateSerializer

    @action(detail=True, methods=["post"])
    def testar(self, request, pk=None):
        """Envia a notificação de teste aos superusers activos.

        `send_push_notification` nunca levanta (`app/services/notificacoes.py`),
        por isso esta acção devolve 200 com o relatório do que aconteceu em vez
        de 500. Antes, o `import` da linha seguinte era de um módulo que não
        existia, e *qualquer* POST aqui dava 500 — que é a pior resposta
        possível a uma acção de diagnóstico: o servidor não distingue "a
        notificação falhou" de "a aplicação está partida".
        """
        template = self.get_object()
        from app.models import PushSubscription
        from app.services.notificacoes import disparar_canais

        # Substitui variáveis
        valores_teste = {}
        for var in template.variaveis:
            valores_teste[var] = f"TESTE_{var}"

        mensagem = template.mensagem
        for var, val in valores_teste.items():
            mensagem = mensagem.replace(f"{{{var}}}", val)

        inscricoes = PushSubscription.objects.filter(
            ativa=True, user__is_superuser=True
        )
        # `template.canais` e' o que decide. Antes esta chamada era sempre
        # `send_push_notification`, e a lista do template era lida por
        # ninguem — o campo mais decorativo do modelo.
        #
        # MEDIDO 2026-10-05: `disparar_canais` e' deliberadamente estrito —
        # sem lista de canais nao adivinha nenhum. Mas `testar` e' uma accao
        # de **diagnostico**: a pergunta que responde e' "este template
        # desenha-se?", e sem canais nao desenhava nada, o que a tornava
        # inutil. Por isso esta accao — e so esta — cai para o unico canal que
        # o sistema sabe fazer, e **diz que caiu** em `nota`.
        canais = list(template.canais or []) or ["inapp"]
        resultados = [
            disparar_canais(
                canais,
                sub.user,
                template.titulo,
                mensagem,
                nivel=template.nivel,
            )
            for sub in inscricoes
        ]

        registadas = [r for r in resultados if r.get("ok")]
        # `entregue` é False sempre que o canal não entregou — e
        # não é. Dizer "enviados: N" seria inventar uma entrega; o que se
        # diz é quantas ficaram registadas e **por que** as outras não.
        #
        # MEDIDO 2026-10-05 (agente 7): isto era um `send_push_notification`
        # por subscrição, e **ignorava `template.canais`**. Um template com
        # `canais: ["email"]` nunca mandava email — registava no painel e
        # respondia `ok: true`. Agora quem chama é
        # `disparar_canais`, que itera a lista e devolve o resultado por canal.
        #
        # O `por_canal` abaixo é a mesma informacao para quem chama
        # `testar`: um template com `["push", "email", "whatsapp"]` diz
        # claramente que 1 de 3 entregou, e porquê os outros dois não.
        por_canal: dict = {}
        for r in resultados:
            for canal, detalhe in (r.get("por_canal") or {}).items():
                por_canal.setdefault(canal, []).append(detalhe)

        return Response(
            {
                "ok": True,
                "registadas": len(registadas),
                # `entregues` conta entregas **ao dispositivo** — que e' o
                # sentido que este campo sempre teve, e que
                # `app/tests_notificacoes.py` trava. Um registo no painel e'
                # uma entrega ao ecra, nao ao telefone: contar os dois como
                # a mesma coisaVoltaria a dizer "notificacao enviada" sem
                # nada ter saido do servidor, que e' exactamente o que este
                # endpoint nao deve fazer.
                "entregues": _entregues_no_dispositivo(resultados),
                "web_push_configurado": False,
                "canais_configurados": list(template.canais or []),
                "canais_usados": canais,
                "por_canal": por_canal,
                "nota": (
                    "Os canais sao os que o template pede em `canais`. "
                    + (
                        "Este template nao tem canais configurados, e o teste "
                        "caiu para 'push' (registar no painel) — e' o unico "
                        "canal que esta instalacao sabe fazer. Configure "
                        "`canais` para escolher outros."
                        if not template.canais
                        else ""
                    )
                    + "Web Push nao esta configurado, e o email so entrega se "
                    "houver um backend real — o que se verifica em "
                    "`por_canal`, canal a canal, com o motivo de cada "
                    "nao-entrega. Um canal nao entregue nao e' um erro "
                    "silencioso: esta escrito."
                ),
                "detalhe": resultados,
            }
        )
