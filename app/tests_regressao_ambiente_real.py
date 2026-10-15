"""Regressao dos 7 defeitos encontrados na auditoria do ambiente real.

Cada teste daqui falha no commit anterior a cada correcao, e a falha e' a mesma
que o produtor via. Nenhum deles le o codigo-fonte para se_assertar: todos
exercitam o caminho real — a view, o `_calcula`, o ficheiro exportado.

O que une estes testes e' que nenhum deles e' um teste de mudanca-de-dado. Todos
sao contratos entre duas coisas que têm de concordar: um pedido e uma resposta,
uma propriedade e os seus talhoes, uma tela e a API que ela chama.
"""

import os
import sys as _sys

from django.contrib.auth.models import User
from django.test import TestCase

from app.models import Propriedade, Safra, Talhao, TalhaoGeometria


def _fazenda(user, nome="Fazenda Teste"):
    """Cria uma propriedade. Funcao de modulo, nao metodo: cada classe abaixo
    herda de `TestCase`, e um helper preso a uma classe base que ninguem herda
    e' um `NameError` a espera."""
    return Propriedade.objects.create(user=user, nome=nome, area_total=100, uf="MT")


def _cultura(nome="Soja"):
    """`Safra.cultura` e' NOT NULL, e uma safra sem cultura nao e' uma safra."""
    from app.models import Cultura

    return Cultura.objects.create(nome=nome)


