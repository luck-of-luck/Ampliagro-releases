"""Testes do onboarding — guarda de XSS e fluxo básico.

POR QUE ESTE FICHEIRO EXISTE
---------------------------
`onboarding.html` recebia a lista de culturas como `json.dumps` injetado com
`|safe` dentro de um `<script>`. `Cultura.nome` e' gravavel via API
(`CulturaViewSet = IsAuthenticated`, tabela global, sem escopo por
propriedade), entao um nome contendo `</script>` executava JavaScript para
qualquer utilizador que chegasse ao onboarding. XSS armazenado
**cross-tenant**, nao self-XSS. O conserto foi `json_script`.

O QUE MUDOU EM 02/10/2026, E O QUE ESTE FICHEIRO PASSEI A MEDIR
-------------------------------------------------------------
O onboarding foi redesenhado (mapa primeiro, ids `onb-*`) e o selector de
cultura saiu da pagina. Os 8 testes deste ficheiro passaram a falhar ha dois
dias, e ninguem corria a suite para ver.

Apagar os testes seria deixar o alarme desligado. Este ficheiro foi reescrito
para guardar a MESMA ameaca por um caminho que sobrevive a redesenhos:

  - o payload nunca aparece cru no HTML servido
  - o template nao usa `|safe` em lado nenhum
  - a view e o template concordam sobre `culturas` — quem passa, quem consome

O ultimo e' o que impede a repeticao: se um redesenho voltar a passar
culturas ao template, o teste acusa em vez de falhar em silencio.

A NOTA DE SEGUIMENTO, QUE NAO ESTA AQUI
---------------------------------------
`Cultura.nome` continua a ser gravavel por qualquer autenticado, em tabela
global. O selector foi para outro sitio do produto. **ONDE essa lista e'
renderizada hoje nao foi verificado por este ficheiro.** A guarda analoga
precisa de existir la.
"""

import json
import re
from pathlib import Path

from django.contrib.auth.models import User
from django.test import Client, TestCase

from app.models import Cultura, Propriedade

PAYLOAD_XSS = "</script><script>window.__PWNED__=1</script>"

TPL = Path(__file__).resolve().parent / "templates" / "onboarding.html"


