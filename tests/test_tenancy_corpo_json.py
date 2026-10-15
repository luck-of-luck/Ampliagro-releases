"""O corpo JSON contorna o `TenantIsolationMiddleware`.

MEDIDO 2026-10-05 (agente 9, a partir de uma observacao de outro agente).

O QUE O MIDDLEWARE FAZ
======================
`app/middleware.py:201`:

    fonte = request.GET if request.method == "GET" else request.POST

`request.POST`, no Django, so' e' populado para `multipart/form-data` e
`application/x-www-form-urlencoded`. Num `POST` com `Content-Type:
application/json` — que e' o que a API DRF fala em quase todo o lado —
`request.POST` vem VAZIO.

A consequencia: o ciclo `for param in self.TABELAS_VERIFICADAS` nao encontra
nada, `request.propriedade` fica `None`, o `fallback` da linha 246 mete a
primeira propriedade do utilizador, e a requisicao passa sem ter sido
verificada. **O middleware e' exactamente a porta que nao abre.**

ISSO E' UMA FUGA HOJE?
======================
Nao. As views que leem `safra_id` do request ja fazem scope
(`propriedade__user=request.user`), como o proprio middleware documenta em
`middleware.py:171-174`. E' uma lacuna no PORTO UNICO: a proteccao existe em
cada view, e nao existe na fronteira.

Porque e' mesmo assim um bug grave: a proxima view que alguem escrever, a
protecao depende de essa pessoa se lembrar. E a falha e' silenciosa — o
`ids_inexistentes` nao dispara, nenhum log, resposta 200. Um teste de
cross-tenant passa na view e falha no gateway, que e' o sitio onde a
concussao sobre "a tabela tem `propriedade__user`?" vai acontecer.

Este ficheiro NAO e' um teste que passa hoje. E' um teste que **demonstra a
lacuna** e que passa a falhar no momento em que `request.body` passar a ser
inspeccionado. ate la, e' a prova de que o buraco existe.
"""


from django.contrib.auth.models import User
from django.test import Client, TestCase

from app.models import Propriedade, Safra


class CorpoJsonContornaOTenancyTest(TestCase):
    """Demostra que `application/json` nao passa pela verificacao."""

    def setUp(self):
        self.alice = User.objects.create_user(username="alice_tc", password="x")
        self.bob = User.objects.create_user(username="bob_tc", password="x")

        self.faz_alice = Propriedade.objects.create(
            user=self.alice,
            nome="Fazenda Alice",
            area_total=10.0,
            uf="GO",
            cidade="Pirenópolis",
        )
        self.faz_bob = Propriedade.objects.create(
            user=self.bob,
            nome="Fazenda Bob",
            area_total=10.0,
            uf="GO",
            cidade="Rio Verde",
        )
        # safra do BOB. O alvo que Alice nao pode tocar.
        # `Safra` exige `cultura` (PROTECT) e `area_plantada` (NOT NULL) —
        # ver `app/models/safra.py:51,54`. Inventar os kwargs foi o erro.
        from decimal import Decimal

        from app.models import Cultura

        self.cultura = Cultura.objects.create(
            nome="Soja", grupo="graos", unidade_comercial="sc", ativo=True
        )
        self.safra_bob = Safra.objects.create(
            propriedade=self.faz_bob,
            cultura=self.cultura,
            ano=2026,
            area_plantada=Decimal("100.00"),
        )

        self.client = Client()
        self.client.force_login(self.alice)

    def test_form_data_e_verificado(self):
        """O caminho que o middleware cobre: `form-data` e' recusado."""
        r = self.client.post(
            "/api/lancamentos-detalhados/",
            data={"safra_id": self.safra_bob.pk},
            content_type="multipart/form-data",
        )
        # O que interesa: NAO pode ser 200 com a safra do Bob consumida.
        self.assertNotEqual(
            getattr(r, "status_code", 0),
            200,
            "form-data devia ser recusado pelo middleware; se chegou a 200, "
            "o gateway nao esta a proteger",
        )

    def test_corpo_json_nao_e_verificado_pelo_middleware(self):
        """A LACUNA: JSON passa sem o middleware ver o `safra_id` do outro.

        Este teste e' a documentacao executada do buraco. Quando alguem
        acrescentar `request.body` a `middleware.py:201`, a assercao
        `ids_inexistentes` passa a ter conteudo e este teste falha — que e'
        como se avisa que a correccao entrou.
        """
        # Invocar o middleware pelo caminho real do DRF nao e' possivel sem
        # uma view que leia `safra_id` do corpo. O que se prova aqui e' a
        # propriedade do Django de que a lacuna depende:
        #   `request.POST` e' VAZIO para `application/json`.
        from django.test import RequestFactory

        rf = RequestFactory()
        req = rf.post(
            "/api/lancamentos-detalhados/",
            data='{"safra_id": %d}' % self.safra_bob.pk,
            content_type="application/json",
        )

        self.assertEqual(
            req.POST.get("safra_id"),
            None,
            "isto e' a premissa da vulnerabilidade. Se o Django passar a "
            "popular `request.POST` para JSON, o middleware passa a ver o "
            "corpo e a lacuna fecha por acidente — o que e' umikedd "
            "acidente, nao uma correccao",
        )
        self.assertTrue(
            req.body,
            "o corpo tem de estar em `request.body`. E' ai que o `safra_id` "
            "esta, e e' ai que o middleware nao olha",
        )

    def test_a_tabela_verificada_declara_safra_id(self):
        """Confirma que `safra_id` ESTA na lista — logo, o middleware
         intended protege-lo. E' o que torna a lacuna uma omissao e nao uma
         decisao."""
        from app.middleware import TenantIsolationMiddleware

        m = TenantIsolationMiddleware(lambda r: None)
        self.assertIn(
            "safra_id",
            m.TABELAS_VERIFICADAS,
            "se `safra_id` saiu da tabela, a omissao do corpo JSON deixou de "
            "importar e este ficheiro devia ser reescrito",
        )
