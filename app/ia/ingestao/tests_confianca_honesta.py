"""Confiança de leitura que ninguém mediu não é "100% confiante".

O QUE ERA
---------
`bridge.py`, em `item_para_parametro`:

    "origem": {
        "documento": item.get("_origem", "nfe"),
        "campo": "det/prod",
        "confianca": item.get("_confianca", 1.0),     # <-- aqui
        "motor": item.get("_motor", "nfe-xml"),
    }

E o aviso, em `preparar_lancamento_nfe`:

    if confianca < 1.0:
        avisos.append(f"Extracao com confianca {confianca:.1f} - revise...")

O default 1.0 diz duas coisas, e as duas são falsas:

  1. Diz que a extração tem 100% de confiança, quando o motor omitiu o
     campo precisamente porque não o mediu.

  2. Diz mais do que isso: como o aviso só dispara abaixo de 1.0, o
     default NUNCA avisa. O motor não mediu, e o produto trata isso como
     medido e revisto.

Isto é o inverso do defeito que a IA-H e eu encontrámos em separado
(`or Decimal("1.0")`, `or 380`): ali um default baixo inventava um
número; aqui um default alto ESCONDE a ausência. O mesmo mecanismo com
o sinal trocado — e por isso é mais difícil de apanhar: nada aparece
malformado, aparece bem formado.

E era pior num sítio específico: isto é a rastreabilidade de uma nota
fiscal. "De onde veio este valor, e com que confiança?" é a pergunta que
justifica o registo existir. Um default de 1.0 responde à pergunta com a
resposta que o lector quer ouvir.

SEGUNDO PONTO, MAIS DISCRETO
-----------------------------
`float(rascunho.get("confianca") or 0.0)`. Sem o `or 0.0` seria melhor,
porque 0.0 é uma medição ("li, e não li nada") e None é ausência. Com
o `or`, as duas coisas viravam a mesma.

A RÉGUA
--------
`None` quando não foi medido. Nunca um número, e nunca 1.0: 1.0 é o
único valor que não pode ser escolhido por defeito, porque é o que
desliga o aviso.
"""

from unittest import TestCase, mock

from app.ia.ingestao import bridge


def _item(**kw):
    base = {
        "descricao": "Fertilizante",
        "codigo": "001",
        "quantidade": "10",
        "unidade": "KG",
        "valor_unitario": "100.00",
        "valor_total": "1000.00",
        "_origem": "nfe",
        "_motor": "nfe-xml",
    }
    base.update(kw)
    return base


def _rascunho(**kw):
    base = {
        "motor": "nfe-xml",
        "itens": [_item()],
        "chave_valida": True,
    }
    base.update(kw)
    return base


def _prepara(rascunho):
    """Corre `preparar_lancamento_nfe` sem o risco de injecção a falar."""
    with mock.patch.object(
        bridge, "avaliar_risco", return_value={"suspeita_injecao": False}
    ):
        return bridge.preparar_lancamento_nfe(rascunho)


class TestConfiancaNaoMedida(TestCase):
    """O `or`-ao-contrario: um default que ESCONDE em vez de inventar."""

    def test_um_item_sem_confianca_da_None(self):
        item = bridge.item_para_parametro(_item(), 1)
        self.assertIsNone(
            item["origem"]["confianca"],
            "a ausencia virou um numero — e se for 1.0, o aviso nunca dispara",
        )

    def test_a_confianca_medida_passa_intacta(self):
        item = bridge.item_para_parametro(_item(_confianca=0.62), 1)
        self.assertAlmostEqual(item["origem"]["confianca"], 0.62, places=3)

    def test_confianca_um_so_aparece_se_medido(self):
        """Este é o teste da regressão que importa: voltar a pôr 1.0
        como default. A diferença entre "o motor disse 1.0" e "ninguém
        mediu" é invisível no valor e decisiva no aviso."""
        item = bridge.item_para_parametro(_item(_confianca=1.0), 1)
        self.assertEqual(item["origem"]["confianca"], 1.0)

    def test_a_rastreabilidade_diz_o_motor(self):
        """O resto do bloco de origem continua inteiro. Sem confiança, o
        produtor ainda sabe de que documento e de que motor veio."""
        origem = bridge.item_para_parametro(_item(), 1)["origem"]
        self.assertEqual(origem["documento"], "nfe")
        self.assertEqual(origem["motor"], "nfe-xml")
        self.assertEqual(origem["campo"], "det/prod")

    def test_confianca_ausente_nao_vira_zero(self):
        """0.0 é uma medição ("li, e não li nada"). None é ausência.
        Com `or 0.0` as duas viravam a mesma."""
        item = bridge.item_para_parametro(_item(), 1)
        v = item["origem"]["confianca"]
        self.assertIsNot(v, 0.0, "ausencia transformada em zero")
        self.assertIsNone(v)


class TestOAvisoNaoDependeDoDefault(TestCase):
    """O aviso é a defesa. Com 1.0 nunca dispara; com None tem de
    disparar."""

    def test_sem_confianca_ha_aviso(self):
        avisos = " ".join(_prepara(_rascunho()).get("avisos", []))
        self.assertIn(
            "mediu",
            avisos,
            "sem confiança medida não há aviso — e sem aviso não há revisão",
        )

    def test_com_confianca_alta_nao_ha_aviso(self):
        avisos = " ".join(_prepara(_rascunho(confianca=1.0)).get("avisos", []))
        self.assertNotIn("mediu", avisos)

    def test_com_confianca_baixa_o_aviso_diz_o_numero(self):
        avisos = " ".join(_prepara(_rascunho(confianca=0.4)).get("avisos", []))
        self.assertIn("0.4", avisos)

    def test_o_aviso_diz_para_rever(self):
        """Um aviso que não diz o que fazer é um aviso que ninguém
        cumpre."""
        avisos = " ".join(_prepara(_rascunho()).get("avisos", []))
        baixo = avisos.lower()
        self.assertTrue(
            "confira" in baixo or "revise" in baixo,
            f"o aviso não diz o que fazer: {avisos!r}",
        )


class TestAConfiancaTravelaAteOParametro(TestCase):
    """De `_confianca` até ao `params` que o resto do sistema vê."""

    def _confianca_no_parametro(self, **kw):
        r = _prepara(_rascunho(**kw))
        # A confiança viaja dentro de `origem` — é de lá que a
        # rastreabilidade se lê, e é o que a tela de confirmação mostra.
        return r["params"]["itens"][0]["origem"]["confianca"]

    def test_o_parametro_carrega_a_confianca_medida(self):
        self.assertAlmostEqual(
            self._confianca_no_parametro(confianca=0.8), 0.8, places=3
        )

    def test_o_parametro_carrega_None_quando_nao_medido(self):
        """O `or 0.0` estava no caminho: uma nota sem confiança apanhava
        um '0.0' com aspecto de medido no payload que o resto do sistema
        consome."""
        self.assertIsNone(self._confianca_no_parametro())

    def test_o_lancamento_continua_a_ser_produzido(self):
        """O inverso: uma correcção que bloqueie a ingestão toda também
        é uma correcção errada. Sem confiança, revê-se — não recusa-se."""
        r = _prepara(_rascunho())
        self.assertTrue(r.get("executavel", False))
        self.assertEqual(len(r["params"]["itens"]), 1)
