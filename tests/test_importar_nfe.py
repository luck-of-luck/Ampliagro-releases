"""Uma NF-e importada duas vezes nao duplica o estoque. E uma nota e' uma despesa.

POR QUE ESTE FICHEIRO EXISTE
===========================
MEDIDO 2026-10-05 (agente 7). O import de NF-e existia (`app/views/nfe_auto.py`)
e funcionava, mas tinha tres defeitos que sao todos a mesma coisa: **o sistema
afirmava um `ok: true` que nao correspondia ao que tinha gravado.**

1. REENVIO DUPLICAVA TUDO
   Nao havia nada que identificasse a nota. `EstoqueItem.local` era
   `f"NF-e {emissao:%d/%m/%Y}"` — a data, que nao distingue duas notas do
   mesmo dia, quanto mais a mesma nota duas vezes. O mesmo XML carregado duas
   vezes criava dois `EstoqueItem` e dois `LancamentoFinanceiro`, e as duas
   respostas eram `{"ok": true, ...}`.

2. UMA NOTA, VARIOS LANCAMENTOS
   O `LancamentoFinanceiro.objects.create(...)` estava **dentro** do
   `for det in itens[:20]`. Uma NF-e de 12 itens virava 12 despesas de "NF-e
   <produto>". O produtor via doze compras onde houve uma.

3. DINHEIRO EM `float`
   `float(str(qCom).replace(",", "."))` e `valor=preco * qtd`. Este
   repositorio ja corrigiu a virgula decimal do LCDPR; o caminho de entrada
   da NF-e mantinha `float`.

A CHAVE DE ACESSO
=================
A identidade de uma NF-e sao os **44 digitos da chave de acesso**, emitidos
pela SEFAZ e unicos por documento. E' o que `NotaFiscalImportada` guarda, com
`unique` por propriedade.

E porque e' que o `ler_nota` **recusa** um XML sem chave de 44 digitos em vez
de o aceitar: sem chave nao ha deduplicacao, e aceitar seria devolver
`ok: true` a um ficheiro que nao da para controlar. Um erro recusado e' melhor
do que um duplicado silencioso.

O QUE ESTE FICHEIRO NAO PROVA
=============================
Que o canal automatico da SEFAZ existe. Nao existe — `ClienteDFe` levanta
`NotImplementedError` com a lista do que falta, e ha' um teste a garantir
que levanta. Um stub que devolvesse notas inventadas seria o defeito que o
`erp_externo.py` foi corrigido por ter.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from app.models import (
    EstoqueItem,
    LancamentoFinanceiro,
    NotaFiscalImportada,
    Propriedade,
)

CHAVE = "35240612345678000199550010000000011000000017"

# Uma NF-e com DOIS itens: 10 x 100,00 + 5 x 20,00 = 1.100,00.
#
# Os valores estao em formato brasileiro (`1.000,00`) de proposito: e' assim
# que vem num XML exportado por muitos ERPs, e `1.000,00` lido como `1.000`
# daria um numero plausivel e errado. O mesmo se passa no item — `qCom=10,0000`
# lido como float sem tratar a virgula daria 10.0 num sitio e 10 noutro,
# conforme a libraria.
NF_E = """<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
<nfe><infNFe>
<ide><cNF>1</cNF><natOp>VENDA</natOp><mod>55</mod><serie>1</serie>
<nNF>123</nNF><dEmi>20260315</dEmi>
<chNFe>{chave}</chNFe></ide>
<emit><CNPJ>12345678000199</CNPJ><xNome>FORNECEDOR DE INSUMOS LTDA</xNome></emit>
<det><prod><cProd>1</cProd><xProd>FERTILIZANTE 20-05-20</xProd>
<qCom>10,0000</qCom><vUnCom>100,0000</vUnCom></prod></det>
<det><prod><cProd>2</cProd><xProd>HERBICIDA</xProd>
<qCom>5,0000</qCom><vUnCom>20,0000</vUnCom></prod></det>
<total><ICMSTot><vNF>1.100,00</vNF></ICMSTot></total>
</infNFe></nfe></nfeProc>"""


def _nf_e(chave=CHAVE):
    return NF_E.format(chave=chave).encode("utf-8")


class ImportarNFeTest(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("comprador", password="x1234567")
        self.prop = Propriedade.objects.create(
            user=self.u, nome="Fazenda Compras", area_total=100, cpf_cnpj="12345678901"
        )
        from app.services.nfe import importar_xml

        self.importar = importar_xml

    def test_uma_nota_e_um_lancamento_nao_um_por_item(self):
        """O defeito central: o `create()` estava dentro do `for` dos itens."""
        r = self.importar(self.prop, _nf_e())

        self.assertTrue(r["ok"], r.get("erro"))
        lancamentos = LancamentoFinanceiro.objects.filter(propriedade=self.prop)
        self.assertEqual(
            lancamentos.count(),
            1,
            "uma NF-e de 2 itens gerou mais do que um lancamento. O produtor "
            "via duas despesas onde houve uma compra.",
        )
        self.assertEqual(lancamentos.first().valor, Decimal("1100.00"))
        self.assertEqual(EstoqueItem.objects.filter(propriedade=self.prop).count(), 2)

    def test_o_valor_e_decimal_e_nao_float(self):
        """`1.000,00` em `qCom`/`vUnCom` tem de dar 1000, nao 1.0."""
        r = self.importar(self.prop, _nf_e())

        self.assertTrue(r["ok"], r.get("erro"))
        item = EstoqueItem.objects.filter(
            propriedade=self.prop, nome__icontains="FERTILIZANTE"
        ).first()
        self.assertEqual(item.quantidade, Decimal("10"))
        self.assertEqual(item.valor_unitario, Decimal("100.00"))
        self.assertEqual(
            item.quantidade * item.valor_unitario,
            Decimal("1000.00"),
        )

    def test_reenviar_a_mesma_nota_nao_duplica_nada(self):
        """A pergunta que o `ok: true` antigo nao respondia."""
        primeira = self.importar(self.prop, _nf_e())
        self.assertTrue(primeira["ok"])
        self.assertFalse(primeira["duplicado"])

        antes = {
            "lancamentos": LancamentoFinanceiro.objects.filter(
                propriedade=self.prop
            ).count(),
            "itens": EstoqueItem.objects.filter(propriedade=self.prop).count(),
        }

        segunda = self.importar(self.prop, _nf_e())

        self.assertTrue(segunda["ok"])
        self.assertTrue(
            segunda["duplicado"],
            "a segunda importacao da mesma chave disse que nao era duplicada. "
            "O estoque vai duplicar em silencio.",
        )
        self.assertEqual(
            LancamentoFinanceiro.objects.filter(propriedade=self.prop).count(),
            antes["lancamentos"],
            "o reenvio duplicou o lancamento financeiro",
        )
        self.assertEqual(
            EstoqueItem.objects.filter(propriedade=self.prop).count(),
            antes["itens"],
            "o reenvio duplicou o estoque",
        )

    def test_a_chave_fica_registrada(self):
        self.importar(self.prop, _nf_e())

        registro = NotaFiscalImportada.objects.get(propriedade=self.prop)
        self.assertEqual(registro.chave, CHAVE)
        self.assertEqual(registro.numero, "123")
        self.assertEqual(registro.total, Decimal("1100.00"))
        self.assertEqual(registro.itens, 2)
        self.assertIn("FORNECEDOR", registro.fornecedor_nome)

    def test_a_mesma_chave_em_outra_propriedade_e_outra_nota(self):
        """A chave e' unica por documento, nao por sistema."""
        outro_user = User.objects.create_user("outro", password="x1234567")
        outro = Propriedade.objects.create(
            user=outro_user, nome="Outra", area_total=10, cpf_cnpj="98765432100"
        )

        self.assertTrue(self.importar(self.prop, _nf_e())["ok"])
        r = self.importar(outro, _nf_e())

        self.assertTrue(r["ok"])
        self.assertFalse(
            r["duplicado"],
            "duas propriedades diferentes com a mesma nota: a segunda foi "
            "declarada duplicada. A constraint e' por propriedade.",
        )

    def test_sem_chave_de_44_digitos_e_recusado(self):
        """Sem chave nao ha deduplicacao, entao nao se aceita.

        A alternativa — aceitar e escrever `ok: true` — devolve um duplicado
        silencioso. Uma recusa diz ao produtor o que fazer.
        """
        r = self.importar(self.prop, _nf_e(chave="123"))

        self.assertFalse(r["ok"])
        self.assertIn("44", r["erro"])
        self.assertEqual(LancamentoFinanceiro.objects.count(), 0)

    def test_xml_nao_e_nfe(self):
        r = self.importar(self.prop, b"<html><body>pagina do banco</body></html>")
        self.assertFalse(r["ok"])
        self.assertEqual(LancamentoFinanceiro.objects.count(), 0)

    def test_xml_malformado(self):
        r = self.importar(self.prop, b"<nfe><infNFe>")
        self.assertFalse(r["ok"])
        self.assertEqual(LancamentoFinanceiro.objects.count(), 0)


class ClienteDFeNaoMenteTest(TestCase):
    """O canal automatico nao existe. E tem de dizer isso, nao inventar notas.

    Um stub que devolvesse notas plausiveis sem consultar a SEFAZ seria o
    mesmo defeito que `erp_externo.webhook_jbs_abate` tinha: `cabecas=10721000`
    copiado de um artigo, com `"status": "Feito"`. Uma excecao honesta agora
    vale mais do que um numero falso depois.
    """

    def test_buscar_documentos_levanta_com_a_lista_do_que_falta(self):
        from app.services.nfe import ClienteDFe

        cliente = ClienteDFe(uf="MT", cnpj="12345678000199")

        with self.assertRaises(NotImplementedError) as ctx:
            cliente.buscar_documentos("20260101", "20260131")

        mensagem = str(ctx.exception)
        self.assertIn("certificado", mensagem.lower())
        self.assertIn("nao implementada", mensagem.lower())
        # E diz onde está o caminho que funciona hoje, para o produtor nao
        # ficar a pensar que o sistema esta partido.
        self.assertIn("/api/nfe/import/", mensagem)
