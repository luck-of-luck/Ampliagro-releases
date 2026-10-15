"""As ferramentas de campo: os obrigatórios não têm omissão.

MEDIDO 2026-10-05. As calculadoras antigas traziam `value="10"`,
`value="120"`, `value="92"`. O produtor via um número que não escolheu,
carregava «Calcular», e o resultado saía com a assinatura dele em cima.

Isto é o botão NDVI outra vez. O `0.72` num `catch` de rota 404 era
`value="0.72"`: um input inventado que a tela assinava como leitura. Um
cálculo com um campo por omissão é uma mentira com aritmética — e pior,
porque parece trabalho a sério em vez de um número solto num `alert`.

A REGRA DESTE FICHEIRO
======================
**Campo obrigatório é o que não tem `value`.** Não é o mais importante, é o
que o produtor ainda não decidiu.

Os opcionais têm `value="0"`, e isso é uma afirmação declarada: «não
declaraste quebra, portanto a quebra é zero». Não é esquecimento.

Este ficheiro não testa a aritmétia — para isso seria preciso correr JS no
browser. Testa a **estrutura da promessa**, que é o que mente.
"""

import pathlib
import re

from django.test import SimpleTestCase

RAIZ = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = RAIZ / "app" / "templates" / "guia-ferramentas.html"


def texto() -> str:
    return TEMPLATE.read_text(encoding="utf-8", errors="replace")


#: Os campos que o produtor tem de decidir. Todos sem omissão.
OBRIGATORIOS = [
    "gfAduboDose",
    "gfAduboArea",
    "gfSemPop",
    "gfSemPms",
    "gfSemGerm",
    "gfSemArea",
    "gfPulvVel",
    "gfPulvEsp",
    "gfPulvVol",
    "gfConvVal",
    "gfUniQtd",
    "gvArea",
    "gvCusto",
    "gvPreco",
    "gvProd",
]


class CamposObrigatoriosNaoTemOmissao(SimpleTestCase):
    def test_ningum_campo_obrigatorio_tem_valor_por_omissao(self):
        """O teste central. Um obrigatório com `value` é uma mentira.

        O campo nasce preenchido com um número que ninguém escolheu, o
        produtor carrega «Calcular», e o resultado é aritmética correcta
        sobre uma decisão que ele não tomou. Para o produtor é impossível
        distinguir isto de um cálculo com os dados dele.
        """
        t = texto()
        culpados = []
        for campo in OBRIGATORIOS:
            m = re.search(r'<input[^>]*id="%s"[^>]*>' % re.escape(campo), t, re.S)
            assert m, f"campo {campo} não encontrado no template"
            tag = m.group(0)
            # `value=` dentro da tag = omissão.
            if re.search(r"\bvalue\s*=", tag):
                # `value="{{ }}"` é template, não omissão: o Django escreve.
                valor = re.search(r'\bvalue\s*=\s*"([^"]*)"', tag)
                v = valor.group(1) if valor else "?"
                if "{{" not in v and "{%" not in v:
                    culpados.append(f"{campo} = {v}")

        self.assertEqual(
            culpados,
            [],
            "campos obrigatórios com valor por omissão: %s\n\n"
            "Cada um destes números vai aparecer no resultado com a assinatura "
            "do produtor, e ele não o escolheu. Um obrigatório sem omissão é a "
            "única forma de o cálculo ser dele." % ", ".join(culpados),
        )

    def test_todo_obrigatorio_tem_asterisco_no_rotulo(self):
        """O asterisco tem de estar no rótulo, não só na convenção.

        O campo e o seu `*` estão no HTML a metros de distância. Se o `*`
        estiver no label, o produtor lê «required» ao lado do nome do campo.
        """
        t = texto()
        for campo in OBRIGATORIOS:
            m = re.search(
                r'<label[^>]*for="%s"[^>]*>(.*?)</label>' % re.escape(campo),
                t,
                re.S,
            )
            assert m, f"campo {campo} não tem label"
            rotulo = m.group(1)
            self.assertIn(
                "gf-campo-obl",
                rotulo,
                f"o label de {campo} não marca a obrigatoriedade. "
                f"Sem o asterisco no rótulo, o produtor não sabe que tem de "
                f"preencher aquilo — e o campo nasce vazio, o que parece um "
                f"erro dele e não uma exigência do cálculo.",
            )

    def test_um_campo_e_marcado_como_opcional_quando_e_opcional(self):
        """O simétrico. Um campo opcional que não diz que é opcional é
        ambíguo: parece obrigatório e não tem asterisco.

        A regra de leitura passa a ser: com `*` é obrigatório; sem `*` é
        opcional e tem omissão zero. Isso só funciona se a distinção estiver
        escrita no rótulo.
        """
        t = texto()
        opcionais = re.findall(
            r'<label[^>]*for="(gf\w+|gv\w+)"[^>]*>(.*?)</label>', t, re.S
        )
        for campo, rotulo in opcionais:
            if campo in OBRIGATORIOS:
                continue
            self.assertTrue(
                "gf-campo-opc" in rotulo or ">opcional<" in rotulo,
                f"{campo} não é obrigatório mas o rótulo não diz que é "
                f"opcional. O produtor tem de poder distinguir os dois "
                f"tipos sem saber a regra.",
            )


