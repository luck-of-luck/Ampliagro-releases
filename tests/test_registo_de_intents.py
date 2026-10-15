"""O que o codigo declara chegou ao registo? Nada some em silencio.

MEDIDO 2026-10-05 (agente 3). Este teste nasceu de um numero mal posto.

Escrevi uma baseline de `87 intents` e ela FALHOU com `84 != 87`. A minha
primeira suspeita foi um defeito: tres capacidades perdidas em silencio.
Investigado: `app/ia/intents4.py:341` tem `except Exception: pass`, o unico
que engole em todo o `app/ia/`, e entrega os 9 que declara. Portanto o
defeito nao era esse — foram tres remocoes legitimas de outro agente, e o
meu numero estava simplesmente desatualizado.

Isso e' a conclusaoERRADA sobre o teste, e importa: **uma baseline com
numero fixo, num repositorio partilhado onde varios agentes mudam coisas,
nao mede nada. Quebra a cada alteracao legitima** — e um teste que quebra
sem razao ensina a ignorar o vermelho, que e' como um alarme se torna
decoracao.

O QUE ESTE TESTE MEDE EM VEZ DISSO
==================================
Compara DUAS coisas que deveriam ser iguais, e so elles:

    o que os ficheiros de `app/ia/intents*.py` DECLARAM
    o que `app.ia.intents.INTENTS` TEM

Se declaras um intent e ele nao chega ao registo, alguem comeu-o pelo
caminho — e esse e' exactamente o modo de falha que o `except Exception:
pass` esconde. A comparacao e' auto-mantida: nao precisa de numero, e
aguenta remocoes legitimas.

O QUE ESTE TESTE NAO FAZ
========================
Nao diz se 84 e' o numero certo. Nao pode: essa pergunta e' de quem
conhece o produto. Aqui so se responde a outra, que e' verificavel e de
machina: o registo bate com o fonte?
"""

import ast
import pathlib
import unittest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
MODULOS = sorted((RAIZ / "app/ia").glob("intents*.py"))


def declarados_no_fonte(caminho: pathlib.Path) -> set[str]:
    """Nomes de intent declarados no fonte.

    Le-se a AST e procuram-se dicts literais que sao atribuidos a um
    `INTENTS*`. Um dict literal tem chaves que sao strings constantes — e
    isso e' o que distingue "declaracao de intent" de qualquer outro dict.

    Deliberadamente NAO se usa regex: um nome de intent que apareca num
    comentario, ou numa string de exemplo, nao e' uma declaracao.
    """
    arvore = ast.parse(caminho.read_text(encoding="utf-8-sig"))
    nomes: set[str] = set()
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Assign):
            continue
        alvo = no.targets[0]
        if not isinstance(alvo, ast.Name) or not alvo.id.startswith("INTENTS"):
            continue
        if not isinstance(no.value, ast.Dict):
            continue
        for chave in no.value.keys:
            if isinstance(chave, ast.Constant) and isinstance(chave.value, str):
                nomes.add(chave.value)
    return nomes


def ids_registados_no_ficheiro(caminho: pathlib.Path) -> set[str]:
    """O que o modulo EXPORTA.

    Importa-se o modulo e le-se o atributo `INTENTS*` que ele define. Se o
    modulo engole a falha no registo, o que exporta e' menos do que
    declara — e e' essa a diferenca que este teste existe para ver.
    """
    import importlib

    mod = importlib.import_module(f"app.ia.{caminho.stem}")
    for nome in dir(mod):
        if nome.startswith("INTENTS") and isinstance(getattr(mod, nome), dict):
            return set(getattr(mod, nome))
    return set()


class OQueEstaDeclaradoChegaAoRegistoTest(unittest.TestCase):
    def test_existe_pelo_menos_um_modulo(self):
        self.assertTrue(MODULOS, "nenhum modulo de intents em app/ia/")

    def test_nada_declarado_desaparece(self):
        """O teste que a baseline devia ter sido.

        Um intent declarado num ficheiro e' uma promessa feita ao produtor.
        Se nao chega a `INTENTS`, a promessa esta' a mais.
        """
        from app.ia.intents import INTENTS

        perdidos: dict[str, list[str]] = {}
        por_modulo: dict[str, int] = {}

        for caminho in MODULOS:
            fonte = declarados_no_fonte(caminho)
            if not fonte:
                continue
            exportado = ids_registados_no_ficheiro(caminho)
            por_modulo[caminho.stem] = len(exportado)
            em_falta = sorted(fonte - exportado)
            if em_falta:
                perdidos[caminho.stem] = em_falta

        self.assertEqual(
            perdidos,
            {},
            "intents declarados no fonte que NAO chegam ao modulo:\n"
            + "\n".join(
                f"  {mod}: {', '.join(n)}" for mod, n in sorted(perdidos.items())
            )
            + "\n\nIsto e' o `except Exception: pass` a trabalhar: o ficheiro "
            "declara, o modulo engole a falha, e o produtor fica sem a "
            "capacidade e sem aviso.",
        )

    def test_o_registo_agregado_tem_tudo_o_que_os_modulos_exportam(self):
        """Segunda metade: os modulos exportam, o agregador recolhe?"""
        from app.ia.intents import INTENTS

        agregado: set[str] = set()
        por_modulo: dict[str, int] = {}
        for caminho in MODULOS:
            exportado = ids_registados_no_ficheiro(caminho)
            if exportado:
                por_modulo[caminho.stem] = len(exportado)
                agregado |= exportado

        self.assertTrue(agregado, "nenhum modulo exporta intents")
        em_falta = sorted(agregado - set(INTENTS))
        self.assertEqual(
            em_falta,
            [],
            f"{len(em_falta)} intents que os modulos exportam e o agregador "
            f"nao tem: {', '.join(em_falta[:12])}",
        )

    def test_a_leitura_dos_ficheiros_encontra_algo(self):
        """Auto-teste do auto-teste.

        Um detector que devolve sempre um conjunto vazio passa em todos os
        testes acima — e era exactamente o modo de falha que este ficheiro
        cameca a corrigir. Se `declarados_no_fonte` nao encontra nada, ele
        esta' errado, e isto diz.
        """
        total = sum(len(declarados_no_fonte(c)) for c in MODULOS)
        self.assertGreater(
            total,
            50,
            "declarados_no_fonte devolveu quase nada. Ou os modulos mudaram "
            "de forma, ou o detector esta' errado — e um detector errado "
            "faz os testes passarem sem verificar nada.",
        )
