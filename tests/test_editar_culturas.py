"""O ecrã "as minhas culturas" — editar a escolha depois do cadastro.

POR QUE ISTO EXISTE
-------------------
O passo de culturas do cadastro diz ao produtor: *"Dá para mudar depois nas
configurações"*. Até aqui essa frase era uma promessa sem ecrã: o produtor
escolhia uma vez no onboarding e ficava preso. Numa decisão que decide tudo o
que ele vê em todo o produto, estar preso é o pior resultado possível — e a
alternativa (não dizer nada) era esconder a limitação.

O QUE ESTE FICHEIRO PROVA
-------------------------
1. Grava e devolve, e substitui em vez de acumular — porque a interface tem de
   oferecer a MESMA operação que o cadastro, e "acrescentar" torna impossível
   desmarcar.
2. A propriedade de outro produtor é 404. Não 403, não 200 com um `set()`
   silencioso: `culturas.set()` na propriedade de outro é uma escrita
   cross-tenant que responde 200, e parece que funcionou.
3. Editing volta a marcar a resposta — senão limpar a lista e voltar a clicar
   em "salvar" desfazia a marca `culturas_escolhidas_em` e o filtro das guias
   voltava a "nunca perguntado".
"""

import json

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils import timezone

from app.models import Cultura, Propriedade


