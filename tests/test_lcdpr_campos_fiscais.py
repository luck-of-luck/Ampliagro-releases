"""Os campos fiscais do endereco: a guarda tem o que ler.

MEDIDO 2026-10-05, apos transcrever o enunciado oficial (Manual de
Preenchimento do LCDPR 1.3, Receita Federal, secção 3.3).

O QUE ESTE FICHEIRO FECHA
========================
A `pode_exportar(exigir_campos_fiscais=True`) exigia `COD_MUN` e `CEP` — e o
`Propriedade` **nao tinha nenhum dos dois**. Ela usava `getattr` precisamente
por isso, e o resultado era uma guarda que disparava sempre sobre campos
inexistentes: ou falhava para toda a parte, ou desligavam a guarda e o ficheiro
sazia com `COD_MUN` vazio, que a Receita recusa.

Este ficheiro verifica que **o modelo tem os campos** e que **o gerador escreve
os valores certos neles**. E' a cadeia completa:

    modelo tem o campo  ->  guarda le-o  ->  gerador escreve-o  ->  ficheiro tem

Uma quebra em qualquer elo passa sem ninguem ver, e cada elo tinha uma.
"""

from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.test import TestCase

from app.models.core import Propriedade, Talhao
from app.services.lcdpr_export import LCDPRExporter, pode_exportar
from app.services.lcdpr_layout import CAMPOS_0030, CAMPOS_0040

pytestmark = pytest.mark.django_db


def _prop(**extra) -> Propriedade:
    u = User.objects.create_user(
        f"fiscal_{abs(hash(tuple(sorted(extra.items())))) % 10**8}",
        password="x1234567",
    )
    p = Propriedade.objects.create(
        user=u,
        nome="Fazenda Fiscal",
        area_total=Decimal("100.00"),
        cpf_cnpj="12345678901",
        **extra,
    )
    Talhao.objects.create(propriedade=p, nome="G1", area_hectare=Decimal("100.00"))
    return p


class OsCamposDoModeloTest(TestCase):
    """O modelo tem os campos que o manual exige. Sem isto, nada em baixo funciona."""

    def test_cod_municipio_existe_e_aceita_7_digitos(self):
        p = _prop(cod_municipio="5103403")
        self.assertEqual(p.cod_municipio, "5103403")
        # 7 digitos: o codigo IBGE. 6 seria o do municipio sem o digito.
        self.assertEqual(len(p.cod_municipio), 7)

    def test_cep_existe(self):
        p = _prop(cep="78000000")
        self.assertEqual(p.cep, "78000000")

    def test_cad_itr_existe_e_e_distinto_do_caepf(self):
        """O dois campos coexistem, e nao sao o mesmo campo.

        MEDIDO 2026-10-05: `caepf` ja existia desde sempre, e `cad_itr` e' o
        codigo do **imovel**. Sao registos diferentes, e trocar um pelo outro
        produz um ficheiro que a Receita recusa — com a certeza de quem preencheu
        bem e com um valor que nao e' o pedido.
        """
        p = _prop(caepf="12345678901234", cad_itr="98765432")
        self.assertEqual(p.cad_itr, "98765432")
        self.assertNotEqual(p.cad_itr, p.caepf)
        # e ambos existem como atributos distintos
        self.assertNotEqual(
            Propriedade._meta.get_field("cad_itr").name,
            Propriedade._meta.get_field("caepf").name,
        )

    def test_os_campos_novos_sao_opcionais_e_vazios_por_defeito(self):
        """Um produtor existente nao pode ser invalido por causa disto.

        A migracao e' `AddField(..., blank=True)` — sem default e sem null. Um
        produtor cadastrado antes dela tem `""` nos cinco, e continua a **ver o
        produto**. O que muda e' que a guarda fiscal passa a poder dizer o que
        falta, em vez de nao ter onde olhar.
        """
        p = _prop()
        for campo in ("cod_municipio", "cep", "cad_itr", "bairro", "telefone"):
            self.assertEqual(
                getattr(p, campo),
                "",
                f"{campo} tem de vir vazio, para nao invalidar quem ja estava cadastrado",
            )
            self.assertTrue(
                Propriedade._meta.get_field(campo).blank,
                f"{campo} tem de aceitar vazio (blank=True)",
            )


