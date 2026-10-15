"""O XML da NF-e é input de utilizador. O parser tem de ser `defusedxml`.

## O que o semgrep apanhou

`python.lang.security.use-defused-xml-parse` (CWE-611, OWASP A04:2017 /
A05:2021) em `nfe_auto.py:72`: `ET.parse(xml_file)`, com
`import xml.etree.ElementTree as ET`.

**É o meu próprio código.** O `ET.parse` estava lá antes de eu tocar na view,
mas eu reescrevi o corpo em volta dele e não vi a that. Scanner não
distingue quem escreveu a linha — e não deve.

## Por que aqui é um risco real, e não teórico

O ficheiro XML vem de `request.FILES["xml"]` — um upload de um produtor, ou
de quem lhe mandar a nota. Um XML com `<!DOCTYPE foo [<!ENTITY x SYSTEM
"file:///etc/passwd">]>` faz o parser nativo resolver a entidade. Um
"billion laughs" (entidades aninhadas) estoura a memória.

`defusedxml.ElementTree.fromstring` recusa ambos. O input é não confiável por
definição — é um ficheiro que veio de fora — e a correcção custa uma linha.
"""

from __future__ import annotations

import json
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from app.models import Propriedade


class NfeXxeTest(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("prod", password="x")
        Propriedade.objects.create(
            user=self.u,
            nome="Fazenda",
            area_total=Decimal("100.00"),
            uf="MT",
            cidade="Sorriso",
        )
        self.url = "/api/nfe/import/"
        self.client.force_login(self.u)

    def _post(self, xml: str):
        return self.client.post(
            self.url, {"xml": SimpleUploadedFile("nfe.xml", xml.encode("utf-8"))}
        )

    def test_xml_com_entidade_externa_nao_e_resolvido(self):
        """Um XML com entidade externa não pode ser expandido.

        Se o parser nativo fosse usado, isto leria um ficheiro do servidor e
        devolveria o conteúdo num lançamento. O teste verifica as duas coisas:
        não cria lançamento, e não devolve 500 com o conteúdo.
        """
        xml = """<?xml version="1.0"?>
<!DOCTYPE nfeProc [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
  <NFe><infNFe>
    <ide><dhEmi>2026-03-10T10:00:00-03:00</dhEmi></ide>
    <det><prod><xProd>&xxe;</xProd><CFOP>1102</CFOP><qCom>1</qCom>
      <uCom>UN</uCom><vUnCom>1.00</vUnCom><vProd>1.00</vProd></prod></det>
  </infNFe></NFe>
</nfeProc>"""

        r = self._post(xml)

        from app.models import LancamentoFinanceiro

        self.assertFalse(
            LancamentoFinanceiro.objects.exists(),
            "XML com entidade externa gerou lancamento — XXE aceite",
        )
        corpo = r.content.decode("utf-8", "replace")
        self.assertNotIn("root:", corpo, "conteudo de ficheiro exposto na resposta")

    def test_view_nao_importa_elementtree_nativo(self):
        """O import nativo não pode voltar.

        Um teste sobre o código-fonte, não sobre o comportamento: é o que
        apanha o `ET.parse` a ser reintroduzido ao lado do `defusedxml`.
        """
        import inspect

        from app.views import nfe_auto

        fonte = inspect.getsource(nfe_auto)
        self.assertNotIn(
            "import xml.etree.ElementTree as ET",
            fonte,
            "o parser nativo voltou; o input de NF-e nao e confiavel",
        )
        self.assertIn("defusedxml", fonte)

    def test_xml_malformado_da_erro_tratado(self):
        """XML partido não pode ser 500 com traceback."""
        r = self._post("<nfeProc><NFe><infNFe>")
        self.assertIn(r.status_code, (200, 400))
        corpo = json.loads(r.content)
        self.assertFalse(corpo.get("ok", False))
