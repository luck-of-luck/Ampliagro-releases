"""`/api/top-globais/<id>/` — os 16 widgets FieldView/JD/Trimble/Solinftec.

## Porquê este ficheiro existir

Este endpoint foi **incompatível com o Python durante meses**. Um `try:` ficou
sem o `except` que o fecha, e o resultado foi um `SyntaxError` na importação:

    app/api/urls.py, line 338
        __import__(...)
    app/api/views/top_globais.py, line 126
        try:
    SyntaxError: expected 'except' or 'finally' block

Como `app/api/urls.py` importa este módulo, **o servidor Django não arrancava**.
Não um widget-aviso, não uma página em branco: o projecto inteiro.

O que torna isto relevante para os testes é que o sintoma não é uma excepção que
um teste apanhe — é o interpretador a recusar o ficheiro antes de qualquer
código correr. Nada de testes passa, porque nada chega a executar.

Por isso o primeiro teste deste ficheiro é `compile()`. É a única forma de
apanhar o que o traceback de um servidor em silêncio não denuncia a ninguém.

## O resto do contrato

Um handler de widget é plug-in: a lista de excepções que ele pode levantar não
está escrita em lado nenhum, e não deve estar. A view apanha `Exception` e
devolve `{"disponivel": false, "motivo": ...}` com HTTP 200 — o widget mostra
"sem telemetria", não uma página de erro. Um 500 aqui seria dizer ao produtor
que a aplicação está partida quando o que falta é um sensor a falar.
"""

import io
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import SimpleTestCase
from rest_framework.test import APITestCase

from app.models import Propriedade


class ModuloImportavelTest(SimpleTestCase):
    """O ficheiro tem de compilar. Sem isto, nada mais deste ficheito corre."""

    def test_top_globais_compila(self):
        from app.api.views import top_globais

        caminho = top_globais.__file__
        fonte = open(caminho, encoding="utf-8").read()
        try:
            compile(fonte, caminho, "exec")
        except SyntaxError as e:
            self.fail(
                f"app/api/views/top_globais.py nao compila (linha {e.lineno}: "
                f"{e.msg}). Como app/api/urls.py o importa, o servidor "
                f"Django nao arranca."
            )

    def test_app_arranca(self):
        """A garantia mais forte que este ficheiro pode dar."""
        from django.core.management import call_command

        try:
            call_command("check", verbosity=0)
        except Exception as e:  # noqa: BLE001
            self.fail(f"manage.py check falhou — a app nao arranca: {e}")


class HandlerQueLevantaTest(APITestCase):
    """Um handler partido devolve "sem dado", nunca uma página de erro."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="tg", password="test")
        Propriedade.objects.create(
            user=self.user, nome="Fazenda TG", area_total=10, uf="SP"
        )
        self.client.force_login(self.user)

    def test_handler_que_explode_nao_vira_500(self):
        from app.api.views import top_globais

        def explosivo(_data):
            raise ValueError("sensor sem leitura")

        with patch.dict(top_globais.WIDGET_HANDLERS, {"kpi-can-bus": explosivo}):
            resposta = self.client.get("/api/top-globais/kpi-can-bus/")

        # 200 com `disponivel: false` — o painel mostra "sem telemetria".
        self.assertEqual(resposta.status_code, 200)
        corpo = resposta.json()
        self.assertFalse(corpo["data"]["disponivel"])
        # E o motivo diz o que aconteceu: swallow em silencio seria o defeito.
        self.assertIn("ValueError", corpo["data"]["motivo"])
        self.assertIn("sensor sem leitura", corpo["data"]["motivo"])

    def test_widget_desconhecido_nao_e_inventado(self):
        resposta = self.client.get("/api/top-globais/nao-existe/")
        # 404 e' a resposta honesta. Devolver um widget vazio com 200 seria
        # dizer ao produtor que existe um dado que nao existe.
        self.assertIn(resposta.status_code, (400, 404))

    def test_proveniencia_e_dizida_pelo_payload(self):
        """`fonte_dado` tem de existir e o aviso tem de acompanhar o simulado.

        Treze handlers declaravam-se "reais" sem consultar nada. O campo
        `aviso` é o que impede que um simulado passe por medido.
        """
        from app.api.views import top_globais

        def sem_evidencia(_data):
            return {"valor": 42}

        with patch.dict(top_globais.WIDGET_HANDLERS, {"kpi-can-bus": sem_evidencia}):
            resposta = self.client.get("/api/top-globais/kpi-can-bus/")

        corpo = resposta.json()
        self.assertEqual(corpo["fonte_dado"], "simulado")
        self.assertIn("SIMULADO", corpo["aviso"])