# ---------------------------------------------------------------------------
# 1) O painel inteiro caia por um talhao sem geometria
# ---------------------------------------------------------------------------
class TalhaoSemGeometriaNaoDerrubaOPainel(TestCase):
    """`/api/top-globais/<id>/` respondia 500 em NOVE widgets.

    `TalhaoGeometria.talhao` e' um `OneToOneField(related_name="geometria")`.
    Sem a linha, `talhao.geometria` levanta `RelatedObjectDoesNotExist`, que
    herda de `AttributeError` — e o acesso estava FORA do `try` que protege o
    handler. O produtor lia `{"error": "Talhao has no geometria."}` com HTTP 500.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="geo", password="x")
        self.prop = _fazenda(self.user, "Fazenda Sem Geo")
        # O primeiro talhao, por ordem de nome, NAO tem geometria. Era este que
        # `.first()` apanhava.
        self.talhao_sem = Talhao.objects.create(
            propriedade=self.prop, nome="AAA Sem geometria", area_hectare=10
        )
        self.talhao_com = Talhao.objects.create(
            propriedade=self.prop, nome="ZZZ Com geometria", area_hectare=20
        )
        TalhaoGeometria.objects.create(
            talhao=self.talhao_com,
            geojson={
                "type": "Polygon",
                "coordinates": [
                    [
                        [-55.7, -12.5],
                        [-55.6, -12.5],
                        [-55.6, -12.4],
                        [-55.7, -12.4],
                        [-55.7, -12.5],
                    ]
                ],
            },
            centroide_lat=-12.45,
            centroide_lon=-55.65,
        )
        self.client.force_login(self.user)

    def test_widget_nao_e_500_quando_o_primeiro_talhao_nao_tem_geometria(self):
        r = self.client.get("/api/top-globais/kpi-guidance-ab/")
        self.assertEqual(
            r.status_code,
            200,
            "Um talhao sem geometria nao pode virar 500: e' falta de dado, "
            "nao 'a app esta partida'.",
        )
        self.assertNotIn("has no geometria", r.content.decode())

    def test_escolhe_o_talhao_que_tem_geometria(self):
        """Nao basta nao estourar: o widget tem de receber a geometria que existe.

        Escolher o primeiro talhao e' o que fazia o painel nao ter coordenada
        nenhuma numa fazenda em que so alguns talhoes foram georreferenciados.
        """
        r = self.client.get("/api/top-globais/kpi-vra-ndvi/")
        params = r.json()["params"]
        self.assertEqual(params["talhao_id"], self.talhao_com.id)
        self.assertIn("lat", params)
        self.assertIn("lon", params)

    def test_propriedade_sem_nenhum_talhao_nao_e_500(self):
        p2 = Propriedade.objects.create(
            user=self.user, nome="Vazia", area_total=5, uf="MT"
        )
        self.assertIsNotNone(p2.pk)
        r = self.client.get("/api/top-globais/kpi-carbono/")
        self.assertEqual(r.status_code, 200)


# ---------------------------------------------------------------------------
# 2) O mesmo cartao dava dois numeros diferentes
# ---------------------------------------------------------------------------
class KpiAreaTemDeSerOAnoInteiro(TestCase):
    """`kpi-area` devolvia UMA linha em vez da soma do ano.

    `.order_by("-ano").first()` sem desempate deixa o SQLite escolher qual das
    safras do ano mais recente devolve, e a escolha muda com o plano de
    execucao: o mesmo cartao respondia 45.000 ha por um caminho do codigo e
    180 ha por outro. Nao havia soma nenhuma, e o "ano" que o cartao anunciava
    era o de uma unica safra.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="area", password="x")
        self.prop = _fazenda(self.user, "Fazenda Area")
        self.cultura = _cultura()
        for nome, ano, plantada, colhida in (
            ("T1", 2025, 100, 95),
            ("T2", 2026, 200, 190),
            ("T3", 2026, 300, 290),
        ):
            Safra.objects.create(
                propriedade=self.prop,
                cultura=self.cultura,
                talhao=Talhao.objects.create(
                    propriedade=self.prop, nome=nome, area_hectare=plantada
                ),
                ano=ano,
                area_plantada=plantada,
                area_colhida=colhida,
            )
        self.client.force_login(self.user)

    def _kpi(self):
        from app.ia.palco_dados import _calcula

        safras = Safra.objects.filter(
            propriedade__in=Propriedade.objects.filter(pk=self.prop.pk)
        )
        vazio = safras.none()
        return _calcula("kpi-area", self.user, safras, vazio, vazio, vazio, "")

    def test_soma_o_ano_mais_recente(self):
        r = self._kpi()
        # 2026 tem duas safras: 200 + 300. Nao 200, nao 300.
        self.assertEqual(r["ano"], 2026)
        self.assertEqual(r["area_plantada"], 500.0)
        self.assertEqual(r["area_colhida"], 480.0)

    def test_downtime_e_a_diferenca_do_ano_nao_de_uma_safra(self):
        self.assertEqual(self._kpi()["area_downtime"], 20.0)

    def test_o_resultado_nao_depende_do_forma_do_queryset(self):
        """A instabilidade que fez isto aparecer: `.first()` sem desempate.

        As duas formas produzem o mesmo recorte — e o `.first()` sem desempate
        devolvia safras diferentes conforme a forma, que era o defeito.
        """
        from app.ia.palco_dados import _calcula

        vazio = Safra.objects.none()
        por_id = _calcula(
            "kpi-area",
            self.user,
            Safra.objects.filter(propriedade__in=[self.prop]),
            vazio,
            vazio,
            vazio,
            "",
        )
        por_base = _calcula(
            "kpi-area",
            self.user,
            Safra.objects.filter(
                propriedade__in=Propriedade.objects.filter(pk=self.prop.pk)
            ),
            vazio,
            vazio,
            vazio,
            "",
        )
        self.assertEqual(por_id, por_base)

    def test_so_a_soma_do_ano_mais_recente_entra(self):
        """O ano de 2025 nao pode vazar para o cartao de 2026.

        `area_downtime` e' a diferenca entre o plantado e o colhido *desse ano*.
        Com a soma a vazar de 2025, o downtime deixava de ser uma resposta para
        uma pergunta e passava a ser aritmetica entre epocas.
        """
        r = self._kpi()
        self.assertNotEqual(r["area_plantada"], 600.0)  # 100 de 2025 incluido
        self.assertNotEqual(r["area_colhida"], 575.0)


