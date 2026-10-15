"""A2b — o laco de medicao, exposto.

O QUE FAZ E POR QUE VIVE NUM FICHEIRO SEPARADO DO `vra.py`
-----------------------------------------------------------
`vra.py` expoe a **prescricao** (o que se mandou aplicar). Este expoe a
**medicao** (o que se mediu) e a ligacao entre as duas.

Sao coisas diferentes com ciclos de vida diferentes — o experimento fecha, as
medicoes ficam — e a ligacao `MedicaoExperimental.prescricao` e' o que fecha o
laco do §4.3: recomendacao -> medicao -> desfecho.

IDEMPOTENCIA — O PROBLEMA CONCRETO
-----------------------------------
O `experiment.js` trabalha offline no talhao e acumula medicoes numa fila. A
rede pode cair **a meio** de um pedido: o cliente recebe erro, mantem o item
marcado como pendente, e volta a tentar quando a rede volta.

O `data-sync.js` faz `item.id ? PUT : POST`. Se o primeiro POST **chegou ao
servidor mas a resposta nao chegou ao cliente**, o servidor ja tem o registo e
o cliente nao sabe. Na proxima tentativa, `item.id` ainda e' falso, faz POST de
novo, e o servidor cria um **duplicado**. Nao ha como saber que e' o mesmo.

Aqui o `uid` e' gerado no cliente, tem `unique=True`, e o create/update e' feito
por `uid`. O mesmo push duas vezes resulta no mesmo registo. Uma propriedade
`_pendente` nao resolve: duplica o mesmo fato duas vezes na base.

TENANCY
-------
Isolado por `user`, como o resto. E a ligacao `prescricao` so e' aceite se
pertencer ao mesmo produtor — senao o A2b seria um vector para ler a
proveniencia de outro (ver `test_outro_produtor_nao_ve_a_medicao`).
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from app.api.serializers import (
    Experimento_Serializer,
    MedicaoExperimental_Serializer,
)
from app.models import Experimento, MedicaoExperimental, PrescricaoVRA


class ExperimentoViewSet(viewsets.ModelViewSet):
    serializer_class = Experimento_Serializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Experimento.objects.filter(user=self.request.user)
            .select_related("safra", "talhao_a", "talhao_b", "cultura", "propriedade")
            .prefetch_related("medicoes")
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def create(self, request, *args, **kwargs):
        """POST idempotente por `uid`.

        Um experimento reenviado nao pode nascer duas vezes — ver o docstring do
        modulo.
        """
        uid = (request.data or {}).get("uid")
        if uid:
            existente = self.get_queryset().filter(uid=uid).first()
            if existente:
                ser = self.get_serializer(existente, data=request.data, partial=True)
                ser.is_valid(raise_exception=True)
                ser.save()
                return Response(ser.data, status=status.HTTP_200_OK)
        return super().create(request, *args, **kwargs)

    @action(detail=True, methods=["get"])
    def analise(self, request, pk=None):
        """As medicoes do experimento, ja ordenadas e com o contexto.

        Devolve o bruto. A estatistica e' do cliente (`experiment.js`), porque
        foi verificada contra tabelas t publicadas la, e duas implementacoes
        do mesmo teste estatistico divergem sem ninguem dar por isso.
        """
        exp = self.get_object()
        dados = MedicaoExperimental_Serializer(
            exp.medicoes.all(), many=True, context=self.get_serializer_context()
        ).data
        return Response(
            {
                "experimento": self.get_serializer(exp).data,
                "medicoes": dados,
                "total": len(dados),
                "fonte_dado": exp.contexto_inicial.get("fonte_dado") or "sem_dado",
            }
        )

    @action(detail=True, methods=["post"])
    def fechar(self, request, pk=None):
        """Marca como concluido. O que se fecha e' o desenho, nao as medicoes."""
        exp = self.get_object()
        exp.status = "concluido"
        exp.data_fim = exp.data_fim or timezone.localdate()
        exp.save(update_fields=["status", "data_fim", "atualizado_em"])
        return Response(self.get_serializer(exp).data)


