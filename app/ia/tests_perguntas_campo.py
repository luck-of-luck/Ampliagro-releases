"""Perguntar por um campo é trabalho, e não é o mesmo que dizer o nome dele.

Onze campos pedidos por algum intent não tinham pergunta própria, e caíam
num `f"Por favor, informe: {campo}."`.

O caso que dói é `tipo`. Um produtor que queria registar um vaqueiro leu
"informe: tipo", respondeu "vaqueiro" — a resposta certa para a pergunta
ERRADA — e ouviu "tipo inválido — use: trator, colheitadeira, pulverizador,
caminhão…".

Três coisas faltavam, e as três são o mesmo trabalho:
  1. dizer o que o campo SIGNIFICA
  2. dizer o que uma resposta VÁLIDA parece
  3. não repetir o nome do campo a quem não o conhece

O teste mais importante é o último. Uma pergunta que contém o identificador
que a pessoa não conhece é um bugreport: obriga a traduzir `xyz` para
linguagem, que é trabalho do sistema, não de quem está a aprender a
usá-lo.
"""

import re
import unittest

from app.ia import registro as R
from app.ia.sandbox import _PERGUNTAS_CAMPO, _perguntar_por


class APerguntaExplicaEmVezDeApontar(unittest.TestCase):
    def test_nenhum_campo_cai_no_fstring(self):
        """O `f"informe: {campo}."` era o sintoma. Se voltar, a
        verificação abaixo não passa."""
        import inspect

        from app.ia import sandbox

        fonte = inspect.getsource(sandbox)
        codigo = "\n".join(
            l for l in fonte.splitlines() if not l.strip().startswith("#")
        )
        self.assertNotIn(
            'f"Por favor, informe: {campo',
            codigo,
            "A pergunta voltou a repetir o nome do campo",
        )

    def test_todo_campo_pedido_tem_pergunta(self):
        """A cobertura que faltava: cada `required_fields` de algum intent
        tem de ter pergunta. Onze não tinham."""
        campos = set()
        for spec in R.REGISTO.values():
            campos.update(spec.get("required_fields", []) or [])
        sem = sorted(c for c in campos if c not in _PERGUNTAS_CAMPO)
        self.assertEqual(
            sem,
            [],
            f"Campos pedidos e sem pergunta: {sem} — caem no "
            "'Por favor, informe: <o nome do campo>'",
        )

    def test_cargo_pergunta_a_funcao_com_exemplos(self):
        """A pergunta que faltava na conversa. `cargo` dizia "informe:
        cargo", e a pessoa respondeu com a função."""
        p = _perguntar_por("cargo", "cadastrar_funcionario")
        self.assertIn("função", p.lower(), "Não diz o que se quer saber")
        for exemplo in ("tratorista", "vaqueiro", "diarista"):
            self.assertIn(exemplo, p, f"A pergunta não dá o exemplo {exemplo!r}")

    def test_tipo_pergunta_com_exemplos_de_maquina(self):
        p = _perguntar_por("tipo", "cadastrar_maquina")
        for exemplo in ("trator", "colheitadeira"):
            self.assertIn(exemplo, p, f"A pergunta não dá o exemplo {exemplo!r}")

    def test_tipo_noutro_intent_nao_fala_de_maquina(self):
        """A mesma palavra, outra pergunta. `tipo` em `cadastrar_maquina` é
        equipamento; noutro lugar pode ser outra coisa — e dizer "trator"
        ali é inventar contexto."""
        p = _perguntar_por("tipo", "meu_intent")
        self.assertNotIn(
            "colheitadeira", p, "Diz 'colheitadeira' num intent que não é de máquina"
        )


class APerguntaNaoExigeTraduzir(unittest.TestCase):
    def test_nenhuma_pergunta_reparte_o_identificador(self):
        """A regra: a pergunta não pode repetir o campo quando ele é um
        IDENTIFICADOR.

        A distinção importa. `brinco` é uma palavra que qualquer pessoa lê
        como uma coisa que se prende ao animal. `area_plantada` e
        `pct_travado` são identificadores: quem os vê tem de saber que
        `pct_travado` quer dizer percentagem de producto travado, e isso
        é trabalho do sistema, não de quem está a aprender a usar a
        ferramenta.

        `campo` fica de fora de propósito — é palavra, e a pergunta
        "De que campo?" é legítima.
        """
        identificadores = ("area_plantada", "data_admissao", "pct_travado")
        for campo in identificadores:
            with self.subTest(campo=campo):
                p = _perguntar_por(campo, "cadastrar_safra")
                self.assertNotIn(
                    campo,
                    p,
                    f"A pergunta repete o identificador {campo!r} — a pessoa "
                    f"terá de adivinhar o que significa: {p[:70]!r}",
                )

    def test_o_underscore_vira_espaco(self):
        p = _perguntar_por("area_plantada", "cadastrar_safra")
        self.assertNotIn("_", p, "O identificador chegou à pergunta com o underscore")

    def test_uma_pergunta_sem_conhecer_o_campo_ainda_pergunta(self):
        """Campo que não está no mapa: perguntar melhor do que repetir o
        nome. A pergunta anterior era literalmente o campo com um ponto
        final."""
        p = _perguntar_por("xyz_que_nao_existe", "meu_intent")
        self.assertNotEqual(p, "Por favor, informe: xyz_que_nao_existe.")
        self.assertIn("xyz que nao existe", p.replace("_", " "))

    def test_a_resposta_nao_e_o_nome_do_campo(self):
        """Nenhuma das perguntas do mapa pode ser o campo devuelto com
        dois pontos — que é o defeito original."""
        padrao = re.compile(r"^Por favor, informe: .+\.$")
        for campo, pergunta in _PERGUNTAS_CAMPO.items():
            with self.subTest(campo=campo):
                self.assertFalse(
                    padrao.match(pergunta),
                    f"A pergunta de {campo!r} ainda e' o defeito: {pergunta!r}",
                )