# ---------------------------------------------------------------------------
# 3) /controle/ respondia 500 por causa do nome de uma relacao
# ---------------------------------------------------------------------------
class ControleAbsolutoNaoE500(TestCase):
    """`Cultura.objects.filter(talhoes__...)` levantava `FieldError`.

    `Cultura` nao tem relacao inversa chamada "talhoes" — o campo que a liga ao
    talhao e' `Talhao.cultura_atual`, sem `related_name`. A pagina respondia 500
    e nao havia teste nenhum sobre ela.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="ctrl", password="x")
        self.prop = _fazenda(self.user, "Fazenda Controle")
        t = Talhao.objects.create(propriedade=self.prop, nome="T1", area_hectare=10)
        from app.models import Cultura

        self.cultura = Cultura.objects.create(nome="Soja")
        t.cultura_atual = self.cultura
        t.save(update_fields=["cultura_atual"])
        self.client.force_login(self.user)

    def test_pagina_abre(self):
        r = self.client.get("/controle/")
        self.assertEqual(r.status_code, 200)

    def test_a_cultura_do_talhao_aparece_na_lista(self):
        r = self.client.get("/controle/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, self.cultura.nome)

    def test_nao_mixer_culturas_de_outro_produtor(self):
        from app.models import Cultura

        outro = User.objects.create_user(username="outro", password="x")
        p2 = Propriedade.objects.create(
            user=outro, nome="Alheia", area_total=1, uf="MT"
        )
        t2 = Talhao.objects.create(propriedade=p2, nome="T9", area_hectare=1)
        c2 = Cultura.objects.create(nome="CULTURA-ALHEIA")
        t2.cultura_atual = c2
        t2.save(update_fields=["cultura_atual"])
        r = self.client.get("/controle/")
        self.assertNotContains(r, "CULTURA-ALHEIA")


# ---------------------------------------------------------------------------
# 4) O LCDPR caia num atributo que nunca existiu
# ---------------------------------------------------------------------------
class LcdprCpfCnpj(TestCase):
    """`propriedade.user.perfil.cpf_cnpj` — esse campo nao existe no schema.

    `cpf_cnpj` esta em `Propriedade`, e em mais lado nenhum. O `AttributeError`
    derrubava a exportacao inteira: 500 para quem clicava em "exportar LCDPR".
    """

    def setUp(self):
        self.user = User.objects.create_user(username="lcd", password="x")
        self.prop = _fazenda(self.user, "Fazenda LCDPR")

    def test_sem_cpf_diz_o_que_fazer_em_vez_de_500(self):
        self.prop.cpf_cnpj = ""
        self.prop.save(update_fields=["cpf_cnpj"])
        self.client.force_login(self.user)
        r = self.client.get("/api/exportar-lcdpr/")
        self.assertEqual(r.status_code, 400)
        corpo = r.content.decode()
        self.assertIn("CPF", corpo)
        # A resposta tem de dizer onde se preenche, nao so que falta.
        self.assertIn("Propriedade", corpo)

    def test_com_cpf_exporta_o_registro_0000(self):
        self.prop.cpf_cnpj = "123.456.789-00"
        self.prop.save(update_fields=["cpf_cnpj"])
        self.client.force_login(self.user)
        r = self.client.get("/api/exportar-lcdpr/")
        self.assertEqual(r.status_code, 200)
        primeira = r.content.decode().splitlines()[0]
        self.assertTrue(primeira.startswith("|0000|"), primeira)
        self.assertIn("12345678900", primeira)

    def test_utilizador_sem_perfil_nao_derruba_a_exportacao(self):
        """`testuser` e `test_nav` estao no banco sem `PerfilUsuario`.

        O fallback que foi removido era `user.perfil.cpf_cnpj`: um utilizador
        sem perfil dava `PerfilUsuario.DoesNotExist` antes mesmo de a
        `AttributeError` aparecer.
        """
        self.prop.cpf_cnpj = "12345678900"
        self.prop.save(update_fields=["cpf_cnpj"])
        self.client.force_login(self.user)
        from app.models import PerfilUsuario

        PerfilUsuario.objects.all().delete()
        r = self.client.get("/api/exportar-lcdpr/")
        self.assertEqual(r.status_code, 200)

    # ---------------------------------------------------------------------------


# 6) O log de producao recebia a saida dos testes
# ---------------------------------------------------------------------------
class LogDeTesteNaoEoDeProducao(TestCase):
    """`manage.py test` escrevia em `logs/ampliagro.log`.

    `manage.py` faz `setdefault` de `DJANGO_SETTINGS_MODULE` e o `pytest.ini`
    aponta ambos para `config.settings.dev`, que herda o `LOGGING` de `base` —
    logo o handler de ficheiro escrevia no log de PRODUCAO. Um
    `manage.py test app.ia.tests` fez o ficheiro crescer de 4.328.735 para
    4.453.879 bytes. Num log com 1.045 tracebacks, 446 vinham de
    `tests_proativo.py explode()`: `explode` e' um nome de teste, nao de uma
    falha. Quem lesse o log achava que a aplicacao estava em chamas.
    """

    def test_esta_suite_escreve_no_ficheiro_dos_testes(self):
        from django.conf import settings

        self.assertEqual(
            settings.ARQUIVO_LOG,
            "test-run.log",
            "Nao pode haver um ficheiro so: 'ampliagro.log' e' o que se le para "
            "saber o que aconteceu a quem estava a usar a aplicacao.",
        )

    def test_reconhece_as_duas_portas(self):
        """`manage.py test` e `pytest` sao duas portas diferentes para o mesmo
        problema. Um diagnostico que so funciona numa delas nao e' um diagnostico."""
        from config.settings.base import _rodar_testes

        casos_true = [
            ["manage.py", "test", "app"],
            ["manage.py", "test"],
            [r"C:\...\Scripts\pytest.exe", "tests/"],
            [r"C:\...\Scripts\py.test.exe"],
        ]
        casos_false = [
            ["manage.py", "runserver", "0.0.0.0:8001"],
            ["manage.py", "migrate"],
            ["manage.py", "checar_drift"],
            [r"C:\...\amplia_mcp\servidor.py", "--usuario", "demo"],
        ]
        original = _sys.argv
        # Tambem o ambiente, e nao so o argv.
        #
        # `PYTEST_CURRENT_TEST` esta setado enquanto este teste corre — e a
        # funcao o consulta. Sem o limpar, os `casos_false` recebiam True e o
        # teste media o ambiente em vez da logica do argv.
        #
        # Nao se pode resolver ligando o check de ambiente ao fim: e' ele que
        # reconhece `python -m pytest`, em que `argv[0]` e' o `__main__.py` do
        # pacote (stem "__main__") e o argv nao diz nada. Sem o check de
        # ambiente, nem o `pytest` do `pytest.ini` nem o do CI seriam
        # reconhecidos, e a suite voltaria a escrever no log de PRODUCAO.
        chaves_env = ["PYTEST_CURRENT_TEST", "PYTEST_ADDOPTS"]
        ambiente = {k: os.environ.pop(k, None) for k in chaves_env}
        try:
            for argv in casos_true:
                _sys.argv = argv
                self.assertTrue(_rodar_testes(), argv)
            for argv in casos_false:
                _sys.argv = argv
                self.assertFalse(_rodar_testes(), argv)
            # E a prova de que o ambiente sozinho tambem chega: e' o que
            # reconhece a porta que o argv nao reconhece.
            _sys.argv = ["manage.py", "runserver", "0.0.0.0:8001"]
            os.environ["PYTEST_CURRENT_TEST"] = "x::y (call)"
            self.assertTrue(_rodar_testes(), "o ambiente tem de bastar")
        finally:
            _sys.argv = original
            for k, v in ambiente.items():
                if v is not None:
                    os.environ[k] = v