class MedicaoExperimentalViewSet(viewsets.ModelViewSet):
    serializer_class = MedicaoExperimental_Serializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return MedicaoExperimental.objects.filter(
            experimento__user=self.request.user
        ).select_related("experimento", "prescricao", "talhao")

    def _resolve_experimento(self, bruto):
        """Troca `experimento_uid` (identidade do cliente) pelo `experimento` (PK).

        O cliente **nao conhece** o `id` do servidor — o experimento pode ter
        sido criado offline, e a rede pode nunca ter voltado. O que ele conhece e' o
        `uid` que gerou. E' por isso que o `uid` existe.

        MEDIDO: sem esta traducao, **todas** as medicoes eram rejeitadas com
        "experimento: Este campo e' obrigatorio" — porque o payload trazia
        `experimento_uid` e o serializer quer `experimento`. Um cliente que
        respeita a documentacao falha sempre. Este erro so apareceu porque o
        teste Python e o `.cjs` correm juntos; cada um sozinho passa.

        Aceita as duas formas: `experimento_uid` tem prioridade (e' o caminho
        do offline), `experimento` continua a funcionar para quem ja tem o id.
        """
        bruto = dict(bruto or {})
        uid = bruto.pop("experimento_uid", None)
        if uid and not bruto.get("experimento"):
            exp = (
                Experimento.objects.filter(uid=uid, user=self.request.user)
                .only("pk")
                .first()
            )
            if exp is None:
                return None, f"experimento_uid {uid!r} nao existe ou nao e' teu"
            bruto["experimento"] = exp.pk
        return bruto, None

    def _resolve_prescricao(self, bruto, experimento):
        """Achata a prescricao que esta medicao avalia, sem ecra.

        POR QUE ISTO EXISTE — e porque nao e' uma deduplicacao
        -------------------------------------------------------
        O §4.3 fecha o laco assim: **recomendacao -> medicao -> desfecho**. A
        ligacao do meio e' a `MedicaoExperimental.prescricao`, e sem ela a
        medicao e' um numero solto que ninguem consegue ligar a uma decisao.

        Escolher a prescricao na interface e' o caminho certo, e continua por
        fazer. Mas ate la haver ecra, o laço **nao fecha**, e um laco que so
        fecha depois de uma tela depende da tela. Aqui o servidor resolve por
        safra + talhao + cultura: que e' exactamente a identidade de "a
        recomendacao que vale para este talhao nesta safra".

        TAMBEM NAO E' MAGIC. Se houver varias, nao adivinha — a medicao fica sem
        prescricao e o motivo fica escrito no resultado. Escolher sozinho entre
        varias recomendacoes compativeis seria inventar qual delas o produtor
        estava a avaliar, e e' o tipo de numero que este projecto nao produz.

        E o cliente pode sempre mandar `prescricao` explicito, que ganha.
        """
        bruto = dict(bruto or {})
        if bruto.get("prescricao"):
            return bruto, None
        if experimento is None:
            return bruto, None

        talhao_id = (
            bruto.get("talhao") or experimento.talhao_a_id or experimento.talhao_b_id
        )
        if not talhao_id:
            return bruto, None

        qs = PrescricaoVRA.objects.filter(talhao_id=talhao_id)
        if experimento.safra_id:
            qs = qs.filter(safra_id=experimento.safra_id)
        if experimento.cultura_id:
            qs = qs.filter(cultura_id=experimento.cultura_id)

        candidatos = list(qs.order_by("-criado_em")[:2])
        if len(candidatos) == 1:
            bruto["prescricao"] = candidatos[0].pk
            return bruto, None
        if len(candidatos) > 1:
            return bruto, (
                f"{len(candidatos)} prescricoes servem este talhao nesta safra; "
                "manda `prescricao` explicitamente para saber qual avalias"
            )
        return bruto, None

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """POST idempotente por `uid`, e transaccional.

        A transacao e' porque um experimento pode chegar com medicoes no mesmo
        pedido (offline acumula em lote). Sem atomicidade, metade das medicoes
        ficava gravada e o cliente repetia o lote todo no reenvio — a duplicacao
        que o `uid` evita, mas que ainda assim custaria reescrita.
        """
        uid = (request.data or {}).get("uid")
        if uid:
            existente = self.get_queryset().filter(uid=uid).first()
            if existente:
                ser = self.get_serializer(existente, data=request.data, partial=True)
                ser.is_valid(raise_exception=True)
                ser.save()
                return Response(ser.data, status=status.HTTP_200_OK)

        traduzido, erro = self._resolve_experimento(request.data)
        if erro:
            return Response({"erro": erro}, status=status.HTTP_400_BAD_REQUEST)
        return super().create(request, *args, **kwargs)

    @action(detail=False, methods=["post"])
    def lote(self, request):
        """Recebe N medicoes de uma vez. O caminho normal do offline.

        Devolve o que foi criado e o que ja existia, para o cliente saber que
        pode limpar a fila. Uma falha no meio desfaz o lote inteiro — a rede
        caiu e vale mais tentar o lote todo outra vez do que descobrir depois
        que metade das medicoes sumiu.
        """
        itens = (request.data or {}).get("medicoes")
        if not isinstance(itens, list):
            return Response(
                {"erro": 'esperado {"medicoes": [...]}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(itens) > 500:
            return Response(
                {"erro": "lote acima de 500; envia em partes"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        criados = ja_existiam = rejeitados = 0
        erros = []
        avisos = []
        for i, bruto in enumerate(itens):
            uid = (bruto or {}).get("uid")
            if uid and self.get_queryset().filter(uid=uid).exists():
                ja_existiam += 1
                continue
            traduzido, erro = self._resolve_experimento(bruto)
            if erro:
                rejeitados += 1
                erros.append({"indice": i, "erro": {"experimento_uid": [erro]}})
                continue
            # A2c: fecha o laco do §4.3 sem esperar pela interface.
            # `_resolve_experimento` devolve o `experimento` como PK; aqui
            # precisamos do objecto para comparar safra/cultura.
            exp_obj = Experimento.objects.filter(
                pk=traduzido.get("experimento")
            ).first()
            traduzido, aviso = self._resolve_prescricao(traduzido, exp_obj)
            if aviso:
                # Nao e' erro: e' ambiguidade. A medicao entra sem prescricao e
                # o motivo viaja no resultado, para o produtor escolher.
                avisos.append({"indice": i, "aviso": aviso})
            ser = self.get_serializer(data=traduzido)
            if not ser.is_valid():
                rejeitados += 1
                # Um item mau nao pode derrubar os outros: o produtor mandou 40
                # medicoes e 39 sao boas. O erro diz qual e' qual.
                erros.append({"indice": i, "erro": ser.errors})
                continue
            ser.save()
            criados += 1

        return Response(
            {
                "criados": criados,
                "ja_existiam": ja_existiam,
                "rejeitados": rejeitados,
                "erros": erros,
                # `avisos` != `erros`: a medicao foi guardada, mas o servidor
                # nao conseguiu escolher qual prescricao ela avalia. O produtor
                # precisa de saber que a ligacao ficou por fazer — e nao pode
                # ler "criados: 40" e supor que as 40 ficaram ligadas.
                "avisos": avisos,
            }
        )