class OnboardingXSSTest(TestCase):
    """`Cultura.nome` e' controlled por outro utilizador. Nao pode virar script."""

    def setUp(self):
        self.user = User.objects.create_user("onb", password="x")
        self.cultura = Cultura.objects.create(
            nome=PAYLOAD_XSS, grupo="graos", ativo=True
        )
        self.limpa = Cultura.objects.create(nome="Soja", grupo="graos", ativo=True)
        self.c = Client()
        self.c.force_login(self.user)

    def _html(self):
        r = self.c.get("/onboarding/")
        self.assertEqual(r.status_code, 200)
        return r.content.decode("utf-8")

    def test_payload_da_cultura_nao_quebra_o_script(self):
        """A guarda que sobrevive a tudo: o payload cru nunca e' servido."""
        html = self._html()
        self.assertNotIn(
            PAYLOAD_XSS,
            html,
            "payload literal no HTML = breakout do <script> (XSS funcional)",
        )
        self.assertNotIn("<script>window.__PWNED__", html)

    def test_template_nao_usa_safe_em_lado_nenhum(self):
        """`|safe` e' o que torna um payload executavel. Não ha excepção."""
        tpl = TPL.read_text(encoding="utf-8")
        usos = re.findall(r"\{\{[^}]*\|safe[^}]*\}\}", tpl)
        self.assertEqual(usos, [], f"o onboarding voltou a usar |safe: {usos!r}")

    def test_view_e_template_concordam_sobre_culturas(self):
        """Impede a repeticao do bug de 02/10.

        Se a view voltar a passar `culturas` e o template nao as renderizar,
        ha codigo morto e — pior — um comentario que volta a mentir sobre o que
        a pagina faz. Se o template voltar a renderizar `culturas`, tem de ser
        por `json_script`, que e' o que escapa.
        """
        fonte = TPL.read_text(encoding="utf-8")
        usa_no_template = "culturas" in fonte

        import inspect

        from app.views import auth as auth_views

        fonte_view = inspect.getsource(auth_views.onboarding_view)
        passa_na_view = '"culturas"' in fonte_view

        if usa_no_template and passa_na_view:
            self.assertIn(
                'json_script:"',
                fonte,
                "a view passa culturas E o template consome — tem de ser json_script",
            )
        else:
            self.assertFalse(
                usa_no_template and not passa_na_view,
                "o template consome culturas mas a view nao as passa",
            )

    def test_a_query_de_cultura_ignora_inativas(self):
        """A view voltou a consultar `Cultura` em 13/10/2026 — com filtro.

        Antes o teste afirmava `Cultura.objects` ausente da view, porque o
        selector de cultura tinha saído do cadastro. O requisito de produto
        ("na entrada da fazenda, perguntar em multi-seleção quais culturas
        produzimos") reabriu essa porta, e um teste que continua a exigir a
        porta fechada rejeitaria a funcionalidade pedida.

        O que NÃO pode voltar é a consulta sem filtro: uma cultura com
        `ativo=False` sumiu do produto, e oferecer um caminho que já não abre
        é pior do que não oferecer nada. A forma do teste é a mesma ameaça
        coberta antes — o que se guarda é o filtro, não a ausência.
        """
        import inspect

        from app.cultures import seletor

        fonte = inspect.getsource(seletor.opcoes_para_seletor)
        self.assertIn(
            "ativo=True",
            fonte,
            "o seletor voltou a listar culturas inativas",
        )

        # E o que é entregue ao browser não pode carregar colunas que não são
        # desenhadas (janela de plantio, chave de mercado, agrodoc…).
        self.assertIn(".only(", fonte, "o seletor voltou a trazer a Cultura inteira")

    def test_ids_validos_rejeita_o_que_nao_e_id(self):
        """`culturas` chega de um POST. Só entra id que existe e está activo."""
        from app.cultures.seletor import ids_validos

        ativa = Cultura.objects.create(nome="Soja", grupo="graos", ativo=True)
        inativa = Cultura.objects.create(nome="Milho", grupo="graos", ativo=False)

        self.assertEqual(ids_validos([ativa.id]), [ativa.id])
        self.assertEqual(ids_validos([inativa.id]), [], "cultura inativa entrou")
        self.assertEqual(ids_validos([999999]), [], "id inexistente entrou")
        self.assertEqual(ids_validos("soja"), [], "string aceite como lista")
        self.assertEqual(ids_validos(None), [])
        self.assertEqual(
            ids_validos([str(ativa.id), ativa.id]),
            [ativa.id],
            "repetido não foi barrado",
        )
        self.assertEqual(ids_validos(["; DROP TABLE app_cultura;"]), [])

    def test_ids_validos_respeita_o_tecto(self):
        """Um POST com 100 000 ids não pode virar um `id__in` desse tamanho.

        O tecto corta ANTES do `id__in`. Por isso mede-se aCORTE, e não a
        lista devolvida: essa ainda passa pelo filtro de existência, e um id
        que não existe na base devolveria `[]` — o que prova que o filtro
        existe, não que o tecto funciona. Os dois são testes diferentes.
        """
        import inspect

        from app.cultures import seletor

        fonte = inspect.getsource(seletor.ids_validos)
        self.assertIn(
            "[:MAXIMO_CULTURAS]", fonte, "a lista não é cortada antes do id__in"
        )
        self.assertEqual(seletor.MAXIMO_CULTURAS, 200)

    def test_ids_validos_filtra_o_que_nao_existe(self):
        """Efeito observável do mesmo filtro, com culturas reais."""
        from app.cultures.seletor import ids_validos

        real = Cultura.objects.create(nome="Feijão", grupo="leguminosas", ativo=True)
        resultado = ids_validos([real.id, 999999])
        self.assertEqual(resultado, [real.id])

    def test_o_payload_vai_json_script_e_a_leitura_vai_por_textcontent(self):
        """A entrega é `json_script`; a LEITURA tem de ser por `textContent`.

        `json_script` sozinho não fecha o XSS: ele garante que o payload não
        é executado, mas um nome de cultura que entre por `innerHTML` na hora
        de desenhar as checkboxes continua a ser XSS armazenado cross-tenant
        — `Cultura.nome` é gravável por qualquer autenticado, sobre a tabela
        global partilhada.

        Este teste existe porque `test_payload_da_cultura_nao_quebra_o_script`
        NÃO o apanha: aquele verifica que o payload cru não aparece no HTML, e
        um XSS montado por JS nunca aparece.
        """
        import re

        fonte = TPL.read_text(encoding="utf-8")
        trecho = fonte.split("onb-culturas-lista")[-1]

        # Desenhar a lista de culturas não pode usar innerHTML.
        self.assertNotIn(
            "innerHTML",
            trecho,
            "a lista de culturas voltou a ser desenhada por innerHTML — "
            "Cultura.nome é controlado por outro utilizador",
        )

        # E o nome tem de entrar por textContent.
        self.assertIn(
            "textContent", fonte, "o nome da cultura não entra por textContent"
        )

        # Nenhum atributo interpolado com a lista crua.
        self.assertIsNone(
            re.search(r'data-[a-z-]+="\{\{[^}]*culturas', fonte),
            "a lista crua está num atributo HTML",
        )