# ---------------------------------------------------------------------------
# 7) Utilizadores sem PerfilUsuario
# ---------------------------------------------------------------------------
class UtilizadoresOrfaos(TestCase):
    """Um `User` sem `PerfilUsuario` nao pode levar um 500.

    O sinal `garantir_perfil_usuario` cria o perfil no `post_save` do `User`, e
    por isso quem e' criado hoje tem sempre perfil. Mas `testuser` (id 21) e
    `test_nav` (id 22) estao no banco de desenvolvimento sem perfil nenhum: o
    sinal nao recupera quem ficou de fora, e `checar_drift` so compara schema,
    nao dados — o orfao e' invisivel para as duas ferramentas.

    O perfil e' criado aqui e apagado a seguir, que e' como se produz o estado
    legado sem depender do banco de desenvolvimento.
    """

    def _utilizador_sem_perfil(self, username):
        """Produz o estado legado: um `User` sem `PerfilUsuario`.

        O `hasattr` tem de ser evaluated numa instancia RECARREGADA. O Django
        guarda em cache a relacao inversa depois do primeiro acesso, e um
        `hasattr` na mesma instancia responde a memoria e nao a base de dados —
        que da' um "o sinal criou o perfil, o teste não prova nada" num teste
        cujo objectivo e' justamente nao ter perfil.
        """
        from app.models import PerfilUsuario

        u = User.objects.create_user(username=username, password="x")
        PerfilUsuario.objects.filter(user=u).delete()
        recarregado = User.objects.get(pk=u.pk)
        self.assertFalse(
            hasattr(recarregado, "perfil"), "o sinal criou o perfil; nada foi provado"
        )
        return recarregado

    def test_a_tela_inicial_aguenta_o_perfil_ausente(self):
        u = self._utilizador_sem_perfil("sem_perfil")
        self.client.force_login(u)
        r = self.client.get("/")
        self.assertNotEqual(
            r.status_code,
            500,
            "Um produtor sem PerfilUsuario leva um 500 na primeira tela: "
            + r.content[:200].decode("utf-8", "replace"),
        )

    def test_o_api_do_utilizador_aguenta_o_perfil_ausente(self):
        u = self._utilizador_sem_perfil("sem_perfil2")
        self.client.force_login(u)
        for url in ("/api/safras/", "/api/insumos/", "/api/top-globais/kpi-area/"):
            with self.subTest(url=url):
                r = self.client.get(url)
                self.assertNotEqual(r.status_code, 500, url)


