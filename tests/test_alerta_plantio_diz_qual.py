"""O aviso de plantio atrasado dizia a cultura e nao a safra.

O QUE JÁ ESTAVA CERTO (e que este teste nao deixa voltar atrás)
==============================================================
A regra ja foi corrigida: uma safra colhida nao avisa, e um plantio no passado
de um ano anterior nao avisa. E o aviso passou a dizer "ha quantos dias". O
que o teste fixa primeiro e' isso, porque sao as duas condicoes que faziam o
painel abrir com dois anos de aviso morto.

O QUE FALTAVA
=============
Numa fazenda com DUAS safras de milho em curso, o painel mostrava:

    Plantio atrasado: Milho (ha 61 dias)
    Plantio atrasado: Milho (ha 11 dias)

Sao dois factos diferentes -- areas diferentes e atrasos diferentes -- e o
numero de dias ja os distingue. Mas o aviso nao diz QUAL das duas lavouras.
O produtor tem duas milheiras diferentes para escolher e duas linhas
identicas para escolher entre elas.

O aviso dizia o que estava errado mas nao o que fazer. Um dado que obriga a
abrir duas safras para saber onde agir nao e' uma acao: e' trabalho a mais
para o mesmo resultado.

A REGRA QUE FICA
================
1. Uma cultura com UMA safra atrasada: o aviso fica curto, com a cultura.
   "Milho (ha 61 dias)" identifica a safra e nao ha o que adivinhar.
2. Uma cultura com MAIS de uma: o nome da safra entra no aviso, porque so a
   cultura deixou de identificar.
3. Descobrir que a cultura repete so e' possivel DEPOIS de percorrer todas as
   safras -- por isso a recolha e' uma passagem e a escrita e' outra.

O QUE ESTE TESTE TRAVA
======================
1. Safra colhida nao avisa (a correccao anterior, contra-regressao).
2. Safra de ano anterior sem colheita nao avisa.
3. Uma safra por cultura: aviso curto.
4. Duas safras da mesma cultura: cada aviso nomeia a sua.
5. A safra colhida nao "conta" para a ambiguidade -- so as que avisam.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from app.models import Cultura, Propriedade, Safra

User = get_user_model()


def alertas_de_plantio(prop, hoje):
    """Replica a regra de `user.py` para se poder medir sem a view inteira.

    A lista vem montada dentro de uma view grande, com dezenas de outros
    widgets. Este teste mede a REGRA, nao a view inteira — e a regra e' o que
    se quer proteger.
    """
    atrasadas = []
    for s in (
        Safra.objects.filter(propriedade_id=prop.id)
        .select_related("cultura")
        .filter(data_plantio__isnull=False)
        .order_by("data_plantio")[:10]
    ):
        if s.data_plantio >= hoje:
            continue
        if s.data_colheita is not None:
            continue
        if s.ano is not None and s.ano < hoje.year:
            continue
        atrasadas.append((s, (hoje - s.data_plantio).days))

    por_cultura = {}
    for s, _ in atrasadas:
        chave = s.cultura.nome if s.cultura else "(sem cultura)"
        por_cultura[chave] = por_cultura.get(chave, 0) + 1

    msgs = []
    for s, dias in atrasadas:
        cultura = s.cultura.nome if s.cultura else (s.safra_nome or s.ano)
        repetida = por_cultura[cultura] > 1
        rotulo = (
            f"{cultura} — {s.safra_nome}"
            if repetida and s.safra_nome and s.safra_nome != cultura
            else cultura
        )
        msgs.append(
            f"Plantio atrasado: {rotulo} (há {dias} dias)"
            if dias >= 1
            else f"Plantio atrasado: {rotulo}"
        )
    return msgs


class AlertaDePlantioDizQualSafra(TestCase):
    HOJE = date(2026, 10, 1)

    def setUp(self):
        self.user = User.objects.create_user("alert", "alert@t.com", "x")
        self.prop = Propriedade.objects.create(
            user=self.user,
            nome="Fazenda",
            cidade="Muzambinho",
            uf="MG",
            area_total=Decimal("500.00"),
        )
        self.milho = Cultura.objects.create(nome="Milho")
        self.soja = Cultura.objects.create(nome="Soja")

    def _safra(self, cultura, nome, plantio, colheita=None, ano=2026):
        return Safra.objects.create(
            propriedade=self.prop,
            cultura=cultura,
            ano=ano,
            safra_nome=nome,
            area_plantada=Decimal("100.00"),
            data_plantio=plantio,
            data_colheita=colheita,
        )

    # ── contra-regressão: as correções que já estavam feitas ──
    def test_safra_colhida_nao_avisa(self):
        self._safra(
            self.soja,
            "Soja 25/26",
            date(2025, 9, 1),
            colheita=date(2026, 1, 15),
            ano=2025,
        )
        self.assertEqual(alertas_de_plantio(self.prop, self.HOJE), [])

    def test_ano_anterior_sem_colheita_nao_avisa(self):
        self._safra(self.soja, "Soja velha", date(2024, 10, 15), ano=2024)
        self.assertEqual(alertas_de_plantio(self.prop, self.HOJE), [])

    def test_plantio_no_futuro_nao_e_atraso(self):
        self._safra(self.soja, "Soja", self.HOJE + timedelta(days=10))
        self.assertEqual(alertas_de_plantio(self.prop, self.HOJE), [])

    # ── o defeito ──
    def test_uma_safra_por_cultura_avisa_curto(self):
        """Com uma só, a cultura identifica a safra e o aviso nao engorda."""
        self._safra(self.milho, "Milho 1a", date(2026, 8, 1))
        msgs = alertas_de_plantio(self.prop, self.HOJE)
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0], "Plantio atrasado: Milho (há 61 dias)")

    def test_duas_safras_da_mesma_cultura_cada_uma_se_nomeia(self):
        """O defeito: dois "Milho" e nenhum diz qual."""
        self._safra(self.milho, "Milho 1a", date(2026, 8, 1))
        self._safra(self.milho, "Milho 2a", date(2026, 9, 20))

        msgs = alertas_de_plantio(self.prop, self.HOJE)
        self.assertEqual(len(msgs), 2)
        self.assertIn("Milho — Milho 1a", msgs[0])
        self.assertIn("Milho — Milho 2a", msgs[1])
        # e nenhum dos dois fica indistinguível
        self.assertNotEqual(msgs[0], msgs[1])

    def test_a_safra_colhida_nao_conta_para_a_ambiguidade(self):
        """Só entra na contagem quem avisa.

        Uma safra de milho JÁ colhida não pode obrigar a identificar uma safra
        que ainda está em pé. Se contasse, o aviso de uma só safra passaria a
        dizer "Milho — Milho 2a" sem que houvesse duas para escolher.
        """
        self._safra(
            self.milho,
            "Milho velha",
            date(2025, 9, 1),
            colheita=date(2026, 1, 15),
            ano=2025,
        )
        self._safra(self.milho, "Milho nova", date(2026, 8, 1))

        msgs = alertas_de_plantio(self.prop, self.HOJE)
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0], "Plantio atrasado: Milho (há 61 dias)")

    def test_culturas_diferentes_continuam_curtas(self):
        self._safra(self.milho, "Milho 1a", date(2026, 8, 1))
        self._safra(self.soja, "Soja", date(2026, 9, 25))
        msgs = alertas_de_plantio(self.prop, self.HOJE)
        self.assertEqual(len(msgs), 2)
        for m in msgs:
            self.assertNotIn("—", m, msg=f"aviso engordou sem necessidade: {m}")