class OnboardingFluxoTest(TestCase):
    """Quem chega ao onboarding e o que ve."""

    def setUp(self):
        self.c = Client()

    def test_anonimo_cai_no_login(self):
        r = self.c.get("/onboarding/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login/", r["Location"])

    def test_usuario_sem_propriedade_ve_o_onboarding(self):
        u = User.objects.create_user("novo", password="x")
        self.c.force_login(u)
        r = self.c.get("/onboarding/")
        self.assertEqual(r.status_code, 200)
        # a pagina tem de ter os campos que o produtor preenche
        self.assertContains(r, 'id="onb-nome"')
        self.assertContains(r, 'id="onb-area"')
        self.assertContains(r, 'id="onb-mapa"')

    def test_usuario_com_propriedade_e_redirecionado(self):
        u = User.objects.create_user("com_faz", password="x")
        Propriedade.objects.create(
            user=u, nome="Faz", area_total=10, uf="MT", cidade="X"
        )
        self.c.force_login(u)
        r = self.c.get("/onboarding/")
        self.assertEqual(r.status_code, 302)


class CulturaGrupoRotulosTest(TestCase):
    """Nenhuma cultura pode aparecer no seletor com o valor cru do grupo.

    MEDIDO em 13/10/2026: a base tem 709 culturas em 30 valores de `grupo`,
    e `Cultura.GRUPOS` declarava 20. Os 12 que faltavam (249 culturas — 69 em
    `peixes`, 41 em `bovinos`, 26 em `ovinos`, 22 em `suinos`, 25 em
    `crustaceos`, 21 em `equinos`, 18 em `aves`, 16 em `infraestrutura`, 5 em
    `bufalos`, 4 em `leite`, 1 em `ovos`, 1 em `perenes`) caíam no
    `dict(GRUPOS).get(chave, chave)`, e o produtor lia "peixes" onde devia
    ler "Peixes".

    Não é crash: é pior. `_preguicosos` normaliza acentos e minúsculas, então
    o valor cru ainda FUNCIONA como chave de normalização — o agrupamento
    continua correcto e o produto parece inteiro. Por isso este teste mede a
    apresentação, que é a única coisa que estava errada.
    """

    def test_toda_cultura_activa_tem_rotulo_declarado(self):
        from app.cultures.seletor import _ROTULOS, opcoes_para_seletor

        faltando = sorted(
            {g["grupo"] for g in opcoes_para_seletor() if g["grupo"] not in _ROTULOS}
        )
        self.assertEqual(faltando, [], f"grupos sem rótulo declarado: {faltando}")

    def test_o_rotulo_nao_e_a_propria_chave(self):
        """`peixes` != `Peixes`. Se um dia alguém declarar o par errado, o
        produtor volta a ler a chave e este teste diz porquê."""
        from app.cultures.seletor import _ROTULOS

        iguais = sorted(k for k, v in _ROTULOS.items() if k == v)
        self.assertEqual(iguais, [], f"rótulo idêntico à chave: {iguais}")

    def test_o_rotulo_nao_cai_no_valor_cru_no_seletor(self):
        """Fecha a cadeia inteira: grupo em `peixes` tem de sair 'Peixes'."""
        from app.cultures.seletor import opcoes_para_seletor

        self.assertIn(
            Cultura.objects.create(nome="Tilápia", grupo="peixes", ativo=True).id,
            [
                c["id"]
                for c in next(
                    g for g in opcoes_para_seletor() if g["grupo"] == "peixes"
                )["culturas"]
            ],
        )
        grupo = next(g for g in opcoes_para_seletor() if g["grupo"] == "peixes")
        self.assertEqual(grupo["rotulo"], "Peixes")


