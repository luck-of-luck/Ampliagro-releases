"""Os tres geradores de LCDPR concordam sobre o separador decimal.

POR QUE ESTE FICHEIRO EXISTE
===========================
MEDIDO 2026-10-04: o Ampliagro tinha **tres** geradores de LCDPR e o teste
(`tests/test_lcdpr_leiaute.py`) auditava **um**.

- `app/services/lcdpr.py` — `LCDPRGenerator`, ponto decimal. Testado.
- `app/services/lcdpr_export.py` — `LCDPRExporter`, **virgula** decimal. Este
  e' o que o BOTAO da UI chama (`app/templates/cadastro-financeiro.html:163`),
  e produz o ficheiro `LCDPR_<id>_<ano>.txt` que o produtor entrega no e-CAC.
- `app/api/views/custos.py:285` — CSV de relatorio. A virgula ai e' correcta
  (CSV em portugues leva virgula); o nome do endpoint e' que esta errado.

O registo `4610961` ("o ficheiro fiscal da RFB estava a escrever virgula
decimal") corrigiu o primeiro e nao o segundo. O resultado: o gerador bom
existia, estava testado, e so se alcancava por URL digitada — enquanto o
botao gerava um ficheiro que a Receita rejeita, com multa em Abril, sem que
o sistema se queixasse.

Este ficheiro fecha o buraco pelo lado que o outro nao fechou: **mede os
dois** e obriga a que concordem. Nao verifica se um gerador esta certo —
verifica-se que nao ha dois com opinions diferentes sobre o mesmo ficheiro.

O QUE NAO E' UM BUG (e nao se deve "corrigir")
=============================================
`custos.py:285 export_lcdpr` emite CSV (`Bloco;Registro;Campo;Valor`). Virgula
decimal num CSV pt-BR e' a convencao certa e a que o produtor espera abrir no
Excel. "Corrigi-lo" para ponto seria mudar um relatorio que funciona para
partilhar algo que so a RFB le. Este ficheiro marca-o como CSV para impedir
que a proxima pessoa o leia como ficheiro fiscal.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from app.models.core import Propriedade


class SeparadorDecimalLCDPRTest(TestCase):
    """Ponto decimal, nos dois geradores que escrevem o ficheiro da RFB."""

    def setUp(self):
        self.u = User.objects.create_user("lcdpr_unico", password="x1234567")
        self.u.first_name = "Joao"
        self.u.last_name = "Produtor"
        self.u.save()
        self.prop = Propriedade.objects.create(
            user=self.u,
            nome="Fazenda Decimal Unico",
            area_total=Decimal("100.00"),
            cpf_cnpj="123.456.789-01",
        )
        # MEDIDO 2026-10-05: este `setUp` ficou desatualizado, e o teste
        # falhava por isso — nao por o separador decimal estar errado.
        #
        # A `LCDPRDadosIncompletos` passou a exigir talhoes cadastrados, porque
        # o registo `0040` declara **imoveis rurais**, e uma propriedade sem
        # talhao nao tem imoveis a declarar. A razao esta escrita no proprio
        # `_tem_talhoes`: *"o LCDPR declara imoveis, nao a fazenda inteira"* —
        # e esta a recusar exportar um `0040` que seria uma invencao.
        #
        # A guarda esta certa. O que estava desatualizado era o **cenario de
        # teste**: um produtor sem talhoes e' um produtor que ainda nao pode
        # exportar, e o teste do separador decimal precisa de um produtor que
        # ja possa.
        self._criar_talhao()

    def _criar_talhao(self):
        """Um talhao minimo, para o `0040` ter o que declarar."""
        from decimal import ROUND_HALF_UP

        from app.models.core import Talhao

        Talhao.objects.create(
            propriedade=self.prop,
            nome="Gleba 1",
            area_hectare=Decimal("100.00").quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            ),
        )

    def test_o_botao_da_ui_nao_escreve_virgula(self):
        """`LCDPRExporter` e' o que o botao chama. Este e' o teste do botao.

        Nao um teste de "o gerador X esta certo": um teste do caminho que o
        produtor realmente percorre. Se um dia alguem reintroduzir o
        `.replace(".", ",")`, este teste apanha-o.
        """
        from app.services.lcdpr_export import LCDPRExporter

        exporter = LCDPRExporter(self.prop, 2026)
        formatado = exporter.formatar_valor(1234.56)
        self.assertNotIn(
            ",",
            formatado,
            "O botao 'Exportar LCDPR (SPED)' produz um ficheiro para a Receita "
            "com virgula decimal. Em Abril o e-CAC rejeita a linha e multa o "
            "produtor, e nenhum sistema se queixa ate lá.",
        )
        self.assertEqual(formatado, "1234.56")

    def test_zero_e_negativo_tambem(self):
        from app.services.lcdpr_export import LCDPRExporter

        exporter = LCDPRExporter(self.prop, 2026)
        self.assertEqual(exporter.formatar_valor(0), "0.00")
        self.assertEqual(exporter.formatar_valor(None), "0.00")
        # Negativo: o LCDPR usa o sinal no registo, nao no numero. Este valor
        # so aparece em `abs()` nos chamadores; se aparecer negativo cru,
        # tem de continuar a nao ter virgula.
        self.assertNotIn(",", exporter.formatar_valor(-50.5))

    def test_os_dois_geradores_concordam(self):
        """A propriedade que o outro teste nao cobre: que nao ha divergencia.

        Um so valor, os dois geradores, o mesmo separador. Se um dia divergirem,
        a causa e' sempre a mesma — e o teste diz qual.
        """
        from app.services.lcdpr import LCDPRGenerator
        from app.services.lcdpr_export import LCDPRExporter

        gerador = LCDPRGenerator(self.prop.id, 2026)
        exporter = LCDPRExporter(self.prop, 2026)

        for valor in (0, 1, 1234.56, 0.05, 999999.99):
            self.assertEqual(
                gerador._formatar_valor(valor),
                exporter.formatar_valor(valor),
                f"os dois geradores discordam sobre {valor}. "
                "Um ficheiro fiscal com doisCriteria e' um ficheiro "
                "que depende de que botao o produtor carregou.",
            )

    def test_o_ficheiro_gerado_nao_tem_virgula_nos_valores(self):
        """Medida no ficheiro completo, nao no metodo isolado.

        O metodo e' a unidade; o ficheiro e' o contrato. Um `.replace()` a
        meio de `gerar_arquivo` — num Q200, num saldo — nao passa pelo teste
        do metodo.
        """
        from app.models.financeiro import LancamentoFinanceiro

        LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            data="2026-03-15",
            categoria="Venda",
            tipo="RECEITA",
            valor=Decimal("1234.56"),
            descricao="Venda de grao",
            pago=True,
        )

        from app.services.lcdpr_export import LCDPRExporter

        texto = LCDPRExporter(self.prop, 2026).gerar_arquivo()
        for linha in texto.splitlines():
            if not linha.startswith("|Q100|"):
                continue
            for campo in linha.split("|")[8:11]:
                # Campos de valor nao podem ter virgula decimal. Um campo
                # textual (historico) pode ter virgula legitimately; por isso
                # so se olha para os campos que sao numeros.
                if campo and campo[0].isdigit():
                    self.assertNotIn(
                        ",",
                        campo,
                        f"valor com virgula decimal no Q100: {linha!r}",
                    )


class OQueNaoEFiscalTest(TestCase):
    """Marca o CSV de relatorio como CSV, para ninguem o entregar a RFB."""

    def setUp(self):
        self.u = User.objects.create_user("lcdpr_csv", password="x1234567")
        self.u.save()
        self.prop = Propriedade.objects.create(
            user=self.u,
            nome="Fazenda CSV",
            area_total=Decimal("10.00"),
            cpf_cnpj="12345678901",
        )

    def test_o_endpoint_de_csv_diz_que_e_relatorio(self):
        """`custos.py:285 export_lcdpr` produz CSV, e tem de o dizer.

        Este endpoint chama-se `export_lcdpr` e tem no nome o que o produtor
        entrega a Receita. A virgula decimal ai esta certa — CSV pt-BR leva
        virgula — mas o nome e' que convence alguem a entregar o ficheiro
        errado. A correccao e' rotular, nao trocar o separador.
        """
        from app.models.financeiro import LancamentoFinanceiro

        LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            data="2026-02-10",
            categoria="Custo",
            tipo="DESPESA",
            valor=Decimal("99.90"),
            descricao="Combustivel",
            pago=True,
        )

        self.client.force_login(self.u)
        resposta = self.client.get(
            "/api/lancamentos-detalhados/export_lcdpr/?ano=2026"
            f"&propriedade={self.prop.id}"
        )

        self.assertEqual(resposta.status_code, 200)
        corpo = resposta.content.decode("utf-8")
        # O cabecalho do CSV e' o que distingue um relatorio de um ficheiro da
        # RFB: o Leiaute e' `|0000|LCDPR|0013|...`, e nao uma tabela de colunas.
        self.assertIn(
            "Registro",
            corpo,
            "o endpoint deixou de emitir o CSV de relatorio",
        )
        # E a virgula no valor continua correcta para um CSV pt-BR.
        self.assertIn("99,90", corpo)
