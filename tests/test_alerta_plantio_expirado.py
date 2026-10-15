"""Um alerta que já não tem ação possível é ruído, e ruído treina o olho.

O DEFEITO
=========
A regra de plantio atrasado era::

    if s.data_plantio < hoje:      ->  alerta "Plantio atrasado"

Isso é verdade para TODA safra cujo plantio já passou — incluindo as safras
de anos anteriores. Na Fazenda Modelo (Primavera do Leste/MT, hoje =
out/2026) o painel abria com:

    Plantio atrasado: Soja   (2024-10-15)
    Plantio atrasado: Milho  (2025-02-28)

Dois anos de aviso, todos os dias, para um produtor que já não pode fazer
nada com eles. E não era aviso: era mentira — a safra de 2024 foi colhida.

O custo de um sistema de alertas não é o alerta falso que aparece; é o
alerta verdadeiro que o produtor deixa de ler. Um painel com 12 avisos dos
quais 9 não têm ação é um painel onde o tenth também é ignorado.

O QUE ESTE TESTE TRAVA
======================
1. Uma safra JÁ COLHIDA não gera "plantio atrasado".
2. Uma safra de ANOS ANTERIORES não gera "plantio atrasado".
3. Uma safra do ano corrente, plantada e não colhida, GERA — e diz há quantos
   dias, porque um "atrasado" sem número obriga a ir abrir a safra.
4. Um atraso longo sobe de nível: duas semanas é calendário, três meses é
   safra perdida.
5. Um plantio FUTURO é novidade, nunca "atrasado".
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from app.api.views.user import _build_alertas_e_novidades
from app.models import Cultura, Propriedade, Safra

User = get_user_model()


class PlantioAtrasadoSoExisteParaSafraEmPe(TestCase):
    def setUp(self):
        self.hoje = date.today()
        self.user = User.objects.create_user("alerta_t", "alerta_t@t.com", "x")
        self.prop = Propriedade.objects.create(
            user=self.user,
            nome="Fazenda",
            cidade="Muzambinho",
            uf="MG",
            area_total=Decimal("1240.00"),
        )
        self.soja = Cultura.objects.create(nome="Soja")
        self.milho = Cultura.objects.create(nome="Milho")

    def _safra(self, cultura, ano, plantio, colheita=None):
        return Safra.objects.create(
            propriedade=self.prop,
            cultura=cultura,
            ano=ano,
            area_plantada=Decimal("200.00"),
            data_plantio=plantio,
            data_colheita=colheita,
        )

    def _alertas_de_safra(self):
        dados = _build_alertas_e_novidades([self.prop])
        return [a for a in dados["alertas_list"] if a["tipo"] == "safra"]

    def _novidades_de_safra(self):
        dados = _build_alertas_e_novidades([self.prop])
        return [n for n in dados["novidades"] if n["tipo"] == "safra"]

    # ───────────────────────────────────────────────────────────────────
    # 1. Safra colhida = nada a fazer
    # ───────────────────────────────────────────────────────────────────
    def test_safra_ja_colhida_nao_e_alerta(self):
        """O caso real: 2024 colhido, e o painel a dizer "atrasado" todos os dias."""
        self._safra(self.soja, 2024, date(2024, 10, 15), colheita=date(2025, 2, 20))

        self.assertEqual(
            self._alertas_de_safra(),
            [],
            "uma safra colhida há mais de um ano continua a dizer 'plantio "
            "atrasado'. Não há atraso: houve colheita.",
        )

    def test_safra_do_ano_passado_sem_colheita_tambem_nao_e_alerta(self):
        """Sem data de colheita, o ANO decide. 2024 não é a safra que espera.

        Descartar em silêncio tem aqui um custo real — o produtor pode ter
        esquecido de registar a colheita. Mas a alternativa (gritar "atrasado"
        dois anos depois) é pior: é ruído, e o ruído é o que apaga os alertas
        que importam. O registo incompleto é um problema de cadastro, e
        tem de ser pedido de outra forma.
        """
        self._safra(self.soja, 2024, date(2024, 10, 15), colheita=None)

        self.assertEqual(
            self._alertas_de_safra(),
            [],
            "uma safra de 2024 sem data de colheita está a gerar 'plantio "
            "atrasado' em 2026.",
        )

    # ───────────────────────────────────────────────────────────────────
    # 2. A safra em pé GERA o alerta
    # ───────────────────────────────────────────────────────────────────
    def test_safra_do_ano_plantada_e_nao_colhida_e_alerta(self):
        """O alerta verdadeiro tem de continuar a aparecer."""
        self._safra(self.soja, self.hoje.year, self.hoje - timedelta(days=10))

        alertas = self._alertas_de_safra()
        self.assertEqual(len(alertas), 1, "a safra em pé perdeu o aviso de atraso")
        self.assertIn("Soja", alertas[0]["msg"])
        self.assertIn("atrasado", alertas[0]["msg"].lower())

    def test_o_alerta_diz_ha_quantos_dias(self):
        """Um "atrasado" sem número obriga o produtor a ir abrir a safra.

        O número é o que permite decidir: dez dias de atraso ainda se
        recupera, cem já não.
        """
        self._safra(self.milho, self.hoje.year, self.hoje - timedelta(days=45))

        alertas = self._alertas_de_safra()
        self.assertEqual(len(alertas), 1)
        self.assertIn(
            "45",
            alertas[0]["msg"],
            "o alerta não diz há quantos dias. O produtor tem de abrir a "
            "safra para saber se ainda está a tempo.",
        )

    def test_um_atraso_longo_sobe_de_nivel(self):
        """Duas semanas é rotina; três meses é uma safra que se perdeu.

        O mesmo nível para os dois treinava o olho a não distinguir.
        """
        self._safra(self.soja, self.hoje.year, self.hoje - timedelta(days=15))
        self._safra(self.milho, self.hoje.year, self.hoje - timedelta(days=100))

        por_cultura = {
            a["msg"].split(":")[1].split("(")[0].strip(): a
            for a in self._alertas_de_safra()
        }

        self.assertEqual(por_cultura["Soja"]["nivel"], "warning")
        self.assertEqual(
            por_cultura["Milho"]["nivel"],
            "critical",
            "100 dias de atraso continuam a ser só um aviso. Uma safra de "
            "milho plantada há três meses e não colhida perdeu-se.",
        )

    # ───────────────────────────────────────────────────────────────────
    # 3. Plantio futuro nunca é "atrasado"
    # ───────────────────────────────────────────────────────────────────
    def test_plantio_futuro_e_novidade_e_nao_alerta(self):
        """A condição anterior podia dizer "atrasado" para um plantio de amanhã.

        A ordem era `if data_plantio < hoje` e o `elif` da novidade só era
        alcançado para datas no FUTURO. Mas o bug real é o inverso: um
        plantio a 10 dias não pode ser "atrasado", e o texto tem de dizer
        QUANDO.
        """
        self._safra(self.soja, self.hoje.year + 1, self.hoje + timedelta(days=10))

        self.assertEqual(self._alertas_de_safra(), [])

        novidades = self._novidades_de_safra()
        atrasados = [n for n in novidades if "atrasado" in n["msg"].lower()]
        self.assertEqual(atrasados, [], "um plantio futuro foi anunciado como atraso")
        self.assertTrue(
            any("Plantio" in n["msg"] for n in novidades),
            "o plantio a dez dias devia aparecer como novidade",
        )

    def test_plantio_futuro_longe_nao_e_nem_novidade(self):
        """Plantio a três meses não é novidade de hoje.

        E o alerta de tempestade do clima não deve interferir — este teste
        é sobre a safra, e uma falha aqui tem de ser distinguível.
        """
        self._safra(self.soja, self.hoje.year + 1, self.hoje + timedelta(days=90))

        dados = _build_alertas_e_novidades([self.prop])
        msgs = [a["msg"] for a in dados["alertas_list"] + dados["novidades"]]
        self.assertFalse(
            [m for m in msgs if m.startswith("Plantio:")],
            f"um plantio a 90 dias foi anunciado como novidade: {msgs}",
        )

    # ───────────────────────────────────────────────────────────────────
    # 4. Uma propriedade sem safras não gera nada
    # ───────────────────────────────────────────────────────────────────
    def test_sem_safras_nao_ha_alerta_de_plantio(self):
        dados = _build_alertas_e_novidades([self.prop])
        self.assertEqual(
            [a for a in dados["alertas_list"] if a["tipo"] == "safra"],
            [],
        )

    def test_a_lista_continua_ordenada_por_gravidade(self):
        """A correção não pode desordenar a lista.

        O painel mostra os 15 primeiros por severidade. Um "atraso" de dois
        meses a `critical` tem de aparecer acima de um aviso de camada.
        """
        self._safra(self.milho, self.hoje.year, self.hoje - timedelta(days=100))
        self._safra(self.soja, self.hoje.year, self.hoje - timedelta(days=10))

        dados = _build_alertas_e_novidades([self.prop])
        niveis = [a["nivel"] for a in dados["alertas_list"]]
        ordem = {"critical": 0, "warning": 1, "info": 2}
        chaves = [ordem.get(n, 3) for n in niveis]
        self.assertEqual(
            chaves, sorted(chaves), "a lista de alertas deixou de estar ordenada"
        )