# ---------------------------------------------------------------------------
# 9) O diagnostico precisa de ver DADOS, nao so schema
# ---------------------------------------------------------------------------
class ChecarDadosVeOTerreno(TestCase):
    """`checar_drift` dizia "sem drift" com o banco todo mentido.

    Tudo o que o comando verificava era SCHEMA: nome de coluna, campo no
    serializer. Passa com valores que ninguem pode explicar. A Fazenda Modelo
    tinha `Propriedade.area_total` = 1.240 ha e os seus 18 talhoes somavam
    3.047 ha — e o dashboard mostrava o primeiro como "AREA TOTAL".

    A divergencia de 1.807 ha vivia invisivel porque nenhuma das outras
    verificacoes a tocava: uma comparava a safra com o talhao, a outra olhava
    para perfis. Sem talhoes, `area_total` nao era comparado com nada.
    """

    def _corre(self):
        """Corre `diagnostico_dados` e devolve o que ele disse.

        Este teste aponta para `diagnostico_dados`, e nao para `checar_drift`,
        porque e' ai que vivem os checks de DADOS. Houve uma versao destes
        checks dentro do `checar_drift` — que compara SCHEMA — e duas
        implementacoes da mesma verificacao e' o que o `AGENTS.md` manda
        evitar. Ficou a mais completa.
        """
        from io import StringIO

        from django.core.management import call_command

        buf = StringIO()
        try:
            call_command("diagnostico_dados", stdout=buf)
        except SystemExit:
            pass
        return buf.getvalue()

    def test_area_total_divergente_dos_talhoes_e_dito(self):
        p = _fazenda(
            User.objects.create_user(username="area_total", password="x"), "Divergente"
        )
        p.area_total = 100
        p.save(update_fields=["area_total"])
        Talhao.objects.create(propriedade=p, nome="T1", area_hectare=500)
        saida = self._corre()
        # Asserte-se nos FACTOS e nao na redacao: quem formata o relatorio pode
        # mudar as palavras sem mudar o que diz. O que tem de aparecer sao a
        # propriedade e os dois numeros que nao fecham.
        self.assertIn("Divergente", saida)
        self.assertIn("500.00", saida)
        self.assertIn("100.00", saida)

    def test_area_total_que_bate_com_os_talhoes_nao_avisa(self):
        """A Fazenda Muzambinho bate certo (85,6 = 85,6). Uma verificacao que
        disparasse sempre seria ruido, e ruido e' o que faz as pessoas ignorarem
        a ferramenta."""
        p = _fazenda(User.objects.create_user(username="ok", password="x"), "BateCerto")
        p.area_total = 300
        p.save(update_fields=["area_total"])
        for i in range(3):
            Talhao.objects.create(propriedade=p, nome=f"T{i}", area_hectare=100)
        self.assertNotIn("BateCerto", self._corre())

    def test_arredondamento_de_centesimos_nao_e_divergencia(self):
        p = _fazenda(
            User.objects.create_user(username="round", password="x"), "Arredonda"
        )
        p.area_total = 100.00
        p.save(update_fields=["area_total"])
        # 0,5 ha de diferenca e' arredondamento de duas casas decimais
        Talhao.objects.create(propriedade=p, nome="T1", area_hectare=100.4)
        self.assertNotIn("Arredonda", self._corre())

    def test_propriedade_sem_talhoes_nao_avisa(self):
        _fazenda(User.objects.create_user(username="vazio", password="x"), "SemTalhoes")
        self.assertNotIn("SemTalhoes", self._corre())

    def test_safra_impossivel_e_dita(self):
        u = User.objects.create_user(username="safra_bad", password="x")
        p = _fazenda(u, "SafraImpossivel")
        t = Talhao.objects.create(propriedade=p, nome="Pequeno", area_hectare=15)
        Safra.objects.create(
            propriedade=p, cultura=_cultura(), talhao=t, ano=2026, area_plantada=45000
        )
        saida = self._corre()
        # O talhao e o numero da safra: e' isso que identifica o achado, e nao a
        # categoria onde o relatorio o põe.
        self.assertIn("Pequeno", saida)
        self.assertIn("45", saida)