class OnboardingCulturasTest(TestCase):
    """O que o produtor marca no passo 3 tem de chegar ao `Propriedade`.

    Este e' o elo que decide o resto do produto: guias, widgets e perguntas de
    IA sao filtrados por `propriedade.culturas`. Um cadastro que cria a
    propriedade e perde a selecao nao da erro: da uma conta que parece ter
    escolhido tudo e nao mostra nada de cultura. Por isso o teste vai ate
    ao banco, e nao ate a resposta 200.
    """

    def setUp(self):
        self.user = User.objects.create_user("produtor", password="x")
        self.soja = Cultura.objects.create(nome="Soja", grupo="graos", ativo=True)
        self.milho = Cultura.objects.create(nome="Milho", grupo="graos", ativo=True)
        self.algodao = Cultura.objects.create(
            nome="Algodão", grupo="oleaginosas", ativo=True
        )
        self.inativa = Cultura.objects.create(
            nome="Milho Anão", grupo="graos", ativo=False
        )
        self.c = Client()
        self.c.force_login(self.user)

    def _salvar(self, **extra):
        payload = {"nome_fazenda": "Fazenda X", "area": 100, "culturas": []}
        payload.update(extra)
        return self.c.post(
            "/api/onboarding/save/",
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_as_culturas_marcadas_ficam_na_propriedade(self):
        r = self._salvar(culturas=[self.soja.id, self.algodao.id])
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"], r.content)

        propriedade = Propriedade.objects.get(user=self.user)
        self.assertEqual(
            set(propriedade.culturas.values_list("id", flat=True)),
            {self.soja.id, self.algodao.id},
        )

    def test_ids_comecem_como_texto_tambem_sao_aceites(self):
        """O browser manda o que sai de `String(id)`. Recusar seria um 400
        que trava o cadastro por um tipo, não por um erro."""
        r = self._salvar(culturas=[str(self.milho.id)])
        self.assertTrue(r.json()["ok"], r.content)
        propriedade = Propriedade.objects.get(user=self.user)
        self.assertEqual(
            list(propriedade.culturas.values_list("id", flat=True)), [self.milho.id]
        )

    def test_cultura_inexistente_nao_e_criada(self):
        r = self._salvar(culturas=[self.soja.id, 999999])
        self.assertTrue(r.json()["ok"], "um id adulterado não deve travar o cadastro")
        propriedade = Propriedade.objects.get(user=self.user)
        self.assertEqual(
            list(propriedade.culturas.values_list("id", flat=True)), [self.soja.id]
        )

    def test_cultura_inativa_nao_entra(self):
        r = self._salvar(culturas=[self.inativa.id])
        self.assertTrue(r.json()["ok"], r.content)
        propriedade = Propriedade.objects.get(user=self.user)
        self.assertEqual(propriedade.culturas.count(), 0)

    def test_cadastro_sem_culturas_nao_e_bloqueado(self):
        """Nenhuma marcada é um cadastro válido: o produtor pode escolher
        depois nas configurações. Travar aqui deixaria quem só queria ver o
        mapa sem poder sair do wizard."""
        r = self._salvar()
        self.assertTrue(r.json()["ok"], r.content)
        self.assertTrue(Propriedade.objects.filter(user=self.user).exists())
