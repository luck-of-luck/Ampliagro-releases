"""A verificacao de CARGO do `mover` nao pode falhar para o lado permissivo.

ESTE TESTE LE O FONTE. NAO EXECUTA O CAMINHO. E ISTO E' IMPORTANTE
===================================================================
Digo isto na primeira linha porque um teste que parece provar uma coisa e
nao prova e' pior do que nenhum teste: da confianca falsa.

O QUE TENTEI, E PORQUE NAO CHEGOU AO `try`
===========================================
O objectivo era correr `mover` de ponta a ponta com o perfil a rebentar
dentro do `try`, e confirmar que a tarefa nao era gravada. Nao foi
possivel, e a razao e' um defeito QUE VIVE ANTES DO CODIGO DESTE
COMMIT:

  `TarefaEstagioViewSet.get_queryset()` le `user.perfil` dentro de um
  `try/except: pass`. Quando o perfil falha, ele engole o erro e cai no
  ramo de fallback. O `get_object()` corre ANTES do `mover`, e por isso o
  pedido morre (403 ou 404) sem nunca entrar no `try` do `mover`.

MEDIDO: com o perfil intacto e um servidor com `area_servidor="GERAL"`, o
`mover` responde 403 e a tarefa fica `pendente`. Ou seja: o caminho nem
sequer chega a `tarefa.save()` com dados normais, o que impede construir
o cenario "verificacao rebenta DEPOIS de o `get_object` passar".

Isto NAO anula a correccao. O `except Exception: pass` seguido de
`tarefa.save()` existia, e devolve 200 se alguma vez for alcancado. Este
teste trava a ESTRUTURA; a prova de execucao depende de o `get_queryset`
ser corrigido primeiro (ver `LIMITE` no fim).

LIMITE CONHECIDO, DITO COM CLAREZA
==================================
`get_queryset` engole o erro do perfil. Isso e' uma falha SEPARADA, com
o seu proprio ficheiro de teste, e NINGUEM a corrigiu ainda. Este commit
nao a trata e nao finge que a trata.
"""

import inspect
import unittest

from app.api.views.production import TarefaEstagioViewSet


def fonte_normalizada():
    """O fonte do `mover` numa so linha.

    O codigo e' escrito com strings partida em varias linhas (a convencao
    do `ruff format`), o que parte qualquer frase no meio:

        "a verificacao de CARGO falhava para o lado "
        "permissivo. A correccao e' na base/perfil..."

    Um `assertIn("lado permissivo", fonte)` falha, porque no fonte essa
    frase nao existe -- ela existe na CONCATENACAO. Foi assim que tres
    destes testes deram falso vermelho contra um codigo correcto.

    Concatenar primeiro e' o que torna a verificacao correcta.
    """
    return " ".join(inspect.getsource(TarefaEstagioViewSet.mover).split())


def saves_de_codigo(texto):
    """Onde `tarefa.save()` e' CHAMADA, e nao MENCIONADO numa string.

    A distincao e' SIMPLES e nao e' heuristica: a mencao no log vem
    sempre entre CRASES (o `ruff format` nao mexe em crases dentro de uma
    string), ou seja `...para `tarefa.save()` com...`. Uma chamada a
    `save` como codigo nunca tem crases.

    Heuristica anterior (procurar `(` ou `=` antes) falhava porque, no
    fonte normalizado, a mencao acabava em crase e nao em `(` — a crase
    e' o marcador certo.
    """
    achados = []
    pos = 0
    while True:
        k = texto.find("tarefa.save()", pos)
        if k == -1:
            break
        antes = texto[:k].rstrip()
        # se a crase imediatamente anterior, e' mencao, nao codigo
        e_mencao = antes.endswith("`")
        if not e_mencao:
            achados.append(antes[-46:])
        pos = k + 1
    return achados


class MoverFalhaPermissaoTest(unittest.TestCase):
    """Estrutura do `except`. NAO e' um teste de execucao."""

    def test_o_except_devolve_503_e_nao_passa(self):
        fonte = fonte_normalizada()
        self.assertIn(
            "status=503",
            fonte,
            "o `except` do `mover` tem de devolver 503. Sem isso, um erro na "
            "verificacao de permissao volta a dar 200 e a gravar a tarefa.",
        )
        depois = fonte.split("except Exception as exc")[-1][:260]
        self.assertNotIn(
            "pass ",
            depois,
            "o `except` volta a ser um `pass`. Era exactamente o bug: a "
            "verificacao de cargo falhava e a tarefa era gravada na mesma.",
        )

    def test_o_save_e_sempre_depois_do_return_do_except(self):
        """O `tarefa.save()` tem de estar no caminho NORMAL.

        O `except` MENCIONA `tarefa.save()` na mensagem de log, para
        explicar o que a versao antiga fazia. Essa mencao nao e' codigo.
        Por isso este teste ve a POSICAO: um `save` de CODIGO (nao
        mencao) tem de estar DEPOIS do `return` que fecha o `except`.
        """
        depois = fonte_normalizada().split("except Exception as exc")[-1]

        return_except = depois.find("return Response(", depois.find("503"))
        self.assertNotEqual(return_except, -1, "o except tem de devolver algo")

        antes_do_return = depois[:return_except]
        achados = saves_de_codigo(antes_do_return)
        self.assertFalse(
            achados,
            f"o `tarefa.save()` esta a correr DENTRO do tratamento de erro "
            f"(apos: {achados!r}). O `except` esta a gravar a tarefa, que "
            f"e' o oposto do que deve fazer.",
        )

        depois_do_return = depois[return_except:]
        self.assertTrue(
            saves_de_codigo(depois_do_return),
            "o `tarefa.save()` do caminho normal desapareceu.",
        )

    def test_a_mensagem_diz_que_nao_se_sabe_e_nao_que_nao_pode(self):
        """503 e' "nao sei", 403 e' "nao pode". Nao se podem trocar.

        Se o 503 disser "sem permissao", o servidor vai pedir ao dono da
        fazenda para_the dar permissao -- e o problema nao e' permissao,
        e' uma falha de leitura do perfil.
        """
        fonte = fonte_normalizada()
        self.assertIn(
            "Nao foi possivel verificar",
            fonte,
            "a mensagem de 503 tem de dizer que NAO SE CONSEGUIU VERIFICAR.",
        )
        bloco_503 = fonte.split("except Exception as exc")[-1].split("status=503")[0]
        for acusacao in ("Sem permissao: tarefa", "nao e' da sua fazenda"):
            self.assertNotIn(
                acusacao,
                bloco_503,
                f"o `except` de 503 acusa o utilizador: {acusacao!r}. O que "
                f"nao se sabe e' a permissao, nao o resultado.",
            )

    def test_o_log_diz_que_a_versao_anterior_gravava(self):
        """O log tem de dizer PORQUE este codigo existe.

        Um log que regista "erro" sem dizer o que o erro custava e' um log
        que se le e se esquece. Foi assim que o fail-open do middleware
        sobreviveu meses: estava la, a dizer que corria mal, e ninguem leu.
        """
        bloco = fonte_normalizada().split("except Exception as exc")[-1]
        self.assertIn(
            "a verificacao de CARGO falhava para o lado",
            bloco,
            "o log tem de dizer que a versao anterior falhava para o lado "
            "permissivo. E' o aviso que impede isto de ser achado de novo "
            "daqui a um ano.",
        )
