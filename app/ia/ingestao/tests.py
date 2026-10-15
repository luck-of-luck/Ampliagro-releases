"""
Testes da BUILD 1: ingestao (OCR, NFe, audio).

Estes testes existem porque cada modulo novo tem um modo de falha que nao
aparece no fluxo feliz:

* `ocr` — degradar em silencio e o modo como ele ja falhou uma vez;
* `nfe`  — tag com namespace, que faz o parser devolver zero em 100% das
           notas reais se ninguem testar com XML de verdade;
* `audio` — extrair sinal do ruido, eDO inventario de peso, que e a decisao
           de arquitetura e nao pode ser opinião.

O teste de `audio.peso_por_ia` e o mais importante deste arquivo: ele trava a
aritmetica que decidiu a arquitetura. Se o numero mudar, a decisao muda e o
documento precisa ser reescrito.
"""

import json
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from app.ia.ingestao import audio, nfe, ocr

# Uma NFe com namespace, como sai de verdade do portal. Montada byte a byte
# para o teste nao depender de fixture externo.
NFE_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
 <NFe>
  <infNFe Id="NFe35260812345678000166550010000001231000001234" versao="4.00">
   <ide><dhEmi>2026-09-26T10:22:33-03:00</dhEmi></ide>
   <emit><CNPJ>12345678000199</CNPJ><xNome>Fertilizantes Vale Verde LTDA</xNome></emit>
   <dest><CNPJ>98765432000188</CNPJ><xNome>Fazenda Modelo</xNome></dest>
   <det nItem="1"><prod>
     <cProd>UREIA45</cProd><xProd>Ureia 45% granulada</xProd>
     <NCM>31021000</NCM><CFOP>5102</CFOP><uCom>KG</uCom>
     <qCom>1250.000</qCom><vUnCom>4.8900</vUnCom><vProd>6112.50</vProd>
   </prod></det>
   <det nItem="2"><prod>
     <cProd>GLIFO</cProd><xProd>Glyphosate 480 SL</xProd>
     <NCM>38089400</NCM><CFOP>5102</CFOP><uCom>L</uCom>
     <qCom>20.000</qCom><vUnCom>38.9000</vUnCom><vProd>778.00</vProd>
   </prod></det>
   <total><ICMSTot><vNF>6890.50</vNF></ICMSTot></total>
  </infNFe>
 </NFe>
