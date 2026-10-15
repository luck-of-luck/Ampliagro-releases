"""O teste que mostra se o buraco era real.

MEDIDO 2026-10-06. A primeira sondaComparou `defusedxml` com a nativa e
concluiu "a nativa tambem recusou" - logo o buraco nao existia. **Falso**, e
por uma razao especifica: o `billion laughs` que escrevi tinha `&lol;`
desbalanceado, que e' erro de SINTAXE. O parser recusou por estar mal
formado, nao por ser perigoso.

Um teste de seguranca que passa porque o input esta' mal formado nao testa a
defesa - testa o parser. Este ficheiro tem os dois casos, com o input
BEM FORMADO, e compara o que cada leitor faz.

Por que isto importa para alem desta sessao: um teste de seguranca que passa
pelo motivo errado e' pior do que nenhum, porque da confianca. E' o mesmo
padrao do `grep sefaz` a reportar capacidade inexistente, e do limiar 0.6 a
fazer o navegador discordar do servidor.
"""

from decimal import Decimal

from django.test import TestCase

# XML BEM FORMADO com uma entidade definida - o ataque classico de expansao.
BILLION_LAUGHS = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    "<!DOCTYPE lolz [\n"
    '  <!ENTITY lol "lol">\n'
    '  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">\n'
    '  <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">\n'
    '  <!ENTITY lol4 "&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;">\n'
    '  <!ENTITY lol5 "&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;">\n'
    '  <!ENTITY lol6 "&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;">\n'
    '  <!ENTITY lol7 "&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;">\n'
    "]>\n"
    '<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">'
    "<v>&lol7;</v>"
    "</nfeProc>"
)

# XXE: entidade externa que aponta para um ficheiro do sistema.
XXE_WINDOWS = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    "<!DOCTYPE foo [\n"
    '  <!ENTITY xxe SYSTEM "file:///c:/windows/win.ini">\n'
    "]>\n"
    '<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">'
    "<v>&xxe;</v>"
    "</nfeProc>"
)

NF_REAL = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">\n'
    "  <NFe>\n"
    '    <infNFe versao="4.00" '
    'Id="NFe35240612345678000199550010000000011000000017">\n'
    "      <ide><nNF>123</nNF><serie>1</serie>"
    "<dhEmi>2026-03-10T10:00:00-03:00</dhEmi><modFrete>9</modFrete></ide>\n"
    "      <emit><CNPJ>12345678000199</CNPJ>"
    "<xNome>Fazenda Emitente</xNome></emit>\n"
    "      <dest><CNPJ>98765432000188</CNPJ><xNome>Comprador</xNome></dest>\n"
    '      <det nItem="1">\n'
    "        <prod><xProd>UREIA 45%</xProd><NCM>31021000</NCM>"
    "<CFOP>5102</CFOP><uCom>SC</uCom><qCom>50.000</qCom>"
    "<vUnCom>2500.00</vUnCom><vProd>125000.00</vProd></prod>\n"
    "        <imposto><ICMS><ICMSTot><vBC>125000.00</vBC>"
    "<vICMS>0.00</vICMS></ICMSTot></ICMS></imposto>\n"
    "      </det>\n"
    "      <total><ICMSTot><vBC>125000.00</vBC>"
    "<vICMS>0.00</vICMS></ICMSTot></total>\n"
    "    </infNFe>\n"
    "  </NFe>\n"
    "</nfeProc>"
)


class OLeitorEstaEndurecido(TestCase):
    def test_o_modulo_usa_defusedxml(self):
        """A CORRECAO. Este e' o teste que falha se alguem voltar a nativa."""
        import inspect

        from app.ia.ingestao import nfe as ing

        src = inspect.getsource(ing)
        # A palavra aparece no comentario que explica a correccao - o que
        # interessa e' se ha um IMPORT, nao se a string existe.
        tem_import = any(
            linha.strip().startswith("import xml.etree")
            or linha.strip().startswith("from xml")
            for linha in src.splitlines()
        )
        self.assertFalse(tem_import, "o modulo voltou a importar a nativa")
        self.assertIn("from defusedxml import ElementTree", src)

    def test_a_defesa_esta_no_codigo_e_nao_so_no_comentario(self):
        import inspect

        from app.ia.ingestao import nfe as ing

        src = inspect.getsource(ing)
        self.assertIn("DefusedXmlException", src)