class EdicaoDeCulturas(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("dono", password="x")
        self.outro = User.objects.create_user("outro", password="x")
        self.prop = Propriedade.objects.create(
            user=self.user, nome="Faz", area_total=100, uf="MT"
        )
        self.soja = Cultura.objects.create(nome="Soja", grupo="graos", ativo=True)
        self.milho = Cultura.objects.create(nome="Milho", grupo="graos", ativo=True)
        self.tilapia = Cultura.objects.create(
            nome="Tilápia", grupo="peixes", ativo=True
        )
        self.c = Client()
        self.c.force_login(self.user)

    def _url(self):
        return f"/perfil/culturas/{self.prop.id}/"

    def _post(self, payload):
        return self.c.post(
            self._url(), data=json.dumps(payload), content_type="application/json"
        )

    # ── gravar ──

    def test_grava_o_que_mandou(self):
        r = self._post({"culturas": [self.soja.id, self.tilapia.id]})
        self.assertTrue(r.json()["ok"], r.content)
        self.assertEqual(
            set(self.prop.culturas.values_list("id", flat=True)),
            {self.soja.id, self.tilapia.id},
        )

    def test_substitui_em_vez_de_acumular(self):
        """O teste que separa "editar" de "acrescentar". Guardar Soja e depois
        guardar Milho tem de deixar SÓ Milho — senão o produtor nunca
        desmarca."""
        self._post({"culturas": [self.soja.id]})
        self._post({"culturas": [self.milho.id]})
        self.assertEqual(
            list(self.prop.culturas.values_list("id", flat=True)),
            [self.milho.id],
        )

    def test_esvaziar_e_salvar_marca_a_resposta(self):
        """O ciclo que desfaz o bug da marca.

        Responder "nenhuma" marca. Editar para "nenhuma" também tem de marcar:
        sem isto, `culturas_escolhidas_em` é reescrito a `null` por um caminho
        e o filtro das guias volta a não filtrar, que é a conta antiga.
        """
        self._post({"culturas": [self.soja.id]})
        r = self._post({"culturas": []})
        self.assertTrue(r.json()["ok"], r.content)
        self.prop.refresh_from_db()
        self.assertIsNotNone(self.prop.culturas_escolhidas_em)
        self.assertEqual(self.prop.culturas.count(), 0)

    def test_ids_comecem_como_texto(self):
        r = self._post({"culturas": [str(self.soja.id)]})
        self.assertTrue(r.json()["ok"], r.content)
        self.assertEqual(
            list(self.prop.culturas.values_list("id", flat=True)),
            [self.soja.id],
        )

    def test_id_inexistente_e_ignorado(self):
        r = self._post({"culturas": [self.soja.id, 999999]})
        self.assertTrue(r.json()["ok"])
        self.assertEqual(
            list(self.prop.culturas.values_list("id", flat=True)),
            [self.soja.id],
        )

    # ── ler ──

    def test_le_o_estado_actual(self):
        self.prop.culturas.set([self.soja, self.milho])
        self.prop.culturas_escolhidas_em = timezone.now()
        self.prop.save(update_fields=["culturas_escolhidas_em"])
        data = self.c.get(self._url()).json()
        self.assertEqual(sorted(data["ids"]), sorted([self.soja.id, self.milho.id]))
        self.assertEqual(data["n_marcadas"], 2)
        self.assertTrue(data["perguntada"])

    def test_diz_quando_nunca_foi_perguntado(self):
        data = self.c.get(self._url()).json()
        self.assertFalse(data["perguntada"])
        self.assertEqual(data["ids"], [])

    # ── tenancy ──

    def test_propriedade_de_outro_e_404(self):
        """O teste mais importante do ficheiro.

        Filtrar por `user=request.user` no `get_object_or_404` é o que evita
        `culturas.set()` numa propriedade alheia. Sem o filtro, o POST
        respondia 200 e a escrita cross-tenant acontecia — o resultado mais
        perigoso possível, porque não parece erro.
        """
        alheia = Propriedade.objects.create(
            user=self.outro, nome="Dele", area_total=50, uf="MT"
        )
        url = f"/perfil/culturas/{alheia.id}/"
        self.assertEqual(self.c.get(url).status_code, 404)
        self.assertEqual(
            self.c.post(
                url,
                data=json.dumps({"culturas": [self.soja.id]}),
                content_type="application/json",
            ).status_code,
            404,
        )
        self.assertEqual(alheia.culturas.count(), 0, "escreveu na propriedade de outro")

    def test_anonimo_nao_chega(self):
        anon = Client()
        self.assertEqual(anon.get(self._url()).status_code, 302)


class CartaoNasConfiguracoes(TestCase):
    """O ecrã mostra o que o endpoint promete mostrar."""

    def setUp(self):
        self.user = User.objects.create_user("cfg", password="x")
        self.prop = Propriedade.objects.create(
            user=self.user, nome="Faz", area_total=100, uf="MT"
        )
        Cultura.objects.create(nome="Soja", grupo="graos", ativo=True)
        self.c = Client()
        self.c.force_login(self.user)

    def test_a_pagina_tem_o_cartao_e_a_lista(self):
        r = self.c.get("/perfil/config/")
        self.assertEqual(r.status_code, 200)
        html = r.content.decode("utf-8")
        self.assertIn('id="lista-culturas-cfg"', html)
        self.assertIn('id="sel-propriedade-culturas"', html)
        self.assertIn('id="salvar-culturas-cfg"', html)

    def test_o_payload_das_culturas_vai_json_script(self):
        """`Cultura.nome` é gravável por qualquer autenticado. Um
        `|safe` aqui é XSS armazenado cross-tenant que atinge todos os que
        abrirem as configurações."""
        html = self.c.get("/perfil/config/").content.decode("utf-8")
        self.assertIn('id="culturas-cfg"', html)
        self.assertIn('type="application/json"', html)

    def test_as_propriedades_vem_no_payload(self):
        html = self.c.get("/perfil/config/").content.decode("utf-8")
        self.assertIn('id="cfg-propriedades"', html)
        self.assertIn(self.prop.nome, html)

    def test_a_marca_da_o_nome_da_cultura_cru(self):
        """Um nome de cultura escrito à mão no template envelhece sozinho.
        Este teste diz que o nome vem do catálogo, não da minha Constants."""
        nova = Cultura.objects.create(
            nome="CULTURA_QUE_NAO_EXISTE_ANTES", grupo="graos", ativo=True
        )
        html = self.c.get("/perfil/config/").content.decode("utf-8")
        self.assertIn(nova.nome, html)

    def test_o_nome_da_cultura_nao_entra_por_innerhtml(self):
        """A leitura tem de ser por `textContent`.

        `json_script` garante que o payload não é EXECUTADO; não garante que
        a lista não seja desenhada com `innerHTML` a partir dele. São dois
        caminhos, e só um é fechado pelo `json_script`.
        """
        html = self.c.get("/perfil/config/").content.decode("utf-8")
        # O bloco do cartão é tudo o que vem depois do identificador dele.
        bloco = html.split("lista-culturas-cfg")[-1]
        self.assertNotIn(
            "innerHTML",
            bloco,
            "a lista de culturas voltou a ser desenhada por innerHTML",
        )
        self.assertIn("textContent", html)