</nfeProc>"""


class OcrTest(TestCase):
    """O invariante: nunca falhar em silencio."""

    def test_arquivo_vazio_nao_quebra(self):
        r = ocr.extrair_texto(b"")
        self.assertFalse(r["texto"])
        self.assertTrue(r["aviso"], "sem arquivo ainda precisa de aviso")

    def test_nao_e_imagem_avisa_em_vez_de_vazar_excecao(self):
        r = ocr.extrair_texto(b"isso nao e uma imagem")
        self.assertEqual(r["motor"], "imagem-invalida")
        self.assertTrue(r["aviso"])
        self.assertEqual(r["confianca"], 0.0)

    def test_arquivo_grande_e_recusado_antes_de_decodificar(self):
        """Decodificar 30 MB numa foto de celular estoura RAM de servidor."""
        grande = b"x" * (ocr.MAX_BYTES + 1)
        r = ocr.extrair_texto(grande)
        self.assertEqual(r["motor"], "arquivo-grande")
        self.assertIn("MB", r["aviso"])

    def test_sem_tesseract_avisa_em_vez_de_devolver_vazio(self):
        """REGRESSAO do bug original: o `except` engolia tudo.

        Com Tesseract ausente, o produtor precisa ler que o sistema nao leu a
        nota. Um rascunho com 'imagem JPEG 800x600' e zero aviso e pior que
        um erro: faz o produtor acreditar que a nota estava em branco.
        """
        import io
        from unittest.mock import patch

        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", (240, 80), "white").save(buf, format="PNG")

        with patch.object(ocr, "tesseract_disponivel", return_value=False):
            r = ocr.extrair_texto(buf.getvalue())
        self.assertEqual(
            r["motor"], "sem-ocr", "deveria chegar no aviso de OCR ausente"
        )
        self.assertIn(
            "XML", r["aviso"], "o aviso precisa sugerir o caminho que funciona"
        )
        self.assertEqual(r["confianca"], 0.0)

    def test_diagnostico_nao_promete_ocr_que_nao_existe(self):
        d = ocr.diagnostico()
        self.assertIsInstance(d["tesseract"], bool)
        if not d["tesseract"]:
            self.assertIn("XML", d["nota"])
            self.assertEqual(d["modo_padrao"], "nfe-xml")

    def test_deteccao_de_xml(self):
        self.assertTrue(ocr.parece_nfe_xml(NFE_XML))
        self.assertFalse(ocr.parece_nfe_xml(b"\x89PNG\r\n\x1a\n"))


class NfeTest(TestCase):
    """O invariante: XML de verdade, com namespace, produce estrutura."""

    def setUp(self):
        self.r = nfe.extrair_nfe_xml(NFE_XML)

    def test_extrai_com_namespace(self):
        """REGRESSAO: `find('.//infNFe')` nao casa tag com namespace.

        Toda NFe real tem namespace, entao o parser devolveria zero itens em
        100% das notas — e isso so apareceria com um XML de verdade.
        """
        self.assertTrue(self.r["ok"], self.r.get("erro"))
        self.assertEqual(self.r["qtd_itens"], 2)
        self.assertEqual(self.r["chave_valida"], True)
        self.assertEqual(self.r["emitente"], "Fertilizantes Vale Verde LTDA")
        self.assertEqual(self.r["destinatario"], "Fazenda Modelo")

    def test_valores_sao_decimal_nao_float(self):
        """Dinheiro em float perde precisao, e a conciliacao bancaria audita
        exatamente a diferencia entre 12.50 e 12.5."""
        self.assertIsInstance(self.r["valor_total"], Decimal)
        self.assertEqual(self.r["valor_total"], Decimal("6890.50"))
        for item in self.r["itens"]:
            self.assertIsInstance(item["valor_total"], Decimal)
            self.assertIsInstance(item["quantidade"], Decimal)

    def test_confianca_1_quando_completo(self):
        self.assertEqual(self.r["confianca"], 1.0)

    def test_xml_truncado_nao_levanta(self):
        """Download pela metade e comum. 500 seria transformar arquivo ruim em
        sistema fora do ar."""
        r = nfe.extrair_nfe_xml(NFE_XML[: len(NFE_XML) // 2])
        self.assertFalse(r["ok"])
        self.assertTrue(r["erro"] or r["aviso"])

    def test_html_de_erro_do_portal_nao_vira_nfe(self):
        r = nfe.extrair_nfe_xml(b"<html><body>Erro 500 no servidor</body></html>")
        self.assertFalse(r["ok"])
        self.assertEqual(r["codigo"], "nao-e-nfe")

    def test_chave_invalida_marca(self):
        xml = NFE_XML.replace(b"35260812345678000166550010000001231000001234", b"123")
        r = nfe.extrair_nfe_xml(xml)
        self.assertFalse(r["chave_valida"])
        self.assertLess(r["confianca"], 1.0)

    def test_valor_ausente_e_none_nao_zero(self):
        """Distinguir 'R$ 0,00' de 'nao informado' importa: zero e giveaway,
        ausente e campo faltando, e a decisao e do produtor."""
        xml = NFE_XML.replace(b"<qCom>1250.000</qCom>", b"<qCom></qCom>")
        r = nfe.extrair_nfe_xml(xml)
        self.assertIsNone(r["itens"][0]["quantidade"])

    def test_resumo_para_ia_cabe_no_prompt(self):
        """O prompt do SmolLM2 e de 4096 tokens. Uma nota de 200 itens nao
        pode estourar o contexto e derrubar o raciocinio inteiro."""
        grande = {
            "ok": True,
            "chave_acesso": "x" * 44,
            "emitente": "F",
            "destinatario": "D",
            "data": "2026-01-01",
            "valor_total": Decimal("1"),
            "itens": [
                {
                    "descricao": "item",
                    "quantidade": Decimal(1),
                    "unidade": "KG",
                    "valor_unitario": Decimal(1),
                    "valor_total": Decimal(1),
                    "ncm": "1",
                }
            ]
            * 200,
        }
        t = nfe.resumir_para_ia(grande, limite=900)

        # 1) cabe no prompt do SmolLM2 (4096 tokens)
        self.assertLessEqual(len(t), 900)

        # 2) e, se cortou, DIZ que cortou. Este e o ponto: sem o aviso, o modelo
        #    recebe 40 itens e trata como se fossem a nota inteira, e pode
        #    "conciliar" uma nota de 200 itens com um terco do valor.
        self.assertIn("ATENCAO", t, "o corte precisa ser declarado ao modelo")
        self.assertIn("omitidos", t)

        # 3) e as regras no fim sobrevivem ao corte
        self.assertIn("REGRAS", t)

    def test_resumo_manda_nao_recalcular(self):
        t = nfe.resumir_para_ia(self.r)
        self.assertIn("nao recalcule", t.lower())
        self.assertIn("confirmacao", t.lower())


class AudioTest(TestCase):
    def test_peso_do_whisper_eh_fracao_do_llm(self):
        """TRAVA A RELACAO, nao o literal.

        A primeira versao deste teste afirmava `pesos["tiny"] == 39`. O numero
        estava errado — eu tinha medido um arquivo solto e somei como se fosse
        o par encoder+decoder, e o real e' 50 MB. Um teste que trava um literal
        errado e pior do que nenhum teste: ele valida o erro com conviccao.

        O que importa para a arquitetura nao e o valor exato, e a RELACAO: o
        Whisper tem de ser uma fracao irrelevante do LLM. Se algum dia essa
        fracao deixar de ser pequena, a decisao de rodar no cliente cai sozinha.
        """
        d = audio.diagnostico()
        pesos = d["cliente"]["pesos_mb"]
        llm = d["cliente"]["llm_peso_mb"]

        for nome, peso in pesos.items():
            with self.subTest(modelo=nome):
                fracao = peso / llm
                self.assertLess(
                    fracao,
                    0.25,
                    f"{nome} a {fracao:.1%} do LLM nao e mais uma fracao "
                    f"irrelevante — a decisao de rodar no cliente precisa ser revista",
                )

        # e o tiny precisa continuar sendo o mais leve, senao a escolha do
        # default no cliente (tiny) deixa de fazer sentido
        self.assertEqual(min(pesos, key=pesos.get), "tiny")

    def test_dtype_webgpu_existe_no_repo_escolhido(self):
        """O repo do modelo precisa ter o dtype que o WebGPU usa.

        `onnx-community/whisper-tiny` NAO tem `q4f16` — so o `Xenova/*` tem.
        Trocar o repo por `onnx-community` "para ser mais novo" faz o WebGPU
        cair para um dtype que nao existe la, e o sintoma e um fallback
        silencioso para WASM em vez de um erro claro.
        """
        d = audio.diagnostico()["cliente"]
        self.assertEqual(d["dtype"], "q4f16", "WebGPU precisa de fp16")
        self.assertTrue(
            d["modelo"].startswith("Xenova/"),
            f"{d['modelo']} nao publica q4f16; use Xenova/whisper-*",
        )

    def test_visao_nao_cabe_no_cliente(self):
        """A visao foi para o servidor por ARITMETICA, nao por preferencia.

        O WebLLM 0.2.79 tem 143 modelos e so um par de visao (Phi-3.5-vision,
        4.2B, ~2,6 GB). Com o LLM de texto de 1,1 GB ja residente, sao ~3,7 GB
        de pesos num aparelho de 4 GB.
        """
        d = audio.diagnostico()["visao"]
        self.assertEqual(d["onde"], "servidor")
        self.assertIn("2,6 GB", d["porque"])
        self.assertIn("TEXTO", d["regra"])

    def test_servidor_nao_exige_celery(self):
        """Redis nao responde nesta maquina, entao Celery nao pode ser o unico
        caminho — a funcionalidade entraria no ar e nunca funcionaria."""
        d = audio.diagnostico()["servidor"]
        self.assertFalse(d["celery_necessario"])
        self.assertFalse(d["redis_necessario"])

    def test_extrai_sinais_do_audio_do_tratorista(self):
        """O exemplo do plano, literal."""
        texto = (
            "Ola chefe, terminei de bater 50 litros do veneno no talhao 4 e o "
            "trator John Deere ferveu a agua, ponto"
        )
        s = audio.extrair_sinais(texto)
        self.assertIn("4", s["talhoes"])
        self.assertTrue(any(q["valor"] == "50" for q in s["quantidades"]))
        self.assertIn("veneno", s["classes_insumo"])
        self.assertTrue(s["sinais_de_falha"], "'ferveu' e sinal de falha")
        # "terminei de bater" e relato de servico ja concluido, nao comando.
        # Marcar como acao fisica pediria confirmacao de algo que ja aconteceu.
        self.assertFalse(
            s["sugere_acao_fisica"],
            "relato de trabalho concluido nao e comando para acionar nada",
        )
        # O mesmo detector, no caso que importa: um comando de verdade.
        self.assertTrue(
            audio.extrair_sinais("liga a irrigacao do talhao 4")["sugere_acao_fisica"],
            "mas 'liga a irrigacao' e comando e precisa chegar na confirmacao",
        )

    def test_virgula_decimal_pt_br(self):
        s = audio.extrair_sinais("gastei 12,5 litros de glifosato no talhao 2")
        valores = [q["valor"] for q in s["quantidades"]]
        self.assertIn("12.5", valores, "virgula decimal vira ponto para o Decimal")

    def test_texto_vazio_nao_inventa_sinal(self):
        """Um extrator de sinal que alucina e pior que um que nao extrai:
        o LLM recebe 'talhao 3' que nao foi dito e age em cima disso."""
        s = audio.extrair_sinais("")
        self.assertEqual(s["talhoes"], [])
        self.assertEqual(s["quantidades"], [])
        self.assertFalse(s["sugere_acao_fisica"])

    def test_limpa_sazonais_de_dictado(self):
        t = audio.limpar_transcricao("terminei a tarefa, ponto e vou embora, virgula")
        self.assertNotIn("ponto", t)
        self.assertNotIn("vírgula", t)
        self.assertIn("terminei", t)


class IngestaoNaoGravaSozinhaTest(TestCase):
    """Regra que atravessa os tres modulos: nada grava sem o produtor.

    Vale tanto para NFe quanto para audio. A confirmacao vive no sandbox
    (`needs_confirm`); o que a ingestao garante e nunca chamar a acao por conta
    propria.
    """

    def setUp(self):
        self.u = User.objects.create_user("ing", "i@x.com", "p")

    def test_nfe_nao_chama_acao_ao_parsear(self):
        from unittest.mock import patch

        with patch("app.ia.sandbox.executar") as m:
            nfe.extrair_nfe_xml(NFE_XML)
        m.assert_not_called()

    def test_audio_nao_chama_acao_ao_extrair_sinais(self):
        from unittest.mock import patch

        with patch("app.ia.sandbox.executar") as m:
            audio.extrair_sinais("liga a irrigacao do talhao 4")
        m.assert_not_called()

    def test_diagnosticos_sao_json_serializaveis(self):
        """Vaop para a UI de configuracao; nao pode estourar na serializacao."""
        for d in (ocr.diagnostico(), audio.diagnostico()):
            json.dumps(d, ensure_ascii=False)
