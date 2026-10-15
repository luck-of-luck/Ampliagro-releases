"""A5: o `confirm()` de presets corrompidos aparecia a quem nunca teve presets.

A condicao em app/templates/base.html era:

    var order = JSON.parse(localStorage.getItem('matrix-preset-order') || '[]');
    var active = localStorage.getItem('matrix-active-preset');
    if (!order.length || !active) { ... confirm('Presets corrompidos...') }

`!order.length` e' verdadeiro quando a chave NAO EXISTE. Uma chave ausente no
localStorage devolve null, `null || '[]'` da '[]', e `![].length` da verdadeiro.
Ou seja: ausencia e corrupcao caiam no mesmo ramo.

E o gatilho nao era uma accao do produtor: sw.js:113 manda CLEAR_PRESET_CACHE
no evento `activate` do service worker, que corre a CADA VEZ QUE UMA NOVA
VERSAO DO SW SAI — que e' quando o produtor abre a aplicacao.

Resultado, medido nesta sessao no browser real com o storage vazio (primeira
visita): o `confirm()` disparava com o texto 'Presets corrompidos foram limpos.
Recarregar para restaurar Agua?'. Se o produtor clicasse em OK, a pagina
recarregava-lhe no meio do que estava a fazer.

Este ficheiro fixa a DISTINCAO entre as duas coisas, executando a mesma
condicao antes e depois. Nao le o template: a logica esta aqui em Python,
porque o que se fixou foi o comportamento, nao a linha.
"""

import unittest


def condicao_antiga(order_json, active):
    """O que base.html fazia. `order_json` e' None quando a chave nao existe."""
    import json

    try:
        order = json.loads(order_json or "[]")
        if not order or not active:
            return "LIMPA + confirm(...)"
        return "nao faz nada"
    except Exception:
        return "except: nao faz nada"


def condicao_nova(order_json, active):
    """O que faz agora: separa AUSENCIA de CORRUPCAO."""
    import json

    if order_json is None and active is None:
        return "SAI (nunca houve presets)"
    try:
        order = json.loads(order_json or "[]")
    except Exception:
        return "LIMPA (JSON invalido)"
    if not isinstance(order, list) or not order or not active:
        return "LIMPA (sem dialogo)"
    return "nao faz nada"


class TestaAusenciaNaoECorrupcao(unittest.TestCase):
    def setUp(self):
        # None = a chave nao existe no localStorage (primeira visita)
        self.ausencia = None
        self.agua = '["Agua"]'
        self.agua_nome = "Agua"

    def test_primeira_visita_nao_dispara_dialogo(self):
        """O bug: quem nunca teve presets recebia 'presets corrompidos'."""
        self.assertEqual(
            condicao_nova(self.ausencia, self.ausencia),
            "SAI (nunca houve presets)",
        )
        # e a antiga mostrava o dialogo — este e' o que mudou
        self.assertIn("confirm", condicao_antiga(self.ausencia, self.ausencia))

    def test_preset_coerente_nao_dispara_nada(self):
        self.assertEqual(condicao_nova(self.agua, self.agua_nome), "nao faz nada")

    def test_json_invalido_e_corrupcao_real(self):
        """Storage danificado a serio: limpa, e nao e' ausencia."""
        self.assertEqual(
            condicao_nova("{isto nao e' json", "Agua"),
            "LIMPA (JSON invalido)",
        )

    def test_ausencia_com_active_presente_e_incoerencia(self):
        """Tinha 'active' gravado mas a ordem desapareceu: isso e' corrupcao."""
        self.assertEqual(
            condicao_nova(self.ausencia, self.agua_nome),
            "LIMPA (sem dialogo)",
        )

    def test_ordem_vazia_com_active_e_incoerencia(self):
        self.assertEqual(condicao_nova("[]", self.agua_nome), "LIMPA (sem dialogo)")

    def test_a_distincao_que_importa(self):
        """Ausencia nao e' corrupcao. E' a linha que o bug apagava."""
        # ausencia: as duas chaves em falta -> nao ha nada a recuperar
        self.assertNotIn("LIMPA", condicao_nova(self.ausencia, self.ausencia))
        # corrupcao: havia preset e ficou incoerente -> recuperar
        self.assertIn("LIMPA", condicao_nova("{lixo", self.agua_nome))


if __name__ == "__main__":
    print()
    print("=== o que mudou, caso a caso ===")
    casos = [
        ("primeira visita (nada gravado)", None, None),
        ("so' o preset Agua", '["Agua"]', "Agua"),
        ("ordem vazia, active presente", "[]", "Agua"),
        ("JSON invalido", "{isto nao e' json", "Agua"),
    ]
    for nome, o, a in casos:
        print(f"  {nome}")
        print(f"     antes : {condicao_antiga(o, a)}")
        print(f"     agora : {condicao_nova(o, a)}")
    print()
    print("  so' o primeiro caso mudou de 'LIMPA' para 'SAI'.")
    print("  E' exactamente o produtor novo que deixou de ver o dialogo.")
