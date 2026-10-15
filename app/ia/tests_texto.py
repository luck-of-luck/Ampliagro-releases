"""Testes do texto que o produtor lê, e do texto que o modelo lê.

A distinção é o ponto inteiro de `app/ia/texto.py`: um intent tem UMA
descrição, escrita PARA O MODELO ("INSTRUÇÃO IA: use para..."), e o sandbox
reutilizava-a como pergunta PARA A PESSOA. Ninguém decidiu isso — a descrição
estava certa para o modelo, e o sandbox fez o que lhe deram.

Estes testes existem para que as duas metades não voltem a ser uma.
"""

from django.test import SimpleTestCase

from app.ia.registro import REGISTO
from app.ia.texto import (
    RE_INSTRUCAO,
    descricao_humana,
    prompt_de_confirmacao,
    sem_instrucao,
)


class PrefixoInstrucaoTest(SimpleTestCase):
    """O regex que separa a instrução ao modelo da descrição útil."""

    def test_tira_o_prefixo_com_dois_pontes(self):
        m = RE_INSTRUCAO.match("INSTRUÇÃO IA: use para 'x'.")
        self.assertIsNotNone(m)
        self.assertEqual(sem_instrucao("INSTRUÇÃO IA: use para 'x'."), "use para 'x'.")

    def test_tira_o_prefixo_com_parenteses_antes_dos_dois_pontes(self):
        """O caso que `startswith` não apanhava.

        `feedback` começa com "INSTRUÇÃO IA (ML):". Com `.startswith()` não
        casava, e o texto interno ia parar ao `o_que_faz` que o modelo lê —
        foi o único de 80 a vazar.
        """
        self.assertEqual(
            sem_instrucao("INSTRUÇÃO IA (ML): usuário satisfeito"),
            "usuário satisfeito",
        )

    def test_nao_toca_em_texto_sem_prefixo(self):
        self.assertEqual(
            sem_instrucao("Lista automações 20 RegraAuto."),
            "Lista automações 20 RegraAuto.",
        )

    def test_aceita_as_variantes_de_acento(self):
        for variante in ("INSTRUÇÃO IA:", "INSTRUCAO IA:", "instrução ia:"):
            self.assertIsNotNone(RE_INSTRUCAO.match(variante), variante)


class DescricaoHumanaTest(SimpleTestCase):
    def test_tira_prefixo_e_ixa_a_primeira_frase(self):
        spec = {"descricao": "INSTRUÇÃO IA: use para x. E depois uma segunda frase."}
        self.assertEqual(descricao_humana(spec), "use para x.")

    def test_corta_a_espaco_maximo(self):
        spec = {"descricao": "INSTRUÇÃO IA: " + "x" * 500}
        self.assertLessEqual(len(descricao_humana(spec)), 160)

    def test_sem_descricao_nao_inventa_texto(self):
        """Um prompt inventado é pior que um feio: pode prometer o que o
        código não faz. Vazio é a resposta honesta."""
        self.assertEqual(descricao_humana({}), "")
        self.assertEqual(descricao_humana({"descricao": ""}), "")

    def test_usa_o_bloco_antes_da_linha_em_branco(self):
        spec = {"descricao": "INSTRUÇÃO IA: a parte útil.\n\nnota interna de uso"}
        self.assertEqual(descricao_humana(spec), "a parte útil.")


class PromptDeConfirmacaoTest(SimpleTestCase):
    def test_prefers_o_campo_do_autor(self):
        spec = {
            "descricao": "INSTRUÇÃO IA: instrucao para o modelo",
            "prompt_confirmacao": "Apagar a safra soja 2026/27?",
        }
        self.assertEqual(prompt_de_confirmacao(spec), "Apagar a safra soja 2026/27?")

    def test_cai_na_descricao_limpa_quando_nao_ha_campo(self):
        spec = {"descricao": "INSTRUÇÃO IA: use para 'apagar a safra'."}
        self.assertEqual(prompt_de_confirmacao(spec), "use para 'apagar a safra'.")


class NenhumPromptVazaInstrucaoTest(SimpleTestCase):
    """O teste que importa, e que é sistémico.

    Não testa um intent — testa todos os que pedem confirmação. O defeito
    foi sempre sistémico: um campo descrição a ser mostrado a quem não
    deveria lê-lo atinge todos de uma vez.
    """

    def _confirmacoes(self):
        return [n for n, s in REGISTO.items() if s.get("requires_confirmation")]

    def test_ha_intents_para_testar(self):
        """Se este teste passar com zero intents, não está a testar nada."""
        self.assertGreater(len(self._confirmacoes()), 5)

    def test_nenhum_prompt_de_confirmacao_vaza_instrucao_interna(self):
        vazam = []
        for nome in self._confirmacoes():
            texto = prompt_de_confirmacao(REGISTO[nome])
            if "INSTRU" in texto:
                vazam.append((nome, texto[:60]))
        self.assertEqual(vazam, [], f"instrução interna mostrada ao produtor: {vazam}")

    def test_toda_escrita_tem_prompt_proprio(self):
        """O fallback existe para intents novos não partirem sem texto.

        Mas toda a escrita tem o seu: o que é uma regra do autor, e é isso
        que faz a pergunta ser boa. Um fallback funciona, mas é uma
        descrição transformada em pergunta — e o autor sabe mais.
        """
        sem = [
            n
            for n in self._confirmacoes()
            if not str(REGISTO[n].get("prompt_confirmacao") or "").strip()
        ]
        self.assertEqual(sem, [], f"escritas sem prompt de confirmação próprio: {sem}")
