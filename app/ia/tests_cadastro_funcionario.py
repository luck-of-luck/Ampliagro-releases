"""Uma pessoa não é uma máquina. E "faqueiro" é "vaqueiro".

Tudo o que este ficheiro cobre vem de uma conversa real entre um produtor
e a IA. As palavras do que ele viu estão nas docstrings, porque um teste
que diz "não deve falhar" sem dizer o que falhou não impede nada.

Os TRÊS erros que ele viu:

  1. "como se cadastrar um funcionário" respondeu com o wizard de
     MÁQUINAS — perguntou "informe: tipo". Não existia intent para
     cadastrar uma pessoa: havia `cadastrar_maquina` e `cadastrar_talhao`,
     e nada para `cadastrar_funcionario`. O que sobrava era máquina.

  2. "faqueiro" foi rejeitado três vezes seguidas com a mesma mensagem,
     como se a pessoa estivesse a inventar uma palavra. Não estava: estava
     a escrever "vaqueiro" com a v trocada. O `difflib` encontra-o com
     cutoff 0.6 — e não era usado.

  3. A pergunta repetiu-se: "Qual o nome?" → Carlos → "✓ Nome: Carlos
     Cargo Salário Admissão Qual o nome?".
"""

import unittest

from app.ia.intents3 import (
    _CARGOS,
    _CARGOS_NAO_PESSOA,
    INTENTS3,
    _corrigir_cargo,
    _nome_cargo,
)


class ExisteIntentDePessoa(unittest.TestCase):
    """O bug de raiz: não havia onde registar uma PESSOA."""

    def test_existe_cadastrar_funcionario(self):
        self.assertIn(
            "cadastrar_funcionario",
            INTENTS3,
            "Não há intent para cadastrar uma pessoa — sobra só o de máquina",
        )

    def test_o_handler_esta_ligado(self):
        """Um intent com `handler: None` existe e não executa. O sintoma
        é um cadastro que devolve None sem erro — a pior forma de falhar,
        porque parece que correu bem."""
        h = INTENTS3["cadastrar_funcionario"].get("handler")
        self.assertIsNotNone(h, "O intent existe mas não tem handler")
        self.assertTrue(callable(h))

    def test_pede_cargo_e_nao_tipo(self):
        """A diferença entre pessoa e máquina é o campo: pessoa tem
        cargo (vaqueiro), máquina tem tipo (trator)."""
        campos = INTENTS3["cadastrar_funcionario"]["required_fields"]
        self.assertIn("cargo", campos)
        self.assertNotIn(
            "tipo", campos, "Pediu 'tipo' a uma pessoa — é o campo da máquina"
        )

    def test_a_maquina_continua_intacta(self):
        """Não se resolve um bug de pessoa à custa de partir o de máquina."""
        m = INTENTS3["cadastrar_maquina"]
        self.assertEqual(m["required_fields"], ["nome", "tipo"])
        self.assertIsNotNone(m.get("handler"))

    def test_a_descricao_distingue_pessoa_de_maquina(self):
        """A descrição vai para o LLM. Se não disser a diferença, o erro
        volta pela mesma porta."""
        d = INTENTS3["cadastrar_funcionario"]["descricao"].lower()
        self.assertIn("pessoa", d)
        self.assertIn("maquina", d)


class ToleraErroDeDigitacao(unittest.TestCase):
    """'faqueiro' é 'vaqueiro' com a v trocada. Um carácter."""

    def test_o_erro_real_do_utilizador(self):
        canonico, perto = _corrigir_cargo("faqueiro")
        self.assertEqual(
            canonico, "VAQUEIRO", "Rejeitou 'faqueiro' como palavra inventada"
        )
        self.assertTrue(perto, "Deveria pedir confirmação, não gravar já")

    def test_o_termo_canonico_e_o_certo(self):
        """Devolve-se o termo verdadeiro, não o que o utilizador
        escreveu — o que vai para a base é 'VAQUEIRO', não 'faqueiro'."""
        canonico, _ = _corrigir_cargo("faqueiro")
        self.assertNotEqual(canonico, "FAQUEIRO")

    def test_o_cargo_certo_e_reconhecido_directamente(self):
        canonico, perto = _corrigir_cargo("vaqueiro")
        self.assertEqual(canonico, "VAQUEIRO")
        self.assertFalse(perto, "O termo exacto não deve pedir confirmação")

    def test_acento_nao_quebra(self):
        for escrito, esperado in (
            ("mecânico", "MECANICO"),
            ("mecanico", "MECANICO"),
            ("técnico agrícola", "TECNICO_AGRICOLA"),
            ("tecnico agricola", "TECNICO_AGRICOLA"),
        ):
            with self.subTest(escrito=escrito):
                self.assertEqual(_corrigir_cargo(escrito)[0], esperado)

    def test_sinonimo_mapeia_para_o_cargo_canonico(self):
        for sinonimo, esperado in (
            ("capataz", "GERENTE"),
            ("encarregado", "GERENTE"),
            ("boiadeiro", "VAQUEIRO"),
            ("auxiliar", "DIARISTA"),
        ):
            with self.subTest(sinonimo=sinonimo):
                self.assertEqual(_corrigir_cargo(sinonimo)[0], esperado)

    def test_uma_maquina_nao_e_um_cargo(self):
        """Isto é o bug de raiz, pelo outro lado: 'trator' tem de ser
        rejeitado como cargo, ou um produtor acaba com um trator na
        equipa. Uma máquina rejeitada é uma pessoa a registar o
        equipamento — e é o que levava a pessoa ao wizard errado."""
        for maquina in ("trator", "colheitadeira", "caminhao", "maquina", "drone"):
            with self.subTest(maquina=maquina):
                canonico, _ = _corrigir_cargo(maquina)
                self.assertIsNone(
                    canonico, f"Aceitou {maquina!r} como cargo de uma pessoa"
                )

    def test_maquinas_estao_no_lado_negativo(self):
        self.assertTrue(_CARGOS_NAO_PESSOA, "A lista de máquinas está vazia")


class PerguntaPeloCampoCerto(unittest.TestCase):
    """'faqueiro' não pode dar 'Não identifiquei a função' 3 vezes."""

    def test_o_termo_correto_existe_no_dicionario(self):
        """O que faz 'faqueiro' funcionar é existir 'vaqueiro' na lista. Se
        alguém limpar o dicionário, a tolerância a erro deixa de servir
        para alguma coisa — e o teste abaixo passa a falhar sem dizer
        porque."""
        self.assertIn(
            "vaqueiro",
            _CARGOS,
            "O dicionário de cargos não tem 'vaqueiro' — a correcção de "
            "'faqueiro' deixou de ter contra o que corrigir",
        )

    def test_nome_do_cargo_para_texto(self):
        """'VAQUEIRO' tem de aparecer como 'vaqueiro' na conversa — o
        utilizador lê isto, não o constant do código."""
        self.assertEqual(_nome_cargo("VAQUEIRO"), "vaqueiro")
        self.assertEqual(_nome_cargo("TECNICO_AGRICOLA"), "técnico agrícola")

    def test_cargo_desconhecido_nao_revela_internals(self):
        canonico, _ = _corrigir_cargo("astrob Repair-Man do ano 3000")
        self.assertIsNone(canonico)
