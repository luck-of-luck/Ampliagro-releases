"""O `get_queryset` nao pode engolir o erro do perfil.

PORQUE ESTE TESTE EXISTE
=======================
MEDIDO 2026-10-05: `TarefaEstagioViewSet.mover` tem uma verificacao de
CARGO que devolve 503 quando a leitura do perfil falha (commit 3db866a).

Mas NAO se conseguia provar isso de ponta a ponta, porque
`get_queryset()` le `user.perfil` ANTES do `mover`, dentro de um
`except Exception: pass`. O `get_object()` corre primeiro, o pedido morre
ali, e o `except` do `mover` nunca era alcancado.

Ou seja: a correccao do `mover` estava correcta mas **nao observavel**.
Isto e' o que este ficheiro resolve — nao com um teste de texto, mas a
correr o caminho e a ver o que sai.

O QUE ESTE TESTE PROVA
======================
Com um utilizador que NAO tem PerfilUsuario:

  antes  o `get_queryset` engole, devolve um queryset de fallback, e o
         pedido acaba em 403/404 — o `mover` nunca corre, e o produtor ve
         um "nao tens acesso" que NAO e' a verdade. A verdade e' "nao
         consegui ler o teu perfil".

  depois o `get_queryset` diz que nao conseguiu verificar, e o pedido
         acaba em 503 com essa mensagem.

A DIFFERENCA QUE O PRODUTOR VE
=============================
  403  "nao tens acesso"        -> o produtor pede permissao ao dono
                                   da fazenda. E' inutil: o problema
                                   nao e' permissao.
  503  "nao consegui verificar"  -> o produtor sabe que e' uma falha
                                   temporaria e volta a tentar.

403 e' uma MENTIRA sobre a causa. 503 e' a verdade. E a segunda coisa que
esta em jogo e' a mesma de sempre: um `[]` ou um 403 que esconde um erro
e' o painel que dizia "sem dado" sem ter feito fetch.

PORQUE O `except` VAI SER LARGO (e nao um `ValueError` estreito)
===============================================================
Porque aqui o erro pode ser QUALQUER: `RelatedObjectDoesNotExist` (utilizador
sem perfil), `AttributeError` (campo que mudou de nome), `OperationalError`
(coluna em falta). Estreitar o `except` a uma把这些 exceções nao
resolveria — apenas tornaria a falha mais rara, nao mais segura.

O que muda e' o QUE SE FAZ com o erro: nao engolir, mas dizer.
"""

import json
from unittest import mock

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from app.api.views.production import TarefaEstagioViewSet
from app.models import (
    EstagioCultura,
    PerfilUsuario,
    Propriedade,
    RegistroProducao,
    TarefaEstagio,
)


class GetQuerysetNaoEngoleOPerfilTest(TestCase):
    def setUp(self):
        self.rf = RequestFactory()
        self.servidor = User.objects.create_user("servidor", password="x")
        self.prop = Propriedade.objects.create(
            user=self.servidor, nome="Fazenda", area_total=10
        )
        PerfilUsuario.objects.update_or_create(
            user=self.servidor,
            defaults={
                "tipo_usuario": "servidor",
                "propriedade_vinculada": self.prop,
                "area_servidor": "GERAL",
            },
        )
        reg = RegistroProducao.objects.create(
            user=self.servidor,
            cultura_key="c",
            grupo="g",
            nome="Soja",
            status="ativo",
            location="t",
            unidade="kg",
            observacoes="",
            fields_json={},
            treatments=[],
        )
        est = EstagioCultura.objects.create(
            registro=reg,
            nome="Plantio",
            cor="#fff",
            icone="bi-x",
            ordem=1,
            tipo="tarefa",
        )
        self.tarefa = TarefaEstagio.objects.create(
            estagio=est, descricao="Reprovar", cargo_alvo="GERAL"
        )

    def _get(self):
        view = TarefaEstagioViewSet()
        req = self.rf.get("/x/")
        req.user = self.servidor
        view.request = req
        view.format_kwarg = None
        view.kwargs = {}
        view.args = ()
        view.queryset = TarefaEstagio.objects.none()
        return view.get_queryset()

    def _sem_perfil(self):
        """Apaga o PerfilUsuario e devolve o utilizador, recarregado.

        MEDIDO: `request.user.perfil` e' o accessor reverso de um
        `OneToOneField`; sem perfil, levanta `RelatedObjectDoesNotExist`,
        que herda de `ObjectDoesNotExist` -> `Exception`.

        O `refresh_from_db()` nao e' paranquial: o `User` em memoria
        pode ter o perfil em cache de uma leitura anterior dentro do
        mesmo teste, e sem isto o `delete()` nao se reflecte e o teste
        passa por acidente — o que e' pior do que falhar, porque
        parece estar a provar alguma coisa.
        """
        PerfilUsuario.objects.filter(user=self.servidor).delete()
        self.servidor = (
            User.objects.get(pk=self.servidor.pk)
            if hasattr(self.servidor, "pk")
            else self.servidor
        )
        return self.servidor

    # ------------------------------------------------------------------
    def test_com_perfil_valido_devolve_a_tarefa(self):
        """O caminho feliz nao pode partir-se.

        Fail-closed que recusa tudo nao e' fail-closed: e' o sistema
        partido. Este teste existe para garantir que a correccao nao
        estragou o caso normal.
        """
        qs = self._get()
        self.assertIn(
            self.tarefa.pk,
            [t.pk for t in qs],
            "um servidor com perfil valido deixou de ver as tarefas da "
            "sua fazenda. A correccao de fail-closed estragou o caminho "
            "feliz.",
        )

    # ------------------------------------------------------------------
    def test_sem_perfil_falha_em_vez_de_devolver_fallback(self):
        """A PROVA.

        Utilizador sem PerfilUsuario. Antes: o `except` engolia e o
        queryset de fallback era devolvido sem dizer nada. Agora: tem de
        falhar de forma visivel.
        """
        self._sem_perfil()

        with self.assertRaises(Exception) as ctx:
            self._get()

        self.assertNotIsInstance(
            ctx.exception,
            TarefaEstagio.DoesNotExist,
            "o perfil sumiu e o `get_queryset`NAO deu erro — ou seja, "
            "engoliu. Um utilizador sem perfil tem de dar um erro "
            "EXPLÍCITO, nao um queryset mais estreito que parece "
            "'nao tens tarefas'.",
        )

    # ------------------------------------------------------------------
    def test_a_mensagem_diz_que_nao_se_sabe_e_nao_que_nao_pode(self):
        """O texto tem de separar 'nao posso' de 'nao tens'.

        Este teste e' sobre a MENSAGEM que o produtor le, nao sobre o
        status. Um 403 com a mensagem errada e' pior que um 500: faz o
        produtor pedir permissao ao dono da fazenda por um bug.
        """
        self._sem_perfil()

        with self.assertRaises(Exception) as ctx:
            self._get()

        texto = str(ctx.exception).lower()
        for acusacao in ("nao tens acesso", "sem permissao", "nao autorizado"):
            self.assertNotIn(
                acusacao,
                texto,
                f"a mensagem acusa o utilizador: {acusacao!r}. O que "
                f"falhou foi a LEITURA do perfil, nao a permissao.",
            )
