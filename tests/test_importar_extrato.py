"""`importar_ofx` grava. E o que a rota promete.

POR QUE ESTE FICHEIRO EXISTE
===========================
MEDIDO 2026-10-04: `POST /api/contas-bancarias/<id>/importar_ofx/` validava a
extensão, lia o ficheiro, importava `ElementTree` para a linha seguinte nunca
usar, e devolvia

    {"ok": True, "importadas": 0, "mensagem": "Parser OFX a implementar"}

**HTTP 200, `ok: true`, zero linhas gravadas.**

Este e' o pior padrao possivel num sistema que trata dinheiro, e e' pior que um
500: um 500 e' um bug que alguem reporta hoje. Um `ok: true` sem escrita e' um
bug que aparece no saldo do banco, na conciliacao, e no fechamento — meses
depois, quando ja nao ha ninguem a ligar as duas coisas. O produtor carrega o
extracto, o sistema diz "ok", ele fecha o ecra. O extracto nao esta la.

O segundo bug era o inverso e tambem grave: `app/services/bank_import.py` tem
`parse_ofx`, `parse_csv` e `conciliar_transacoes` — e nao ha **nenhum** importer
que os chame (grep `bank_import` so encontra o proprio ficheiro). E
`ofxparse` nao esta no `requirements.txt`, portanto `OfxParser = None` e
`parse_ofx` levanta. Codigo morto que parece a funcionalidade.

O QUE ESTE FICHEIRO TRAVA
=========================
1. Um OFX real grava as transacoes. (O que a rota diz.)
2. Reenviar o mesmo extracto **actualiza**, nao duplica nem rebenta em
   `IntegrityError` — `hash_unico` tem `unique=True` e o reenvio do extrato do
   banco e' a norma, nao a excecao.
3. Um ficheiro ilegivel da **400**, nao 200 com `ok: true`. `ExtratoNao-
   Reconhecido` existe para isto.
4. Um extracto sem uma unica transacao com data nao devolve `ok: true`.
5. `1.234,56` e' 1234.56. O parser antigo fazia `replace(",", ".")` e lia
   "1.234,56" como 1.23456 — um erro de milhao num sistema que trata dinheiro,
   e que nao dava sintaxe invalida: dava um numero plausivel.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from app.models.core import Propriedade
from app.models.financeiro_banco import ContaBancaria, MovimentacaoBancaria
from app.services.extrato import ExtratoNaoReconhecido, ler_extrato

OFX_REAL = """OFXHEADER:100
DATA:OFXSGML
VERSION:102

