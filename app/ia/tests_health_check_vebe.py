"""Este teste nao apanha o bug anterior. E' sobre isso que ele existe.

MEDIDO 2026-10-05: `intents_comparativo` nao terminava em nenhum sufixo de
`_SUFIXOS`, por isso nao entrava em `ESPERADO`. O intent chegava ao REGISTO
na mesma — `app/ia/intents.py` importa-o e faz `INTENTS.update(...)`.

Resultado: a capacidade FUNCIONAVA e `saude()["integro"]` dizia True. O
health check, que existe para dizer "a IA esta cega para parte do que sabe
fazer", via tudo enquanto um catalogo lhe era invisivel.

E porque e' preciso um teste deste genero: qualquer teste que leia `REGISTO`
passa. O intent esta la. So a RELACAO entre o que existe em disco e o que o
health check considera esta em jogo.
"""

import pkgutil
import unittest

from app.ia import registro


class OHealthCheckVebeTest(unittest.TestCase):
    def test_todo_modulo_de_intents_e_visivel_ao_health_check(self):
        """Nenhum `intents*.py` em disco pode ser invisivel ao `saude()`."""
        import app.ia

        em_disco = {
            i.name
            for i in pkgutil.iter_modules(app.ia.__path__)
            if registro._e_catalogo(i.name)
        }
        self.assertTrue(
            em_disco,
            "a introspeccao nao devolveu nenhum catalogo — o teste passaria "
            "a vazio, que e' a pior forma de um teste de integridade",
        )
        self.assertEqual(
            sorted(registro.ESPERADO),
            sorted(em_disco),
            "modulos de catalogo que o health check nao ve. `saude()` diria "
            "`integro: True` com a IA cega para eles.",
        )

    def test_intents_comparativo_e_visivel(self):
        """O modulo concreto onde o bug estava, para a regressao ser nomeada."""
        self.assertIn(
            "intents_comparativo",
            registro.ESPERADO,
            "`intents_comparativo` nao e' visivel ao health check. O intent "
            "`comparativo_revisao` continua a funcionar porque `intents.py` "
            "o importa — e e' por isso que este bug pode durecer: a "
            "capacidade funciona, e quem testa capacidades nao nota.",
        )

    def test_o_prefixo_agarraria_o_nome(self):
        """A regra do nome, testada nos dois sentidos.

        A lista de sufixos falhava porque `endswith('_intents')` nao casa com
        `intents_comparativo`. A regra nova casa com qualquer `intents*`.
        """
        for nome, esperado in (
            ("intents", True),
            ("intents2", True),
            ("intents3", True),
            ("intents4", True),
            ("intents_comparativo", True),
            ("chamado_intents", True),
            ("contas_intents", True),
            ("iot_intents", True),
            ("proativo_intents", True),
            ("dinamico_intents", True),
            # e o que NAO e' catalogo:
            ("registro", False),
            ("sandbox", False),
            ("skills", False),
            ("validators", False),
            ("proveniencia", False),
            ("tests", False),
        ):
            with self.subTest(modulo=nome):
                self.assertEqual(registro._e_catalogo(nome), esperado)

    def test_saude_nao_diz_ver_quando_ha_catalogo_cego(self):
        """Simula um catalogo que nao carregou, e exige que `saude()` o diga.

        Sem esta mutacao, `integro: True` continua a ser o valor por omissao
        e o teste acima so prova que a lista bate — nao que o alarme dispara.
        """
        original = registro.CARREGADOS.copy()
        try:
            registro.CARREGADOS.discard("intents_comparativo")
            s = registro.saude()
            self.assertFalse(
                s["integro"],
                "com um catalogo fora de CARREGADOS, `integro` tem de ser "
                "False. Se e' True, o health check nao ve falhas — e um "
                "alarme que nunca toca e' pior do que nao existir.",
            )
            self.assertIn("intents_comparativo", s["falhou"])
        finally:
            registro.CARREGADOS.clear()
            registro.CARREGADOS.update(original)


if __name__ == "__main__":
    unittest.main()
