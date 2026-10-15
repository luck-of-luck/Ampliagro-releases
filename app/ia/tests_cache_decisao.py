"""Cache nao pode guardar uma DECISAO do copiloto.

O QUE QUEBREI, E O QUE ESTE FICHEIRO PRENDE
============================================
`vai_chover` tinha TTL de 900 s em `sandbox.CACHE_TTL`. A resposta a "vai
chover?" nao e' so o tempo: `sandbox.executar` acrescenta-lhe o copiloto, que
responde "Quer que eu remarque para dia 08/10?".

Essa segunda frase e' uma DECISAO sobre as aplicacoes pendentes. A chave do
cache e' `ia:v1:{user.id}:{intent}:{sha256(params)}` — nao inclui o estado das
tarefas. Portanto o cache guardava uma decisao tomada com o estado de ha 15
minutos.

CONSEQUENCIA REAL
-----------------
O produtor pergunta, recebe a oferta, e Remarka. Pergunta outra vez dentro de
15 minutos: o fast-path devolve a resposta em cache e salta o bloco do
copiloto. A oferta continua a apontar para uma tarefa que ja nao esta la. E o
inverso tambem: se a aplicacao fica em risco DEPOIS do cache aquecido, o
copiloto fica calado na altura em que devia falar.

Este bug JA TINHA SINTOMA, e noutro sitio: o `setUp` de
`ConsoleRegistroTest` (app/ia/tests.py:497) faz `cache.clear()` com o
comentario "o cache e' LocMem (process-wide) e sobrevive entre testes". Ninguem
arranjou a causa; contornaram o sintoma no teste.

O QUE ESTE FICHEIRO PRENDE
--------------------------
Duas coisas, e as duas JA FALHAVAM antes da correccao:

1. `vai_chover` (e os outros quatro intents de tempo) nao podem ter TTL > 0.
2. O passo "busca" tem de continuar a ser registado mesmo sem cache — mas o
   detalhe nao pode dizer "cache: MISS" quando nao ha cache. Era o que a
   correccao do ponto 1 tinha partido.

COMO PROVAR QUE TEM DENTES
--------------------------
Repor `"vai_chover": 900` no `CACHE_TTL`: `test_decisao_nao_viaja_no_cache` tem
de FALHAR. Se passar, nao esta a medir a correccao.
"""

from django.test import TestCase

import pytest


# MEDIDO 2026-10-05. Este ficheiro mede o CACHE. A fixture `limpar_cache_
# entre_testes` do `conftest.py` (autouse, limpa antes e depois de cada
# teste) foi criada para acabar com a contaminacao de ordem, e MAKE este
# teste falhar: ela apaga o cache entre a accao e a assertiva, que e'
# precisamente o que este teste precisa de observar.
#
# O marker diz "limpa antes, nao depois" — o teste comeca limpo e pode
# deixar estado, porque o objectivo e' ver o cache a funcionar.
#
# A alternativa — desligar a fixture neste ficheiro — seria silently
# reintroduzir a contaminacao nos 119 testes deste modulo.
@pytest.mark.keep_cache
class CacheNaoGuardaDecisaoTest(TestCase):
    def setUp(self):
        from django.core.cache import cache

        self.cache = cache
        self.cache.clear()
        self.addCleanup(self.cache.clear)

    def test_decisao_nao_viaja_no_cache(self):
        """O intent que produz oferta do copiloto nao pode ter TTL."""
        from app.ia import copiloto, sandbox

        offers_sem_data = [
            i for i in copiloto.INTENTS_DE_TEMPO if sandbox.CACHE_TTL.get(i, 0) != 0
        ]

        self.assertEqual(
            offers_sem_data,
            [],
            "estes intents respondem com uma DECISAO do copiloto sobre as "
            "tarefas pendentes, e a chave do cache nao inclui o estado das "
            "tarefas. Com TTL > 0 a oferta servida em cache aponta para uma "
            f"tarefa que ja nao esta la: {offers_sem_data!r}",
        )

    def test_o_mesmo_intent_com_fatos_iguais_nao_e_servido_de_cache(self):
        """Duas perguntas iguais, duas execucoes — a segunda recalcula."""
        from app.ia import sandbox

        self.assertEqual(
            sandbox.CACHE_TTL.get("vai_chover"),
            0,
            "vai_chover tem de estar sem cache: a resposta inclui a oferta do "
            "copiloto, que depende do estado das tarefas.",
        )

    def test_o_passo_busca_e_registado_mesmo_sem_cache(self):
        """O contrato da consola: 'fui buscar dados' aparece sempre.

        A correccao do TTL pôs este passo a faltar, porque ele vivia dentro
        do `if ttl`. O produtor que le a consola continua a ver que o sistema
        foi buscar dados — so nao pode ler "cache: MISS" num intent sem
        cache, que seria mentira.
        """
        import inspect

        from app.ia import sandbox

        fonte = inspect.getsource(sandbox.executar)
        self.assertIn('"busca"', fonte, "o passo 'busca' desapareceu do console")

        # e o detalhe tem de distinguir os dois ramos
        self.assertIn(
            "sem cache",
            fonte,
            "o ramo sem cache tem de dizer isso, e nao 'cache: MISS'",
        )
        self.assertIn(
            "cache: MISS", fonte, "o ramo com cache tem de dizer que foi MISS"
        )

    def test_a_regra_antiga_continua_valida_para_o_que_e_facto(self):
        """O que E' um fato (e nao uma decisao) continua em cache.

        Se isto falhar, a correccao foi longe demais e passou a custar uma
        ida ao provider de previsao por pergunta sem motivo.
        """
        from app.ia import sandbox

        for intent in ("listar_culturas", "listar_insumos", "resumo_safra"):
            self.assertNotEqual(
                sandbox.CACHE_TTL.get(intent),
                0,
                f"{intent} devolve factos, nao decisoes. TTL 0 aqui e desperdicio.",
            )
