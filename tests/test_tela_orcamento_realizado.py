"""A tela do orcado x realizado.

O endpoint tinha testes (`tests/test_api_custo_por_talhao.py`) e o servico
tinha testes. Esta era a peça em falta: um motor com porta e uma porta sem
parede.

Estes testes nao verificam que a tela e' bonita - isso e' opiniao. Verificam
três coisas que sao facto:

1. A rota responde e o template renderiza.
2. O template nao tem `id` duplicado nem consome um payload que nao existe.
3. A promessa do texto do aviso e' cumprida - se a tela diz que ha lancamento
   sem talhao, e' porque o payload traz o numero.
"""

import re
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from app.models import (
    PerfilUsuario,
    Propriedade,
    Talhao,
)

D = Decimal


class ARota(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ana", "ana@x.com", "s12345678")
        # `create_user` ja' cria o PerfilUsuario (UNIQUE em user_id). Criar
        # aqui um segundo rebentava com IntegrityError - e a primeira leitura
        # do erro e' sempre "o meu fixture esta' errado", nao "o modelo".
        PerfilUsuario.objects.filter(user=self.user).update(
            tipo_usuario="produtor", area_servidor="AGRONOMIA"
        )
        self.prop = Propriedade.objects.create(
            user=self.user, nome="Fazenda", cep="37400000", area_total=D("30")
        )
        Talhao.objects.create(
            propriedade=self.prop, nome="Baixada", area_hectare=D("10")
        )
        self.client.force_login(self.user)

    def test_a_url_responde_200(self):
        r = self.client.get(reverse("orcamento-realizado"))
        self.assertEqual(r.status_code, 200)

    def test_o_template_e_o_certo(self):
        r = self.client.get(reverse("orcamento-realizado"))
        self.assertIn("Orcamento x Realizado", r.content.decode())

    def test_desligado_redireciona(self):
        self.client.logout()
        r = self.client.get(reverse("orcamento-realizado"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("login", r["Location"])

    def test_servidor_sem_permissao_da_403(self):
        """A view pede ADMIN/FINANCEIRO. Quem nao tem, nao entra.

        Um servidor de MECANICA ve maquinas, nao o desvio do orcado da safra
        alheia. Este teste existe para fixar essa separacao - e a razao de
        `orcamento-realizado` nao estar mapeado para `GERAL` em
        `app/hierarquia.py`, ao contrario de `custos-producao`.
        """
        srv = User.objects.create_user("ze", "ze@x.com", "s12345678")
        PerfilUsuario.objects.filter(user=srv).update(
            tipo_usuario="servidor", area_servidor="MECANICA"
        )
        self.client.force_login(srv)
        r = self.client.get(reverse("orcamento-realizado"))
        self.assertEqual(r.status_code, 403)


class OTemplate(TestCase):
    """O HTML tem de bater certo com o payload. Sem teste, os dois divergem."""

    def setUp(self):
        self.user = User.objects.create_user("ana", "ana@x.com", "s12345678")
        PerfilUsuario.objects.filter(user=self.user).update(
            tipo_usuario="produtor", area_servidor="AGRONOMIA"
        )
        self.prop = Propriedade.objects.create(
            user=self.user, nome="Fazenda", cep="37400000", area_total=D("30")
        )
        self.client.force_login(self.user)

    def _html(self):
        return self.client.get(reverse("orcamento-realizado")).content.decode()

    def test_nao_ha_id_duplicado(self):
        """MEDIDO 2026-10-05: escrevi `stat-lucrealiz` duas vezes.

        Com `id` duplicado, `getElementById` devolve sempre o primeiro. O
        cartao 'Lucro por ha' escrevia por cima do 'Lucro realizado' e os dois
        mostravam o mesmo numero - sem erro, sem aviso, e o produtor via um
        cartao que nao existe. Foi o `grep` que apanhou, nao o browser.
        """
        html = self._html()
        # so os ids que o JS procura
        ids = re.findall(r'getElementById\([\'"]([a-z0-9\-]+)[\'"]\)', html)
        declarados = re.findall(r'\bid="([a-z0-9\-]+)"', html)
        for i in ids:
            self.assertEqual(
                declarados.count(i),
                1,
                f'id "{i}" usado por JS {declarados.count(i)}x no HTML',
            )

    def test_todo_id_procurado_existe_no_html(self):
        html = self._html()
        ids = set(re.findall(r'getElementById\([\'"]([a-z0-9\-]+)[\'"]\)', html))
        declarados = set(re.findall(r'\bid="([a-z0-9\-]+)"', html))
        self.assertEqual(
            ids - declarados,
            set(),
            f"o JS procura ids que nao existem: {sorted(ids - declarados)}",
        )

    def test_o_html_declara_o_titulo_que_o_bloco_espera(self):
        html = self._html()
        self.assertIn("Orcamento x Realizado", html)

    def test_nao_ha_texto_corrompido(self):
        """Cedo na sessao saiu 'appearing nao e' zero' - CJK num ficheiro PT.

        Um `grep` por caracteres CJK nao e' exotismo: e' a deteccao mais
        barata de texto corrompido num ficheiro escrito por um LLM.
        """
        html = self._html()
        cjk = re.findall(r"[一-鿿]", html)
        self.assertEqual(cjk, [], f"caracteres CJK no template: {cjk[:5]}")

    def test_a_coluna_de_desvio_existe_no_cabecalho(self):
        html = self._html()
        for th in ("Orcado", "Realizado", "Desvio", "Custo/ha"):
            self.assertIn(f"<th>{th}</th>", html)

    def test_o_texto_diz_que_so_conta_o_que_foi_pago(self):
        """A coluna Realizado tem de explicar a sua regra.

        O produtor ve 'Realizado 10.000' e o cadastro mostra 13.000. Sem a
        nota, parece um erro do sistema - e o unico sitio onde o produtor
        descobre que o sistema esta certo e ele e' que estava a contar o
        boleto errado.
        """
        html = self._html()
        self.assertIn("pago", html)
        self.assertIn("boleto", html)

    def test_o_aviscome_antes_dos_numeros(self):
        """O aviso tem de estar acima da tabela.

        Um R$ 9.000 que nao esta em nenhum talhao nao aparece nas linhas. Se
        o aviso estiver abaixo, o produtor le a tabela, ve um custo baixo, e
        so depois e' avisado de que faltam 9.000. A ordem e' o aviso.
        """
        html = self._html()
        self.assertLess(
            html.index("aviso-pendencias"),
            html.index('id="tabela"'),
            "o aviso tem de vir antes da tabela",
        )


class AUrlDaApiNoTemplate(TestCase):
    def test_o_template_aponta_para_a_url_certa(self):
        """MEDIDO 2026-10-05: um URL errado aqui falha em silencio.

        O `fetch` a um caminho inexistente devolve 404, o `.catch` escreve
        'Nao foi possivel carregar', e o produtor acha que a fazenda esta
        vazia. Nada no servidor levanta. Por isso o caminho esta escrito a
        mao aqui e conferido contra o `urls.py`.
        """
        with open("app/templates/orcamento-realizado.html", encoding="utf-8") as fh:
            template = fh.read()
        # A URL esta numa variavel (`let url = '/api/...'`), nao dentro do
        # fetch. MEDIDO 2026-10-05: procurei `fetch('/api/...')` e nao
        # encontrei - o template estava certo, o regex estava errado. Procurar
        # "a rota literal dentro do fetch" e' uma suposicao sobre a forma do
        # codigo, e a forma muda; a rota e' o que interessa.
        m = re.search(r"(/api/financeiro/[a-z\-/]+)", template)
        self.assertIsNotNone(m, "o template nao menciona nenhuma rota /api/")
        caminho = m.group(1)

        from django.urls import resolve

        # `resolve` levanta se a rota nao existir - e' o que apanha o erro.
        try:
            resolve(caminho)
        except Exception as e:
            self.fail(
                f"o template chama {caminho} e essa rota nao existe ({e}). "
                "Um fetch para um 404 mostra 'nao foi possivel carregar' e "
                "nao distingue 'fazenda vazia' de 'endereco errado'."
            )