class OComportamento(TestCase):
    """O que o produtor ve, para cada entrada."""

    def _parse(self, xml: str):
        from app.ia.ingestao import nfe as ing

        return ing.extrair_nfe_xml(xml.encode("utf-8"))

    # --- o que tem de continuar a funcionar ----------------------------
    def test_uma_nfe_real_e_lida(self):
        r = self._parse(NF_REAL)
        self.assertTrue(r.get("ok"), f"NF-e valida rejeitada: {r.get('erro')}")
        self.assertEqual(len(r.get("itens") or []), 1)
        self.assertEqual(
            (r["itens"][0].get("descricao") or r["itens"][0].get("produto")),
            "UREIA 45%",
        )

    def test_a_ncm_sai_da_nota(self):
        """`F06` (NCM/TIPI) e' um dos criterios que a folha marca como
        parcial. A NF-e ja' traz a NCM de cada item - e' de la' que tem de
        vir, nao de um cadastro manual que o produtor preenchewrong."""
        r = self._parse(NF_REAL)
        self.assertEqual(r["itens"][0].get("ncm"), "31021000")

    def test_o_emitente_e_a_data_saem(self):
        r = self._parse(NF_REAL)
        self.assertTrue(r.get("fornecedor") or r.get("emitente"))
        self.assertEqual(r.get("data"), "2026-03-10")

    # --- o que tem de ser recusado -------------------------------------
    def test_billion_laughs_e_recusado(self):
        r = self._parse(BILLION_LAUGHS)
        self.assertFalse(r.get("ok"))
        self.assertIn("recusado", (r.get("erro") or "").lower())

    def test_xxe_nao_le_ficheiro_do_sistema(self):
        r = self._parse(XXE_WINDOWS)
        self.assertFalse(r.get("ok"))
        dump = str(r).lower()
        self.assertNotIn("[fonts]", dump)
        self.assertNotIn("[extensions]", dump)

    def test_xxe_tem_codigo_distinto_do_xml_invalido(self):
        """Sao coisas diferentes e quem le o erro precisa de saber qual.

        'XML invalido' e' um download pela metade. 'XML perigoso' e' uma
        tentativa. Um sistema que responde as duas com 'arquivo corrompido'
        ensina o produtor a ignorar os avisos de seguranca - que sao os que
        importam.
        """
        r_perigoso = self._parse(BILLION_LAUGHS)
        r_invalido = self._parse("<nfeProc><sem-fechar>")
        self.assertNotEqual(r_perigoso.get("erro"), r_invalido.get("erro"))
        self.assertFalse(r_invalido.get("ok"))
        self.assertIn("invalido", (r_invalido.get("erro") or "").lower())

    def test_recusar_nao_e_levantar(self):
        """O modulo promete nunca levantar. Um 500 aqui transformaria
        'arquivo mau' em 'sistema fora do ar'."""
        for xml in (BILLION_LAUGHS, XXE_WINDOWS, "<nfeProc>", b"nao sou xml"):
            r = self._parse(xml) if isinstance(xml, str) else None
            if r is None:
                from app.ia.ingestao import nfe as ing

                r = ing.extrair_nfe_xml(xml)
            self.assertIsInstance(r, dict)
            self.assertFalse(r.get("ok"))

    def test_o_teto_de_tamanho_nao_substitui_o_defusedxml(self):
        """O teto de 12 MB limita o FICHEIRO, nao a EXPANSAO.

        Um XML de 588 bytes com sete entidades aninhadas - o caso 2 - cresce
        para 10^7 caracteres se for expandido. Por isso as duas defesas sao
        ambas necessarias, e este teste existe para-nessa conclusao nao ser
        esquecida quando alguem perguntar porque as duas coisas.
        """
        self.assertLess(len(BILLION_LAUGHS), 1024, "o ataque tem de ser pequeno")
        r = self._parse(BILLION_LAUGHS)
        self.assertFalse(r.get("ok"))
