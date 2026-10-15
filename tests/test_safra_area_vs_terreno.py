"""Uma safra tem de caber no terreno onde foi registada.

O DEFEITO
=========
`SafraSerializer` validava `area_plantada > 0` e mais nada. Um produtor
podia (e alguém podia por importação) registar uma safra de 45.000 ha
apontada para um talhão de 15 ha, numa propriedade de 1.240 ha. E foi
exatamente o que estava no banco da Fazenda Modelo (Primavera do Leste/MT),
safra id=13, "Feijão-carioca", 45.000 ha, talhão "Alpiste 001" de 15 ha.

O efeito não era um erro de formulário. Era o número no painel: o cartão de
área respondia 45.000 ha a "quanto tenho plantado", e o produtor multiplicava
uma safra impossível pelo preço da saca para decidir o que vender.

Nenhum `checar_drift` o apanhava — o drift compara SCHEMA (banco e modelos
dizem o mesmo), e este registo tinha o schema certo e o valor errado.

POR QUE RECUSAR E NÃO CORRIGIR EM SILÊNCIO
==========================================
Ninguém sabe qual era o valor certo. Um número inventado para tapar outro é
uma segunda mentira, e uma pior: a primeira estava visível no formulário, a
segunda estava escondida num total. Este ficheiro recusa a entrada NOVA com
uma mensagem que diz o que se passou e onde; a correção dos registos
existentes é trabalho de quem conhece a fazenda, e não de um validador.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from app.api.serializers import SafraSerializer
from app.models import Cultura, Propriedade, Safra, Talhao

User = get_user_model()


class SafraTemDeCaberNoTerreno(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("val_t", "val_t@t.com", "x")
        self.prop = Propriedade.objects.create(
            user=self.user,
            nome="Fazenda",
            cidade="Primavera do Leste",
            uf="MT",
            area_total=Decimal("1240.00"),
        )
        self.cultura = Cultura.objects.create(nome="Feijão-carioca")
        self.talhao = Talhao.objects.create(
            propriedade=self.prop,
            nome="Alpiste 001",
            area_hectare=Decimal("15.00"),
        )
        self.talhao_500 = Talhao.objects.create(
            propriedade=self.prop,
            nome="Talhão Grande",
            area_hectare=Decimal("500.00"),
        )

    def _serializer(self, **extra):
        base = {"propriedade": self.prop.id, "cultura": self.cultura.id, "ano": 2026}
        base.update(extra)
        return SafraSerializer(data=base)

    # ───────────────────────────────────────────────────────────────────
    # 1. O caso real
    # ───────────────────────────────────────────────────────────────────
    def test_recusa_45000_ha_num_talhao_de_15_ha(self):
        """O número exato que estava no banco.

        Este é o teste que impede a reintrodução. A tolerância é de 10% —
        16,5 ha — e 45.000 está três mil vezes acima.
        """
        s = self._serializer(talhao=self.talhao.id, area_plantada="45000.00")

        self.assertFalse(s.is_valid(), "45.000 ha num talhão de 15 ha foi aceite")
        msg = str(s.errors)
        self.assertIn("area_plantada", s.errors)
        self.assertIn("Alpiste 001", msg, "a mensagem não diz qual talhão é")
        self.assertIn("15.00", msg, "a mensagem não diz a área do talhão")

    def test_a_mensagem_diz_ao_produutor_o_que_fazer(self):
        """Um erro que não diz o que fazer é um beco.

        O produtor tem de conseguir responder à pergunta sozinho: é o talhão
        que está errado, ou é a área? A mensagem nomeia os dois e diz o
        caminho.
        """
        s = self._serializer(talhao=self.talhao.id, area_plantada="45000.00")
        self.assertFalse(s.is_valid())
        msg = str(s.errors["area_plantada"]).lower()
        self.assertIn("talhão", msg)
        self.assertIn("reveja", msg)

    # ───────────────────────────────────────────────────────────────────
    # 2. Sem talhão, a propriedade é a âncora
    # ───────────────────────────────────────────────────────────────────
    def test_sem_talhao_compara_com_a_area_da_propriedade(self):
        """Sem talhão não há medida mais específica — a propriedade chega.

        É o caminho por onde o registo corrompido pode voltar: alguém
        cadastra a safra sem talhão, e a única comparação disponível passa a
        ser a área da fazenda.
        """
        s = self._serializer(area_plantada="45000.00")

        self.assertFalse(s.is_valid())
        msg = str(s.errors["area_plantada"])
        self.assertIn("propriedade", msg.lower())
        self.assertIn("1,240.00", msg)

    # ───────────────────────────────────────────────────────────────────
    # 3. A tolerância tem de existir
    # ───────────────────────────────────────────────────────────────────
    def test_a_area_do_talhao_inteiro_passa(self):
        """O talhão inteiro é o caso normal, e tem de entrar sem atrito."""
        s = self._serializer(talhao=self.talhao_500.id, area_plantada="500.00")
        self.assertTrue(s.is_valid(), s.errors)

    def test_uma_sobra_de_dez_por_cento_passa(self):
        """Talhões que se sobrepõem existem. 10% de folga absorve-os.

        Um validador demasiado apertado faz o produtor contorná-lo — e um
        contorno é sempre pior que a excepção que motivou.
        """
        s = self._serializer(talhao=self.talhao_500.id, area_plantada="550.00")
        self.assertTrue(
            s.is_valid(),
            f"10% de folga foi recusado: {s.errors}. A tolerância é o que "
            "impede o produtor de contornar a validação.",
        )

    def test_duas_safras_no_mesmo_ano_podem_caber_na_fazenda(self):
        """Soja e safrinha no mesmo ano é a rotação normal.

        A validação contra a propriedade tem de tolerar mais do que a área
        da fazenda, ou recusa o que um produtor de grãos faz todos os anos.
        """
        s = self._serializer(area_plantada="2000.00")  # 1,6x a fazenda
        self.assertTrue(s.is_valid(), s.errors)

    def test_area_sem_talhao_e_sem_propriedade_nao_e_um_beco(self):
        """Se não há contra o que comparar, a validação não pode travar.

        Uma propriedade com `area_total` a zero (ninguém a mediu) e uma safra
        sem talhão não têm medida de referência. Recusar aqui seria
        inventar uma regra que ninguém pediu.
        """
        prop_sem_area = Propriedade.objects.create(
            user=self.user,
            nome="Sem Medir",
            cidade="X",
            uf="MG",
            area_total=Decimal("0"),
        )
        s = SafraSerializer(
            data={
                "propriedade": prop_sem_area.id,
                "cultura": self.cultura.id,
                "ano": 2026,
                "area_plantada": "500.00",
            }
        )
        self.assertTrue(s.is_valid(), s.errors)

    def test_talhao_sem_area_nao_bloqueia_a_safra(self):
        """Um talhão cadastrado a olho, com área a zero, não tem medida.

        E bloquear a safra por causa disso seria transformar um dado em falta
        numa recusa: o produtor tem de poder registar a safra, mesmo sem o
        talhão medido.
        """
        talhao_sem_area = Talhao.objects.create(
            propriedade=self.prop, nome="Sem Medir", area_hectare=Decimal("0")
        )
        s = self._serializer(talhao=talhao_sem_area.id, area_plantada="500.00")
        self.assertTrue(s.is_valid(), s.errors)

    # ───────────────────────────────────────────────────────────────────
    # 4. As regras que já existiam continuam a valer
    # ───────────────────────────────────────────────────────────────────
    def test_area_zero_continua_recusada(self):
        s = self._serializer(area_plantada="0")
        self.assertFalse(s.is_valid())
        self.assertIn("area_plantada", s.errors)

    def test_area_negativa_continua_recusada(self):
        s = self._serializer(area_plantada="-10")
        self.assertFalse(s.is_valid())
        self.assertIn("area_plantada", s.errors)

    def test_colheita_antes_do_plantio_continua_recusada(self):
        s = self._serializer(
            area_plantada="100.00",
            data_plantio="2026-03-01",
            data_colheita="2026-02-01",
        )
        self.assertFalse(s.is_valid())

    # ───────────────────────────────────────────────────────────────────
    # 5. A alteração tem de alcançar a SAFRA, não só a entrada
    # ───────────────────────────────────────────────────────────────────
    def test_corrigir_a_area_de_uma_safra_existente_tambem_e_validada(self):
        """Editar passa pelo mesmo caminho — o defeito nasce de uma edição.

        Um validador que só guarda e deixa editar aberto deixa a porta
        exacta por onde o problema entrou.
        """
        s = SafraSerializer(
            instance=Safra.objects.create(
                propriedade=self.prop,
                cultura=self.cultura,
                ano=2026,
                area_plantada=Decimal("100.00"),
                talhao=self.talhao,
            ),
            data={"area_plantada": "45000.00"},
            partial=True,
        )
        self.assertFalse(
            s.is_valid(),
            "a edição de uma safra para 45.000 ha num talhão de 15 ha foi "
            "aceite. A validação tem de valer para update como para create.",
        )
