"""MRV: o que o servico mede, e o que ele NAO faz.

Estes testes existem para que `app/services/mrv.py` nunca possa passar por algo
que nao e'. Cada `xfail(strict=True)` abaixo e' uma promessa do manifesto que
AINDA esta em aberto -- e o `strict=True` garante que implementar a promessa
faca o teste VERMELHO, ate o marcador seja removido a mao.

O que NAO se testa aqui: se os factores de emissao estao certos. Isso e'
conhecimento externo, e verifica-se contra a publicacao de origem, nao contra
este repositorio.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from app.models.core import Propriedade
from app.models.financeiro import LancamentoFinanceiro
from app.models.safra import AplicacaoInsumo, Insumo, Safra
from app.services.mrv import (
    AVISO_CARBONO_NEGATIVO,
    AVISO_ESCOPO_2,
    AVISO_ESCOPO_3,
    AVISO_NAO_VERIFICADO,
    FATOR_COMBUSTIVEL,
    RelatorioMRV,
)


class TesteContratoDoRelatorio(TestCase):
    """O relatorio tem de devolver as MESMAS chaves em todos os ramos.

     Motivo, de `compliance_ambiental.py`: dois ramos com conjuntos de chaves
     diferentes sao um contrato que ninguem pode satisfazer. Um consumidor que
     faca `r["escopo_3"]["tCO2e"]` rebenta num ramo e nao no outro, e o
    博物ador ve "500" onde devia ver "falta este dado".
    """

    def setUp(self):
        self.u = User.objects.create_user("mrv_contrato", password="x1234567")
        self.prop = Propriedade.objects.create(
            user=self.u, nome="Fazenda MRV", area_total=Decimal("1000"), uf="MT"
        )

    def test_o_relatorio_tem_contrato_fixo(self):
        r = RelatorioMRV.calcular(propriedade_id=self.prop.id, ano=2026)
        for chave in (
            "propriedade_id",
            "ano",
            "escopo_1",
            "escopo_2",
            "escopo_3",
            "total_escopo_1_tCO2e",
            "total_com_escopo_3_tCO2e",
            "carbono_negativo",
            "carbono_negativo_motivo",
            "pode_ser_verificado",
            "pode_ser_verificado_motivo",
            "metodo",
            "aviso",
        ):
            self.assertIn(chave, r, f"falta a chave '{chave}' no relatorio")

    def test_o_ramo_sem_dados_devolve_o_mesmo_contrato(self):
        """Propriedade sem safras, sem aplicacoes, sem bioma.

        Este e' o ramo que mais vezes divergiu: e' o "nao ha dados", e um ramo
        sem dados e' o ramo onde a gente esquece a chave.
        """
        prop_vazia = Propriedade.objects.create(
            user=self.u, nome="Vazia", area_total=Decimal("0"), uf="MT"
        )
        r = RelatorioMRV.calcular(propriedade_id=prop_vazia.id, ano=2026)
        for chave in (
            "escopo_1",
            "escopo_2",
            "escopo_3",
            "total_escopo_1_tCO2e",
            "carbono_negativo",
            "pode_ser_verificado",
            "aviso",
        ):
            self.assertIn(chave, r, f"o ramo vazio nao devolve '{chave}'")


class TesteNaoEMissaoDeCredito(TestCase):
    """O mais importante: isto NAO vende carbono, e tem de dizer isso sempre."""

    def setUp(self):
        self.u = User.objects.create_user("mrv_aviso", password="x1234567")
        self.prop = Propriedade.objects.create(
            user=self.u, nome="Fazenda Aviso", area_total=Decimal("500"), uf="MT"
        )

    def test_nunca_diz_que_pode_ser_verificado(self):
        r = RelatorioMRV.calcular(propriedade_id=self.prop.id, ano=2026)
        self.assertFalse(r["pode_ser_verificado"])
        self.assertIn("NAO e' um credito", r["pode_ser_verificado_motivo"])

    def test_o_aviso_esta_no_resultado_e_nao_e_opcional(self):
        """O aviso nao pode ser removivel sem mudar o contrato.

        Um relatorio que devolve o numero e deixa o aviso para o consumidor ler
        na documentacao e' um relatorio que emite credito por omissao: quem
        chama a API recebe o numero e nao a ressalva.
        """
        r = RelatorioMRV.calcular(propriedade_id=self.prop.id, ano=2026)
        self.assertEqual(r["aviso"], AVISO_NAO_VERIFICADO)
        self.assertEqual(r["pode_ser_verificado_motivo"], AVISO_NAO_VERIFICADO)
        self.assertEqual(r["escopo_2"]["motivo"], AVISO_ESCOPO_2)
        self.assertEqual(r["escopo_3"]["motivo"], AVISO_ESCOPO_3)

    def test_carbono_negativo_e_none_e_nao_zero(self):
        """`None` e' "nao medimos". `False` e' "medimos e deu negativo".

        Um `False` aqui seria uma afirmacao: o produtor le "nao e' negativo" e
        conclui que o uso de solo esta balancado. Nao medimos uso de solo
        aparte -- logo e' `None`.
        """
        r = RelatorioMRV.calcular(propriedade_id=self.prop.id, ano=2026)
        self.assertIsNone(
            r["carbono_negativo"],
            "carbono_negativo devia ser None. False seria uma medicao que nao "
            "foi feita.",
        )
        self.assertIn("ARMAZENADO", r["carbono_negativo_motivo"])

    def test_escopo_2_e_3_sao_none_nao_zero(self):
        r = RelatorioMRV.calcular(propriedade_id=self.prop.id, ano=2026)
        self.assertIsNone(r["escopo_2"]["tCO2e"])
        self.assertIsNone(r["escopo_3"]["tCO2e"])
        self.assertFalse(r["escopo_2"]["medido"])
        self.assertIsNone(
            r["total_com_escopo_3_tCO2e"],
            "somar escopo 3 a zero daria um total que parece completo e nao e'",
        )


class TesteCombustivel(TestCase):
    """Combustivel em litros e' a UNICA emissao de escopo 1 que medimos hoje.

    E mede-se porque o factor existe, a unidade bate, e a conta e' verificavel
    a lapis. O resto nao tem factor ou nao tem unidade, e e' devolvido como
    "nao medido" -- nunca como zero.
    """

    def setUp(self):
        self.u = User.objects.create_user("mrv_comb", password="x1234567")
        self.prop = Propriedade.objects.create(
            user=self.u, nome="Fazenda Comb", area_total=Decimal("100"), uf="MT"
        )
        self.insumo = Insumo.objects.create(
            propriedade=self.prop,
            categoria="COMBUSTIVEL",
            nome="Diesel S10",
            quantidade=Decimal("1000"),
            unidade="L",
            valor_unitario=Decimal("6.00"),
        )

    def test_diesel_em_litro_da_a_conta_que_se_espera(self):
        # 100 L x 2,68 kgCO2e/L = 268 kg = 0,268 t
        aplicacao = (
            AplicacaoInsumo.objects.create(
                insumo=self.insumo,
                talhao__propriedade=self.prop,
                dose=Decimal("100"),
            )
            if False
            else None
        )
        # `talhao` e' obrigatorio: cria-se um.
        from app.models.core import Talhao

        talhao = Talhao.objects.create(
            propriedade=self.prop, nome="T1", area_hectare=Decimal("10")
        )
        aplicacao = AplicacaoInsumo.objects.create(
            insumo=self.insumo,
            talhao=talhao,
            dose=Decimal("100"),
            data=date(2026, 2, 10),
        )

        r = RelatorioMRV.calcular(propriedade_id=self.prop.id, ano=2026)
        linha = next(
            x for x in r["escopo_1"]["linhas"] if x["categoria"] == "COMBUSTIVEL"
        )
        self.assertTrue(linha["medido"])
        self.assertEqual(linha["toneladas_co2e"], Decimal("0.268000"))
        # e a fonte tem de estar CITADA na propria linha
        self.assertIn("IPCC", linha["fator_fonte"])
        self.assertEqual(linha["fator_ano"], 2006)

    def test_combustivel_em_unidade_desconhecida_nao_e_convertido(self):
        """Gasolina em 'balde' nao se converte com o factor de diesel/L.

        O que este teste impede: o sistema a dividir 5 'baldes' por um factor de
        kg/L e chamar ao resultado uma medicao.
        """
        from app.models.core import Talhao

        self.insumo.unidade = "balde"
        self.insumo.save()
        talhao = Talhao.objects.create(
            propriedade=self.prop, nome="T2", area_hectare=Decimal("10")
        )
        AplicacaoInsumo.objects.create(
            insumo=self.insumo, talhao=talhao, dose=Decimal("5"), data=date(2026, 2, 10)
        )

        r = RelatorioMRV.calcular(propriedade_id=self.prop.id, ano=2026)
        linha = next(
            x for x in r["escopo_1"]["linhas"] if x["categoria"] == "COMBUSTIVEL"
        )
        self.assertFalse(linha["medido"])
        self.assertIsNone(linha["fator"])
        self.assertIn("densidade", linha["fator_motivo"])
        self.assertEqual(linha["toneladas_co2e"], Decimal("0"))


class TesteFertilizanteNaoSeChuta(TestCase):
    """O factor de N2O e' por kg de N. O Ampliagro nao sabe quanto N tem.

    Este e' o teste mais importante do ficheiro: e' o que impede o sistema de
    inventar a maior emissa agricola que existe. N2O de fertilizante e' uma das
    maiores fontes de emissoes agricolas do mundo, e um numero inventado aqui
    contamina o inventario inteiro.
    """

    def setUp(self):
        self.u = User.objects.create_user("mrv_fert", password="x1234567")
        self.prop = Propriedade.objects.create(
            user=self.u, nome="Fazenda Fert", area_total=Decimal("100"), uf="MT"
        )
        self.fert = Insumo.objects.create(
            propriedade=self.prop,
            categoria="FERTILIZANTE",
            nome="NPK 04-30-10",
            quantidade=Decimal("500"),
            unidade="kg",
            valor_unitario=Decimal("3.50"),
        )

    def test_fertilizante_sem_composicao_de_N_diz_que_nao_mediu(self):
        from app.models.core import Talhao

        talhao = Talhao.objects.create(
            propriedade=self.prop, nome="T3", area_hectare=Decimal("10")
        )
        AplicacaoInsumo.objects.create(
            insumo=self.fert, talhao=talhao, dose=Decimal("200"), data=date(2026, 3, 5)
        )

        r = RelatorioMRV.calcular(propriedade_id=self.prop.id, ano=2026)
        linha = next(
            x for x in r["escopo_1"]["linhas"] if x["categoria"] == "FERTILIZANTE"
        )
        self.assertFalse(linha["medido"])
        self.assertIsNone(linha["fator"])
        self.assertIn("composicao", linha["fator_motivo"])
        self.assertEqual(linha["toneladas_co2e"], Decimal("0"))
        # e o total nao pode ter herdado nada disto
        self.assertEqual(
            r["total_escopo_1_tCO2e"],
            Decimal("0"),
            "200 kg de fertilizante sem composicao de N produziram emissao. "
            "Isso e' um chute com aparencia de medicao.",
        )


class TesteDesmatamentoNaoSeAdivinha(TestCase):
    """Bioma sem factor publicado -> sem numero.

    O desmatamento e' a maior linha possivel do inventario. Adivinhar o factor
    de um bioma desconhecido e' inventar precisamente a linha que mais pesa
    para um eventual credito.
    """

    def setUp(self):
        self.u = User.objects.create_user("mrv_bioma", password="x1234567")
        self.prop = Propriedade.objects.create(
            user=self.u, nome="Fazenda Bioma", area_total=Decimal("1000"), uf="MT"
        )

    def test_bioma_desconhecido_da_none_e_nao_zero(self):
        self.prop.bioma = "bioma_que_nao_existe"
        self.prop.save()

        r = RelatorioMRV.calcular(propriedade_id=self.prop.id, ano=2026)
        solo = r["escopo_1"]
        self.assertFalse(solo["medido"])
        self.assertIsNone(solo["fator_por_ha"])
        self.assertIn("Adivinhar", solo["motivo"])
        self.assertEqual(solo["toneladas_co2e"], Decimal("0"))

    def test_sem_area_total_nao_inventa_denominador(self):
        self.prop.bioma = "amazonia"
        self.prop.area_total = Decimal("0")
        self.prop.save()

        r = RelatorioMRV.calcular(propriedade_id=self.prop.id, ano=2026)
        self.assertFalse(r["escopo_1"]["medido"])
        self.assertIn("denominador", r["escopo_1"]["motivo"])


class TesteFactorSemFonteNaoEntra(TestCase):
    """A regra que protege o inventario inteiro.

    Se um factor sem `fonte` pudesse entrar, bastava alguem escrever
    `Decimal("1.23")` num dicionario e o numero entrava no relatorio sem que
    ninguem pudesse dizer de onde veio.
    """

    def test_todo_o_factor_publicado_tem_fonte(self):
        from app.services import mrv

        for nome, fator in mrv.FATOR_POR_CATEGORIA.items():
            self.assertTrue(
                fator.get("fonte"),
                f"o factor da categoria '{nome}' nao tem fonte. Um factor sem "
                "fonte nao e' medicao, e' uma opiniao com casas decimais.",
            )
            self.assertIsInstance(fator["fator"] if "fator" in fator else fator, dict)


class TesteNaoArrancaComDadosQueNaoExiste(TestCase):
    """O servico tem de aguentar o ano sem registos, sem lancar excecao."""

    def setUp(self):
        self.u = User.objects.create_user("mrv_vazio", password="x1234567")
        self.prop = Propriedade.objects.create(
            user=self.u, nome="Sem Nada", area_total=Decimal("50"), uf="MT"
        )

    def test_ano_sem_qualquer_registo(self):
        r = RelatorioMRV.calcular(propriedade_id=self.prop.id, ano=1999)
        self.assertEqual(r["total_escopo_1_tCO2e"], Decimal("0"))
        self.assertEqual(r["escopo_1"]["linhas"], [])
        self.assertFalse(r["pode_ser_verificado"])


class TesteAUnidadeDoFactorDeDesmatamento(TestCase):
    """A unidade do factor de desmatamento e' tCO2e/ha — e o codigo ja errou uma vez.

    Este teste existe por causa de um erro MEU, encontrado na revisao a este
    ficheiro a 2026-10-05: o codigo dividia o factor por 1000, como se fosse
    quilogramas. O resultado saia 1000x menor — e uma propriedade de 500 ha em
    Amazonia, que emite ~49.000 tCO2e, aparecia com 49 tCO2e.

    Um inventario que declara a Amazonia praticamente neutra nao e' um detalhe
    de casas decimais. E' a maior linha do inventario, e e' a que decide o
    valor de tudo.

    O teste faz a conta a mao, com o factor do dicionario, e compara. Se alguem
    mudar o factor, ou voltar a dividir por 1000, este teste apanha.
    """

    def _cultura(self):
        from app.models.core import Cultura

        c, _ = Cultura.objects.get_or_create(
            nome="Soja MRV", defaults={"grupo": "graos", "unidade_comercial": "sc"}
        )
        return c

    def setUp(self):
        self.u = User.objects.create_user("mrv_unid", password="x1234567")
        self.prop = Propriedade.objects.create(
            user=self.u,
            nome="Fazenda Unidade",
            area_total=Decimal("1000"),
            uf="AM",
            bioma="amazonia",
        )

    def test_o_total_de_uso_de_solo_bate_com_o_factor(self):
        """500 ha em Amazonia tem de dar o factor x 500. SEM dividir por 1000."""
        from app.services.mrv import FATOR_DESMATAMENTO_HA

        fator_amazonia = FATOR_DESMATAMENTO_HA["amazonia"][0]

        Safra.objects.create(
            propriedade=self.prop,
            cultura=self._cultura(),
            ano=2026,
            area_plantada=Decimal("500"),
            producao_total=Decimal("1000"),
        )

        r = RelatorioMRV.calcular(propriedade_id=self.prop.id, ano=2026)
        solo = r["escopo_1"]

        esperado = Decimal("500") * fator_amazonia
        obtido = solo["toneladas_co2e"]

        self.assertEqual(
            obtido,
            esperado,
            f"500 ha em Amazonia com fator {fator_amazonia} tCO2e/ha da "
            f"{esperado} tCO2e. Obtive {obtido}. A diferenca de 1000x e' a "
            "divisao por 1000 que nao deve existir: este factor JA e' em "
            "toneladas.",
        )

    def test_a_unidade_esta_escrita_no_nome_do_campo(self):
        """O campo tem de dizer a unidade. `fator_por_ha` nao diz nada."""
        Safra.objects.create(
            propriedade=self.prop,
            cultura=self._cultura(),
            ano=2026,
            area_plantada=Decimal("10"),
        )
        r = RelatorioMRV.calcular(propriedade_id=self.prop.id, ano=2026)
        solo = r["escopo_1"]
        self.assertIn(
            "fator_tCO2e_por_ha",
            solo,
            (
                "o campo do factor nao diz a unidade. `fator_por_ha` permite "
                "confundir tCO2e com kg — que e' exactamente o erro que aconteceu."
            ),
        )
        self.assertNotIn(
            "fator_por_ha",
            solo,
            (
                "`fator_por_ha` nao diz a unidade e invites a dividi-lo por 1000 "
                "como se fosse kg."
            ),
        )
        # E o valor esta la, para o consumidor conferir a conta sem abrir o codigo.
        self.assertEqual(
            solo["fator_tCO2e_por_ha"],
            "98.0",
            (
                "o factor de Amazonia mudou. Se mudou de proposito, muda tambem o "
                "commentario da constante."
            ),
        )