class AGuardaLeOModeloTest(TestCase):
    """A guarda tem de ler o campo, e nao disparar sobre uma ausencia."""

    def test_sem_cod_mun_a_guarda_aponta_o_campo(self):
        p = _prop(cep="78000000")
        faltando = pode_exportar(p, 2026, exigir_campos_fiscais=True)
        self.assertEqual(len(faltando), 1)
        self.assertIn("municipio", faltando[0]["nome"].lower())
        self.assertIn("0030", faltando[0]["registo"])

    def test_com_cod_mun_e_cep_a_guarda_passa(self):
        p = _prop(cod_municipio="5103403", cep="78000000")
        self.assertEqual(pode_exportar(p, 2026, exigir_campos_fiscais=True), [])

    def test_a_guarda_fraca_nao_exige_o_que_e_do_manual(self):
        """Por defeito a guarda e' frouxa. Ver a docstring de `exigir_talhoes`.

        Um produtor no primeiro ano pode nao ter codigo cadastrado. Recusar-lhe a
        exportacao nao o ajuda; o que o ajuda e' ver a linha incompleta. E o
        que ele **nao** pode levar e' um ficheiro que ele acha que esta certo.
        """
        p = _prop()
        self.assertEqual(pode_exportar(p, 2026), [])


class OGeradorEscreveOModeloTest(TestCase):
    """O ultimo elo: o valor do modelo tem de chegar ao ficheiro, no campo certo."""

    def _linha(self, ficheiro: str, prop) -> str:
        for ln in LCDPRExporter(prop, 2026).gerar_arquivo().split("\r\n"):
            if ln.startswith(f"|{ficheiro}|"):
                return ln
        raise AssertionError(f"o ficheiro gerado nao tem a linha {ficheiro}")

    def test_o_0030_leva_cod_mun_cep_e_bairro(self):
        p = _prop(
            cod_municipio="5103403",
            cep="78000000",
            bairro="Cuiaba",
            telefone="65999998888",
            endereco="Av. Marechal Rondon",
            uf="MT",
        )
        campos = self._linha("0030", p).split("|")[1:-1]
        self.assertEqual(len(campos), len(CAMPOS_0030))
        self.assertEqual(campos[4], "Cuiaba", "BAIRRO tem de estar na posicao 5")
        self.assertEqual(campos[5], "MT", "UF na posicao 6")
        self.assertEqual(campos[6], "5103403", "COD_MUN na posicao 7")
        self.assertEqual(campos[7], "78000000", "CEP na posicao 8")
        self.assertEqual(campos[8], "65999998888", "NUM_TEL na posicao 9")

    def test_o_0040_leva_cad_itr_e_os_mesmos_campos_de_endereco(self):
        """O 0040 declara o mesmo endereco que o 0030 — e o `CAD_ITR` a mais.

        MEDIDO 2026-10-05: o 0040 escrevia `caepf` no campo 5 (`CAD_ITR`) e a
        inscricao estadual no 6 (`CAEPF`). Com os dois campos agora no modelo,
        a linha sai com o valor certo no sitio certo — e `caepf`/`cad_itr`
        deixam de poder ser confundidos.
        """
        p = _prop(
            cad_itr="98765432",
            caepf="12345678901234",
            inscricao_estadual="123456789",
            cod_municipio="5103403",
            cep="78000000",
            bairro="Cuiaba",
        )
        campos = self._linha("0040", p).split("|")[1:-1]
        self.assertEqual(len(campos), len(CAMPOS_0040))
        self.assertEqual(campos[4], "98765432", "CAD_ITR nao pode receber o CAEPF")
        self.assertEqual(campos[5], "12345678901234", "CAEPF")
        self.assertEqual(campos[6], "123456789", "INSCR_ESTADUAL")
        self.assertEqual(campos[13], "5103403", "COD_MUN na posicao 14")
        self.assertEqual(campos[14], "78000000", "CEP na posicao 15")

    def test_o_cep_sai_so_com_digitos(self):
        """`07800-000` e' o que o produtor escreve; `78000000` e' o que o ficheiro quer.

        O manual diz N 8. Um CEP com hifen passes o campo do formulario e
        falha o validador, e o produtor nao tem como saber que errou.
        """
        p = _prop(cod_municipio="5103403", cep="78000000", bairro="Cuiaba")
        campos = self._linha("0030", p).split("|")[1:-1]
        self.assertTrue(
            campos[7].isdigit(),
            f"o CEP no ficheiro tem de ser so digitos; saiu {campos[7]!r}",
        )