class NenhumCampoNumeroTemOmissaoInventado(SimpleTestCase):
    def test_nenhum_input_number_tem_value_hardcoded(self):
        """Varredura ampla: nenhum `input type="number"` leva `value`.

        Mais apertado do que a lista de obrigatórios de propósito — apanha
        um campo novo que nasça preenchido, antes de alguém o declarar
        obrigatório.

        A excepção é `value="{{` (o Django escreve o valor) e `value="0"`
        nos opcionais, que é uma afirmação declarada e não uma invenção.
        """
        t = texto()
        numeros = re.findall(r'<input[^>]*type="number"[^>]*>', t, re.S)
        com_valor = []
        for tag in numeros:
            m = re.search(r'\bvalue\s*=\s*"([^"]*)"', tag)
            if not m:
                continue
            v = m.group(1).strip()
            if "{{" in v or "{%" in v:
                continue  # o Django escreve isto em runtime
            # identificador do campo
            idm = re.search(r'id="([^"]+)"', tag)
            campo = idm.group(1) if idm else "?"
            if v not in ("0", "0.0", "0.00"):
                com_valor.append(f"{campo} = {v}")

        self.assertEqual(
            com_valor,
            [],
            "inputs numéricos com valor por omissão que não seja zero: %s\n\n"
            "Zero num campo opcional é uma declaração («não há quebra»). "
            "Qualquer outro número é uma decisão que o sistema tomou pelo "
            "produtor." % ", ".join(com_valor),
        )


class FerramentasUsamDadosReais(SimpleTestCase):
    def test_ndvi_nao_tem_numero_de_omissao(self):
        """A regra do NDVI, que é a lição de hoje.

        `0.72` apareceu num `catch` de uma rota 404. Este teste garante que
        não volta — nem como omissão de campo, nem como fallback.
        """
        t = texto()
        # O `catch` e o `else` do NDVI não podem escrever decimais.
        for nome in ("gfNdviOut",):
            m = re.search(r"mostra\('%s',\s*(.*?)\);\n" % nome, t, re.S)
        # Versão prática: o NDVI não tem nenhum decimal no código.
        bloco = t[t.index("lerNdvi") : t.index("// ── Voz")]
        decimais = re.findall(r"\b0\.\d+\b", bloco)
        self.assertEqual(
            decimais,
            [],
            f"o bloco do NDVI tem decimais {decimais}. Um índice de vegetação "
            f"escrito no código é um número que a falha fabricou — foi "
            f"exactamente o defeito de hoje.",
        )

    def test_ndvi_usa_a_rota_que_existe(self):
        """A rota tem de ser a real, e `r.ok` tem de ser verificado.

        Duas verificações porque falharam as duas em tempos diferentes:
        a rota errada (`/api/ia/super/`) e o parse sem `r.ok` (404 devolve
        HTML, e `r.json()` sobre HTML lança).
        """
        t = texto()
        bloco = t[t.index("lerNdvi") : t.index("// ── Voz")]
        self.assertIn("/api/agronomia/ndvi/", bloco)
        # `/api/ia/super/` só pode aparecer no COMENTÁRIO que explica o
        # defeito. Se aparecer em código, volta a ser a rota inventada.
        #
        # Verifico linha a linha, ignorando as de comentário, porque o
        # comentário é o registo do que aconteceu e apagá-lo seria perder a
        # lição.
        for linha in t.splitlines():
            limpa = linha.strip()
            if limpa.startswith(("//", "*", "/*", "#", "<!--")):
                continue
            self.assertNotIn(
                "/api/ia/super/",
                limpa,
                f"a rota inventada voltou em código: {limpa[:90]}",
            )
        self.assertIn(
            "if (!r.ok)",
            bloco,
            "o NDVI faz `r.json()` sem verificar `r.ok`. Um 404 devolve HTML e "
            "`r.json()` lança — o `catch` entrava em vez de dizer o que houve.",
        )

    def test_a_voz_diz_que_nao_grava(self):
        """Reconhecimento de voz que «fala com o sistema» sem dizer que não
        grava nada é uma promessa implícita.

        O produtor ouve «Gravado» e saúda-se. Aqui diz-se o contrário.
        """
        t = texto()
        self.assertIn(
            "Nada foi gravado",
            t,
            "a ferramenta de voz não avisa que não escreve na base. "
            "O produtor tem de saber antes de falar, não depois.",
        )
