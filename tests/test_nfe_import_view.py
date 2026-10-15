"""A view da NF-e usa o motor partilhado, e o HTTP diz a verdade.

POR QUE ESTE FICHEIRO EXISTE
===========================
MEDIDO 2026-10-05 (agente 7). `tests/test_importar_nfe.py` prova que o
**serviço** e' correcto. Este prova que a **view** o usa e traduz o resultado
para HTTP sem o alterar.

Uma view que reimplementa o parser tem dois motores — e o segundo envelhece
sozinho. Foi exactamente o que aconteceu: a view tinha a sua copia do parser,
que foi corrigida a `defusedxml` e a FKs mas **nao** a chave de acesso nem a
contagem de lancamentos, porque o modelo `NotaFiscalImportada` nao existia.
Se o servico Ganhar uma regra e a view nao, o produtor recebe respostas
diferentes conforme o caminho.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

# `tests/` nao e' um pacote (nao tem `__init__.py`), e o pytest importa os
# ficheiros de teste por basename. Importar `test_importar_nfe` funciona
# porque `tests/` esta no `sys.path` durante a coleta; importar
# `tests.test_importar_nfe` **nao** — e' por isso que este comentario existe,
# para a proxima pessoa nao perder dez minutos a adivinhar o caminho.
from test_importar_nfe import CHAVE, NF_E

from app.models import LancamentoFinanceiro, NotaFiscalImportada, Propriedade


class ViewImportarNFeTest(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("vendedor", password="x1234567")
        self.prop = Propriedade.objects.create(
            user=self.u, nome="Fazenda", area_total=100, cpf_cnpj="12345678901"
        )
        self.url = reverse("nfe-import")

    def _xml(self, chave=CHAVE):
        from django.core.files.uploadedfile import SimpleUploadedFile

        return SimpleUploadedFile(
            "nota.xml",
            NF_E.format(chave=chave).encode("utf-8"),
            content_type="application/xml",
        )

    def test_a_primeira_importacao_responde_201(self):
        self.client.force_login(self.u)

        r = self.client.post(self.url, {"xml": self._xml()})

        self.assertEqual(r.status_code, 201, r.content[:200])
        self.assertTrue(r.json()["ok"])
        self.assertEqual(r.json()["lancamentos"], 1)
        self.assertEqual(LancamentoFinanceiro.objects.count(), 1)
        self.assertEqual(NotaFiscalImportada.objects.count(), 1)

    def test_o_reenvio_responde_200_e_nao_grava(self):
        """O `ok: true` antigo nas duas vezes e' o que este teste proibe.

        200 e' o codigo certo para "o pedido foi cumprido, a nota ja estava
        la" — e o corpo diz `duplicado: true`. Um 201 seria mentira (nao foi
        criado nada) e um 400 seria errado (o ficheiro e' valido).
        """
        self.client.force_login(self.u)
        self.client.post(self.url, {"xml": self._xml()})

        r = self.client.post(self.url, {"xml": self._xml()})

        self.assertEqual(r.status_code, 200, r.content[:200])
        self.assertTrue(r.json()["duplicado"])
        self.assertEqual(LancamentoFinanceiro.objects.count(), 1)

    def test_xml_invalido_responde_400_com_motivo(self):
        """400, nao 500.

        Um 500 diz ao produtor que o Ampliagro esta partido, e nao e' verdade:
        o ficheiro e' que nao presta.
        """
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.force_login(self.u)
        r = self.client.post(
            self.url,
            {"xml": SimpleUploadedFile("x.xml", b"<nfe><infNFe>")},
        )

        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json()["ok"])
        self.assertIn("erro", r.json())

    def test_sem_ficheiro_responde_400(self):
        self.client.force_login(self.u)
        r = self.client.post(self.url, {})

        self.assertEqual(r.status_code, 400)

    def test_sem_sessao_responde_302_para_login(self):
        """`login_required` no decorator.

        Um `fetch` segue o 302 e recebe HTML com 200 — o `sync.js` marcaria a
        nota como sincronizada sem ela terIDO importada. E' o mesmo buraco que
        o `exigir_sessao_json` do Caderno desfez.
        """
        r = self.client.post(self.url, {"xml": self._xml()})

        self.assertEqual(r.status_code, 302)
        self.assertEqual(LancamentoFinanceiro.objects.count(), 0)

    def test_um_xml_grande_demais_responde_413(self):
        """O teto e' lido **antes** de gastar memoria com o ficheiro."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.force_login(self.u)
        grande = SimpleUploadedFile("grande.xml", b"x" * (6 * 1024 * 1024))
        r = self.client.post(self.url, {"xml": grande})

        self.assertEqual(r.status_code, 413)
        self.assertEqual(LancamentoFinanceiro.objects.count(), 0)