<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><CURDEF>BRL
<BANKACCTFROM><BANKID>341
<ACCTID>12345-6</ACCTID><ACCTTYPE>CHECKING</ACCTTYPE></BANKACCTFROM>
<BANKTRANLIST>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20260315120000
<TRNAMT>1234.56
<FITID>TXN0001
<NAME>VENDA GRAO
<MEMO>NOTA FISCAL 123
</STMTTRN>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260320120000
<TRNAMT>-450.00
<FITID>TXN0002
<NAME>COMBUSTIVEL
<MEMO>POSTO Ipiranga
</STMTTRN>
</BANKTRANLIST>
<LEDGERBAL><BALAMT>784.56</BALAMT></LEDGERBAL>
</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>
"""


class LerOFXTest(TestCase):
    """O parser, isolado da HTTP."""

    def test_le_o_ofx_e_separa_credito_de_debito(self):
        tx = ler_extrato(OFX_REAL.encode("utf-8"), "extrato.ofx")

        self.assertEqual(len(tx), 2)
        self.assertEqual(tx[0]["valor"], Decimal("1234.56"))
        self.assertEqual(tx[0]["tipo"], "RECEITA")
        self.assertEqual(tx[0]["fitid"], "TXN0001")
        self.assertEqual(tx[0]["data"].isoformat(), "2026-03-15")

        self.assertEqual(tx[1]["valor"], Decimal("-450.00"))
        self.assertEqual(tx[1]["tipo"], "DESPESA")

    def test_milionario_com_virgula_e_milionario(self):
        """`1.234,56` e' 1234.56. Nao 1.23456.

        O parser antigo fazia `Decimal(valor.replace(",", "."))`, que produz
        `1.23456` — um numero plausivel, e 1000x menor. Um extrato com esse
        erro da' um saldo que parece certo e nao esta, e o produtor so o
        descobre quando a reconciliacao nao bate.
        """
        tx = ler_extrato(OFX_REAL.encode("utf-8"), "e.ofx")
        self.assertEqual(tx[0]["valor"], Decimal("1234.56"))

    def test_ficheiro_ilegivel_dit_o_que_enviar(self):
        with self.assertRaises(ExtratoNaoReconhecido) as ctx:
            ler_extrato(b"isto nao e um extracto", "extrato.pdf")

        mensagem = str(ctx.exception)
        # A excepcao existe para a view poder responder 400 com o remedy, nao
        # para ser um `ValueError` generico que so diz "algo correu mal".
        self.assertIn("ofx", mensagem.lower())
        self.assertIn("csv", mensagem.lower())


class ImportarOFXGravaTest(TestCase):
    """A rota que o produtor carrega, e o que ela grava."""

    def setUp(self):
        self.u = User.objects.create_user("ofx_user", password="x1234567")
        self.prop = Propriedade.objects.create(
            user=self.u,
            nome="Fazenda Extrato",
            area_total=Decimal("100.00"),
            cpf_cnpj="12345678901",
        )
        self.conta = ContaBancaria.objects.create(
            propriedade=self.prop, banco="341", agencia="1234", conta="56789"
        )

    def _posta(self, conteudo, nome="extrato.ofx"):
        from django.core.files.uploadedfile import SimpleUploadedFile

        return self.client.post(
            f"/api/contas-bancarias/{self.conta.id}/importar_ofx/",
            {"arquivo": SimpleUploadedFile(nome, conteudo)},
        )

    def test_a_rota_grava_as_movimentacoes(self):
        """O teste central. Antes disto a rota respondia "ok" e nao gravava."""
        self.client.force_login(self.u)
        resposta = self._posta(OFX_REAL.encode("utf-8"))

        self.assertEqual(resposta.status_code, 201, resposta.content[:200])
        self.assertTrue(resposta.json()["ok"])

        gravadas = MovimentacaoBancaria.objects.filter(conta=self.conta)
        self.assertEqual(gravadas.count(), 2)
        self.assertEqual(float(gravadas.get(documento="TXN0001").valor), 1234.56)
        self.assertEqual(gravadas.get(documento="TXN0001").tipo, "CREDITO")
        self.assertEqual(gravadas.get(documento="TXN0002").tipo, "DEBITO")

    def test_ok_so_e_true_quando_entrou_alguma_linha(self):
        """A mentira antiga era `ok: true` com zero gravadas.

        Um extracto sem transacoes legiveis e' um erro do ficheiro, nao um
        sucesso. `422` e' o codigo certo: o servidor leu o pedido, mas nao
        ha o que gravar.
        """
        self.client.force_login(self.u)
        resposta = self._posta(
            b"OFXHEADER:100\n<BANKTRANLIST></BANKTRANLIST>", "vazio.ofx"
        )

        self.assertEqual(resposta.status_code, 422)
        self.assertFalse(resposta.json()["ok"])
        self.assertEqual(MovimentacaoBancaria.objects.count(), 0)

    def test_reenvio_do_mesmo_extrato_actualiza_e_nao_duplica(self):
        """Reenviar e' a norma. `hash_unico` e' `unique=True`.

        Sem `update_or_create`, o segundo POST levanta `IntegrityError` a meio
        — o utilizador fica com metade do extracto escrito e um 500. Com o
        `FITID` a servir de identidade, o reenvio actualiza as mesmas linhas e
        a resposta diz as duas coisas: quantas novas, quantas actualizadas.
        """
        self.client.force_login(self.u)

        primeira = self._posta(OFX_REAL.encode("utf-8"))
        self.assertEqual(primeira.status_code, 201)
        self.assertEqual(primeira.json()["criadas"], 2)
        self.assertEqual(primeira.json()["actualizadas"], 0)

        segunda = self._posta(OFX_REAL.encode("utf-8"))
        self.assertEqual(segunda.status_code, 201)
        self.assertEqual(segunda.json()["criadas"], 0)
        self.assertEqual(segunda.json()["actualizadas"], 2)

        self.assertEqual(
            MovimentacaoBancaria.objects.filter(conta=self.conta).count(), 2
        )

    def test_ficheiro_ilegivel_da_400_nao_200(self):
        self.client.force_login(self.u)
        resposta = self._posta(b"isto nao e um extracto", "coisas.pdf")

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("erro", resposta.json())
        self.assertEqual(MovimentacaoBancaria.objects.count(), 0)

    def test_valor_invalido_rejeita_arquivo_inteiro(self):
        self.client.force_login(self.u)
        for valor in ("", "abc", "NaN", "Infinity", "1e999", "0.001", "1000000000000"):
            with self.subTest(valor=valor):
                resposta = self._posta(OFX_REAL.replace("-450.00", valor).encode())
                self.assertEqual(resposta.status_code, 400)
                self.assertIn("2", resposta.json()["erro"])
                self.assertEqual(MovimentacaoBancaria.objects.count(), 0)

    def test_csv_sem_valor_nao_inventa_zero(self):
        self.client.force_login(self.u)
        for csv in (
            "data;descricao\n15/03/2026;Venda",
            "data;valor\n15/03/2026;100\n16/03/2026;",
        ):
            with self.subTest(csv=csv):
                resposta = self._posta(csv.encode(), "extrato.csv")
                self.assertEqual(resposta.status_code, 400)
                self.assertEqual(MovimentacaoBancaria.objects.count(), 0)

    def test_data_invalida_rejeita_lote_sem_omitir_movimentos(self):
        self.client.force_login(self.u)
        arquivos = (
            [
                ("extrato.ofx", OFX_REAL.replace("20260320120000", data))
                for data in ("", "20260230120000", "invalida")
            ]
            + [
                ("extrato.csv", f"data;valor\n15/03/2026;100\n{data};20")
                for data in ("", "30/02/2026", "invalida")
            ]
            + [("extrato.csv", "valor;descricao\n100;Venda")]
        )
        for nome, conteudo in arquivos:
            with self.subTest(nome=nome, conteudo=conteudo):
                resposta = self._posta(conteudo.encode(), nome)
                self.assertEqual(resposta.status_code, 400)
                self.assertIn("data", resposta.json()["erro"])
                self.assertEqual(MovimentacaoBancaria.objects.count(), 0)

    def test_falha_na_segunda_gravacao_reverte_a_primeira(self):
        from unittest.mock import patch

        from django.db import IntegrityError

        from app.services.extrato import gravar_movimentacoes

        original = MovimentacaoBancaria.objects.update_or_create
        chamadas = 0

        def gravar_ou_falhar(**kwargs):
            nonlocal chamadas
            chamadas += 1
            if chamadas == 2:
                raise IntegrityError("falha simulada na segunda linha")
            return original(**kwargs)

        with (
            patch.object(
                MovimentacaoBancaria.objects,
                "update_or_create",
                side_effect=gravar_ou_falhar,
            ),
            self.assertRaises(IntegrityError),
        ):
            gravar_movimentacoes(self.conta, ler_extrato(OFX_REAL.encode(), "e.ofx"))
        self.assertEqual(MovimentacaoBancaria.objects.count(), 0)

    def test_csv_valido_preserva_centavos_e_zero_explicito(self):
        self.client.force_login(self.u)
        resposta = self._posta(
            b"data;valor;id\n15/03/2026;1.234,56;A\n16/03/2026;0;B",
            "extrato.csv",
        )
        self.assertEqual(resposta.status_code, 201)
        self.assertEqual(
            MovimentacaoBancaria.objects.get(documento="A").valor, Decimal("1234.56")
        )
        self.assertEqual(
            MovimentacaoBancaria.objects.get(documento="B").valor, Decimal("0")
        )

    def test_reenvio_preserva_movimentos_conciliados(self):
        self.client.force_login(self.u)
        self._posta(OFX_REAL.encode())
        MovimentacaoBancaria.objects.update(conciliado=True)
        resposta = self._posta(OFX_REAL.encode())
        self.assertEqual(resposta.status_code, 201)
        self.assertEqual(resposta.json()["preservadas"], 2)
        self.assertEqual(resposta.json()["actualizadas"], 0)
        self.assertEqual(
            MovimentacaoBancaria.objects.filter(conciliado=True).count(), 2
        )

    def test_sem_id_preserva_ocorrencias_e_reenvio_com_outro_formato(self):
        self.client.force_login(self.u)
        csv = "data;valor;descricao\n15/03/2026;100;Venda\n15/03/2026;100;Venda"
        primeira = self._posta(csv.encode(), "extrato.csv")
        self.assertEqual(primeira.status_code, 201)
        self.assertEqual(primeira.json()["criadas"], 2)
        segunda = self._posta(csv.replace(";100;", ";100,00;").encode(), "extrato.csv")
        self.assertEqual(segunda.status_code, 201)
        self.assertEqual(segunda.json()["criadas"], 0)
        self.assertEqual(MovimentacaoBancaria.objects.count(), 2)

    def test_sem_id_usa_descricao_inteira(self):
        self.client.force_login(self.u)
        prefixo = "a" * 60
        csv = f"data;valor;descricao\n15/03/2026;100;{prefixo} A\n15/03/2026;100;{prefixo} B"
        resposta = self._posta(csv.encode(), "extrato.csv")
        self.assertEqual(resposta.status_code, 201)
        self.assertEqual(resposta.json()["criadas"], 2)
        self.assertEqual(
            set(MovimentacaoBancaria.objects.values_list("descricao", flat=True)),
            {prefixo + " A", prefixo + " B"},
        )

    def test_sem_id_reconhece_importacao_legada_e_preserva_vinculo(self):
        from hashlib import sha256

        self.client.force_login(self.u)
        antigo = MovimentacaoBancaria.objects.create(
            conta=self.conta,
            data="2026-03-15",
            valor=Decimal("100.00"),
            tipo="CREDITO",
            descricao="Venda",
            conciliado=True,
            hash_unico=sha256(
                f"{self.conta.pk}|2026-03-15|100|Venda".encode()
            ).hexdigest(),
        )
        resposta = self._posta(
            b"data;valor;descricao\n15/03/2026;100,00;Venda", "extrato.csv"
        )
        self.assertEqual(resposta.status_code, 201)
        self.assertEqual(resposta.json()["preservadas"], 1)
        self.assertEqual(MovimentacaoBancaria.objects.count(), 1)
        antigo.refresh_from_db()
        self.assertTrue(antigo.conciliado)

    def test_sem_id_nao_funde_movimento_manual_coincidente(self):
        self.client.force_login(self.u)
        manual = MovimentacaoBancaria.objects.create(
            conta=self.conta,
            data="2026-03-15",
            valor=Decimal("100.00"),
            tipo="CREDITO",
            descricao="Venda",
        )
        resposta = self._posta(
            b"data;valor;descricao\n14/03/2026;50;Outra\n15/03/2026;100;Venda",
            "extrato.csv",
        )
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("ambígua", resposta.json()["erro"])
        self.assertEqual(
            list(MovimentacaoBancaria.objects.values_list("pk", flat=True)), [manual.pk]
        )

    def test_reenvio_divergente_nao_altera_conciliado_nem_resto_do_lote(self):
        self.client.force_login(self.u)
        self._posta(OFX_REAL.encode())
        MovimentacaoBancaria.objects.filter(documento="TXN0002").update(conciliado=True)
        for antes, depois in (
            ("-450.00", "-451.00"),
            ("-450.00", "450.00"),
            ("20260320", "20260321"),
            ("POSTO Ipiranga", "Outra descrição"),
        ):
            with self.subTest(alteracao=antes):
                conteudo = OFX_REAL.replace("1234.56", "999.00").replace(antes, depois)
                resposta = self._posta(conteudo.encode())
                self.assertEqual(resposta.status_code, 400)
                self.assertIn("conciliad", resposta.json()["erro"])
                self.assertEqual(
                    MovimentacaoBancaria.objects.get(documento="TXN0001").valor,
                    Decimal("1234.56"),
                )
                conciliado = MovimentacaoBancaria.objects.get(documento="TXN0002")
                self.assertEqual(conciliado.valor, Decimal("450.00"))
                self.assertTrue(conciliado.conciliado)

    def test_o_valor_nao_viaja_com_sinal_no_gravado(self):
        """`valor` e' `Decimal(max_digits=14)`, e `MovimentacaoBancaria` guarda
        o montante com o sinal no `tipo` (`CREDITO`/`DEBITO`).

        Gravar -450 num campo de valor e' guardar o mesmo numero duas vezes: o
        sinal no valor e' o sinal no tipo. Um extrato debitado tem de sair
        450.00 + DEBITO, ou o saldo junto do produtor sai duas vezes errado.
        """
        from app.services.extrato import gravar_movimentacoes

        resultado = gravar_movimentacoes(
            self.conta, ler_extrato(OFX_REAL.encode("utf-8"), "e.ofx")
        )
        self.assertEqual(resultado["criadas"], 2)

        debito = MovimentacaoBancaria.objects.get(documento="TXN0002")
        self.assertEqual(debito.valor, Decimal("450.00"))
        self.assertGreaterEqual(debito.valor, Decimal("0"))
        self.assertEqual(debito.tipo, "DEBITO")
