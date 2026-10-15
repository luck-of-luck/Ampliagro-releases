"""O `PROTECT` é a rede que impede uma cultura de levar safras de gente.

PORQUE ESTE FICHEIRO EXISTE
===========================
Tres comentários no código citam-no como se existisse:

    app/models/safra.py:50      # `tests_cascata_cultura.py`.
    app/models/producao.py:21   # `tests_cascata_cultura.py`.
    app/models/producao.py:181  # `tests_cascata_cultura.py`.

Não existia. Um comentário que afirma uma protecção que ninguém testa é
pior do que um comentário ausente: quem o lê acredita que há uma rede, e
alguém que mude um `PROTECT` para `CASCADE` não recebe nada para o saber.

O QUE UM `CASCADE` CUSTARIA
============================
`on_delete=models.CASCADE` numa cultura apagada leva três anos de produção
registada sem um único aviso. `PROTECT` recusa a operação e devolve a
verdade a quem tentou: há registos a depender.

OS OITO `PROTECT` PARA `Cultura`, E AS DUAS EXCEPÇÕES
=====================================================
Fixados um a um, porque a lista é curta e cada um é uma decisão:

    Safra.cultura                PROTECT   safra.py:51
    RegistroProducao.cultura     PROTECT   producao.py:16
    PrescricaoVRA.cultura        PROTECT   producao.py:182
    ZARC.cultura                 PROTECT   producao.py:386
    Experimento.cultura          PROTECT   producao.py:480
    EnsaioCultivar.cultura       PROTECT   producao.py:591   (G-03)
    LoteMuda.cultura             PROTECT   viveiro.py        (G-04)
    MixPastagem.cultura          PROTECT   pecuaria.py       (G-06)

    Talhao.cultura_atual         SET_NULL  core.py:153
    MonitoramentoPraga.cultura   SET_NULL  mip.py:14

As excepções são deliberadas e estão testadas como tal. `Talhao.cultura_atual`
é o，甚 "qual é a cultura que está plantada agora" — o talhão sobrevive à
cultura, e o ciclo recomeça. `MonitoramentoPraga` é um registo de
observação; perder a ligação é aceitável, perder três anos de safra não é.
"""

from django.contrib.auth.models import User
from django.db.models import ProtectedError
from django.test import TestCase

from app.models import (
    ZARC,
    Cultura,
    EnsaioCultivar,
    Experimento,
    LoteMuda,
    MixPastagem,
    MonitoramentoPraga,
    Piquete,
    PrescricaoVRA,
    Propriedade,
    RegistroProducao,
    Safra,
    Talhao,
    Viveiro,
)


class CascataCulturaTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "produtor_cascata", "cascata@x.com", "senhaforte123"
        )
        self.prop = Propriedade.objects.create(
            user=self.user, nome="Fazenda Cascata", area_total=100
        )
        self.talhao = Talhao.objects.create(
            propriedade=self.prop, nome="T-01", area_hectare=10
        )
        self.soja = Cultura.objects.create(nome="Soja", grupo="graos")

    # --- os oito PROTECT ---------------------------------------------------

    def test_safra_impede_apagar_a_cultura(self):
        self._safra()
        with self.assertRaises(ProtectedError):
            self.soja.delete()
        self.assertTrue(Cultura.objects.filter(pk=self.soja.pk).exists())

    def _safra(self):
        return Safra.objects.create(
            propriedade=self.prop,
            cultura=self.soja,
            ano=2026,
            safra_nome="Soja 2026/27",
            area_plantada=10,
            observacao="",
        )

    def test_registro_producao_impede_apagar_a_cultura(self):
        RegistroProducao.objects.create(
            user=self.user, cultura=self.soja, nome="Soja", quantidade=100
        )
        with self.assertRaises(ProtectedError):
            self.soja.delete()

    def test_prescricao_vra_impede_apagar_a_cultura(self):
        PrescricaoVRA.objects.create(
            safra=self._safra(),
            talhao=self.talhao,
            cultura=self.soja,
            tipo_insumo="FERTILIZANTE",
            dose_ha=200,
            unidade="kg/ha",
            grade_geojson={},
            iso_xml="",
        )
        with self.assertRaises(ProtectedError):
            self.soja.delete()

    def test_zarc_impede_apagar_a_cultura(self):
        ZARC.objects.create(
            cultura=self.soja,
            uf="MT",
            municipio="Muzambinho",
            data_inicio_plantio="2026-10-01",
            data_fim_plantio="2027-02-28",
            ciclo_dias=120,
            risco_climatico=0.15,
        )
        with self.assertRaises(ProtectedError):
            self.soja.delete()

    def test_experimento_impede_apagar_a_cultura(self):
        Experimento.objects.create(
            uid="exp-cascata-1",
            user=self.user,
            cultura=self.soja,
            nome="Dose vs dose",
            hypothesis="H1",
            variavel="N",
            tratamento_a="100",
            tratamento_b="200",
            metricas={},
            significance_level=0.05,
            status="PLANEJADO",
            data_inicio="2026-10-01",
            contexto_inicial={},
        )
        with self.assertRaises(ProtectedError):
            self.soja.delete()

    def test_ensaio_cultivar_impede_apagar_a_cultura(self):
        """6º PROTECT (G-03): ensaio sazonal nao e' razao para perder a
        cultura do catalogo."""
        EnsaioCultivar.objects.create(
            user=self.user, cultura=self.soja, nome="Ensaio G03"
        )
        with self.assertRaises(ProtectedError):
            self.soja.delete()

    def test_lote_muda_impede_apagar_a_cultura(self):
        """7º PROTECT (G-04): a muda ja produzida sobrevive ao catalogo."""
        viveiro = Viveiro.objects.create(
            propriedade=self.prop, nome="Viveiro Central", tipo="estaquia"
        )
        LoteMuda.objects.create(viveiro=viveiro, cultura=self.soja)
        with self.assertRaises(ProtectedError):
            self.soja.delete()

    def test_mix_pastagem_impede_apagar_a_cultura(self):
        """8º PROTECT (G-06): o mix e' o que o piquete contem; apagar a
        especie do catalogo nao apaga o que ja foi plantado."""
        piquete = Piquete.objects.create(
            propriedade=self.prop,
            nome="P-01",
            area_hectare=10,
            capacidade_ua_ha=3,
        )
        MixPastagem.objects.create(piquete=piquete, cultura=self.soja, pct=60)
        with self.assertRaises(ProtectedError):
            self.soja.delete()

    def test_apagar_cultura_nao_leva_a_safra(self):
        """O objectivo final, medido pelo efeito e não pela excepção.

        A `ProtectedError` é o meio. O que interessa é que a safra continua
        a existir depois da tentativa — é isso que o produtor não vê, e é por
        isso que ele confia no sistema.
        """
        safra = self._safra()
        try:
            self.soja.delete()
        except ProtectedError:
            pass
        self.assertTrue(Safra.objects.filter(pk=safra.pk).exists())

    # --- as duas excepções, fixadas como excepções -----------------------

    def test_monitoramento_praga_permite_apagar(self):
        """`SET_NULL` é deliberado. Este teste existe para o fixar: quem o
        mudar para `PROTECT` vê isto falhar e lê aqui porque é que se
        perdeu."""
        praga = MonitoramentoPraga.objects.create(
            talhao=self.talhao,
            cultura=self.soja,
            data="2026-01-15",
            praga="lagarta",
            nivel_infestacao=15,
        )
        self.soja.delete()
        praga.refresh_from_db()
        self.assertIsNone(
            praga.cultura_id,
            "esperava SET_NULL; se isto parte, o on_delete mudou e a "
            "excepção deliberada deixou de ser deliberada",
        )

    def test_talhao_permite_apagar_a_cultura_atual(self):
        """O talhão é a folha que não se perde. O ciclo é que recomeça."""
        self.talhao.cultura_atual = self.soja
        self.talhao.save()
        self.soja.delete()
        self.talhao.refresh_from_db()
        self.assertIsNone(self.talhao.cultura_atual_id)
        self.assertTrue(Talhao.objects.filter(pk=self.talhao.pk).exists())

    # --- o caminho normal de uma cultura sem nada dependente -------------

    def test_cultura_sem_dependencias_apaga_normalmente(self):
        """O outro lado: `PROTECT` não pode tornar o catálogo impossível de
        gerir. Uma cultura que ninguém usa tem de apagar."""
        orfa = Cultura.objects.create(nome="Canola", grupo="oleaginosas")
        orfa.delete()
        # MEDIDO 2026-10-05. Filtrar por `nome` dava `True is not false`: a
        # migracao `0008_expandir_grupos_culturas` ja semeia uma "Canola", e
        # `Cultura.nome` NAO tem unique (verificado: `campo.unique is False`,
        # zero constraints). O `create` fazia um duplicado, o `delete` apagava
        # o novo, e o filtro encontrava o antigo — um falso positivo que
        # acusava o `PROTECT` de bloquear o catalogo sem o bloquear.
        #
        # `pk` e' o que se quer medir: apagou ESTE registo, ou nao?
        self.assertFalse(Cultura.objects.filter(pk=orfa.pk).exists())

    def test_multiplas_culturas_apagam_independente(self):
        """Apagar uma não leva as outras — o bug clássico do `PROTECT` mal
        posto, em que o campo errado o ganha e o catálogo inteiro fica
        bloqueado."""
        a = Cultura.objects.create(nome="Milho", grupo="graos")
        b = Cultura.objects.create(nome="Algodão", grupo="fibras")
        a.delete()
        self.assertFalse(Cultura.objects.filter(pk=a.pk).exists())
        self.assertTrue(Cultura.objects.filter(pk=b.pk).exists())

    def test_m2m_nao_bloqueia_o_apagamento(self):
        """`Propriedade.culturas` é ManyToMany: apagar a cultura só desliga
        a ligação. É o comportamento certo para uma lista de culturas
        possíveis de uma fazenda."""
        self.prop.culturas.add(self.soja)
        self.soja.delete()
        self.assertFalse(Cultura.objects.filter(pk=self.soja.pk).exists())
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.culturas.count(), 0)
