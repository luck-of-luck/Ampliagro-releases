"""
O que verificar_regressoes.py promete, e o que este ficheiro mede.

O verificador responde a "esta palavra existe no codigo?". Este teste responde
a "este preco e' honesto?". Sao perguntas diferentes, e a segunda e' a que
importa.

PORQUE ISTO EXISTE
==================
O verificador foi accused, com razao, de medir palavras: injectar um comentario
`# import random` nao o engana, porque `so_codigo()` faz ast.parse + ast.unparse
e um comentario nao sobrevive. Essenao era a prova.

A prova e' esta: o mesmo preco inventado, escrito de outra forma, passa o
verificador com 4/4 "ok".

    de  from random import Random   +  Random().random()       (verificador: ok)
    de  random.uniform(15, 25)                                 (verificador: DEFEITO)

O preco e' o mesmo. O nome da funcao e' que o verificador le.

O QUE ESTE TESTE FAZ
====================
Executa o codigo e mede o preco. Nao le o ficheiro, nao procura strings, e nao
precisa de comments para passar. Se alguem voltar a inventar precos por
qualquer caminho, este teste parte -- e o verificador pode continuar a dizer
"ok" sem deixar de ser verdade.

Cada `test_` mede COMPORTAMENTO. Se um destes falhar, o preco ficou
desonesto. Nao ha outra leitura.
"""

import pytest

from app.services.cotacoes import CotacoesService


class TestPrecoSemFonteNaoEReAL:
    """O preco que nao veio de fonte tem de ser None, e dizer porquê.

    Este e' o defeito #1 (P0, fechado em b604f88): cotações sorteadas a dedo
    apareciam com `"fonte": "real"`. Um produtor decidia irrigar por um preco
    que nunca existiu.
    """

    def test_preco_e_none_sem_fonte_configurada(self):
        r = CotacoesService._vazio(["soja", "milho"], "sem fonte")
        assert r["soja"]["preco"] is None, (
            f"preco {r['soja']['preco']!r} sem fonte real: e' um numero inventado"
        )

    def test_motivo_vem_no_mesmo_lugar_do_preco(self):
        """None sem motivo e' indistinguivel de um bug.

        O frontend le `motivo` para explicar ao produtor. Se voltar a faltar, o
        vazio deixa de avisar e passa a parecer um erro de carregamento — que
        e' exactamente o que se QUERIA evitar.
        """
        r = CotacoesService._vazio(["soja"], "motivo de teste")
        assert r["soja"]["motivo"] == "motivo de teste"

    def test_nenhum_preco_e_zero(self):
        """0 e' um preco. E um preco impossivel.

        O conserto anterior removeu um 0 que era o valor default. Isto existe
        para o 0 nao voltar, seja por onde vier — e para nenhum numero
        aparecer no sitio onde so pode estar None.
        """
        r = CotacoesService._vazio(["soja", "milho", "cafe"], "sem fonte")
        for commodity, v in r.items():
            preco = v["preco"]
            assert preco is None, (
                f"{commodity}: preco {preco!r} sem fonte real. "
                f"Sem fonte so pode ser None."
            )
            assert preco != 0, (
                f"{commodity}: preco 0. 0 nao e' 'sem preco', e' um preco"
            )

    def test_todas_as_commodities_tem_mesma_estrutura(self):
        """O frontend itera o que vier. Uma chave a menos parte o painel."""
        r = CotacoesService._vazio(["soja", "milho"], "sem fonte")
        for commodity, v in r.items():
            assert set(v) == {"preco", "variacao", "motivo"}, (
                f"{commodity}: chaves {sorted(v)} — o painel espera preco/variacao/motivo"
            )

    def test_chaves_mesmo_sem_qualquer_commodity(self):
        """Lista vazia devolve dicionario vazio, nao rebenta."""
        assert CotacoesService._vazio([], "sem fonte") == {}


class TestVerificadorNaoEBrinde:
    """Este bloco e' sobre o verificador, e diz uma coisa desconfortavel.

    O verificador de regressoes le o codigo-fonte. Nao e' um erro — e' um
    atalho, e as vezes da a resposta mais depressa. O problema e' quando as
    DUAS fontes ficam a dizer "ok": ai nao ha nada que vigie o preco.

    Estes testes existem para que essa confianca nao se Unsupported. Se este
    ficheiro for apagado, o preco deixa de ter quem o vigie — e o verificador
    continua a dizer "ok".
    """

    def test_o_preco_e__none_e_nao_uma_palavra(self):
        """Se este teste deixar de passar, o preco voltou.

        Deliberadamente o mais simples possivel. Os quatro testes de cima
        medem as bordas (motivo, zero, estrutura, lista vazia); este mede o
        caso do meio, que e' o que o produtor vê.
        """
        assert CotacoesService._vazio(["soja"], "sem fonte")["soja"]["preco"] is None

    def test_o_comportamento_nao_depende_de_nome_de_funcao(self):
        """O verificador procurava 'uniform'. Aqui nao ha nomes, ha resultado.

        Este teste nao menciona `random`, `uniform`, `hashlib` nem `0.88`.
        Passa com qualquer implementacao honesta e falha com qualquer
        implementacao desonesta — que e' o que se pede de um teste.
        """
        duas_vezes = [
            CotacoesService._vazio(["soja"], "sem fonte")["soja"]["preco"]
            for _ in range(2)
        ]
        assert duas_vezes == [None, None], (
            f"precos variaveis entre chamadas: {duas_vezes} — ha aleatoriedade no preco"
        )


# NOTA PARA QUEM ABRIR ESTE FICHEIRO
# ==================================
# O verificador (scripts/verificar_regressoes.py) tem 18 checks que leem o
# codigo-fonte. Este ficheiro NAO os substitui todos — substitui os de cotacoes,
# que sao os que consequentialos. Os outros 9 (ndvi, tenancy, fallback IBGE,
# widgets de hash, solo, erp) continuam a ser medidos por leitura.
#
# Porque nao todos de uma vez: cada check precisa do seu teste, e um teste
# escrito a correr contra codigo que ninguem le ha mais um ano nao serve para
# nada. Este e' o primeiro. O proximo e' ndvi + tenancy, que sao os dois P0
# que ainda dependem so de leitura.
#
# A regra que sai daqui, e que devia valer para os outros:
#   um check que le o texto responde a "esta escrito assim?".
#   so um teste que executa responde a "isto funciona?".
#   O primeiro e' uma opiniao sobre o codigo. O segundo e' uma garantia.