# ---------------------------------------------------------------------------
# 8) O template estava a um hifen de distancia
# ---------------------------------------------------------------------------
class ComparativoSafrasEncontraOTemplate(TestCase):
    """A view pedia `comparativo_safras.html`; o ficheiro e' `comparativo-safras.html`.

    `TemplateDoesNotExist` nao tem fallback: a rota respondia 500 para toda a
    gente, com o template de 6 KB na mesma pasta.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="cs", password="x")
        self.prop = _fazenda(self.user, "Fazenda Comp")
        self.client.force_login(self.user)

    def test_pagina_abre(self):
        r = self.client.get("/financeiro/comparativo-safras/")
        self.assertEqual(r.status_code, 200)

    def test_nenhuma_pagina_server_rendered_cai(self):
        """Nenhuma pagina pode pedir um template que nao existe.

        O bug foi um hifen em vez de um underscore no nome, e nenhuma das duas
        metades o apanha sozinha: `TemplateDoesNotExist` nao sobe ao import, e a
        pagina responde 500. O que se verifica e' o pedido, nao o ficheiro.

        Este teste NAO le o fonte da view para se auto-verificar. Um teste que
        le o codigo passa quando o codigo esta partido e falha quando um
        refactor o reformata sem mudar o comportamento — nos dois casos, errado.
        """
        paginas = [
            "/financeiro/comparativo-safras/",
            "/controle/",
            "/rastreabilidade/",
            "/simulador-lucro/",
        ]
        for url in paginas:
            with self.subTest(url=url):
                r = self.client.get(url)
                self.assertNotEqual(
                    r.status_code,
                    500,
                    f"{url} devolveu 500 ({r.content[:200]}).",
                )
