from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase

from app.models import EstoqueItem, IAArtefato, Propriedade


class ConfirmacaoOCRTest(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user("ocr-confirmacao")
        self.prop = Propriedade.objects.create(
            user=self.usuario, nome="Fazenda OCR", area_total=10
        )
        self.client.force_login(self.usuario)
        self.item = {"nome": "Ureia", "quantidade": "12,50", "unidade": "kg"}
        self.rascunho = IAArtefato.objects.create(
            user=self.usuario,
            chave="teste-ocr",
            tipo="rascunho_estoque",
            dados={"itens": [self.item]},
        )

    def enviar(self, dados):
        if isinstance(dados, dict):
            dados = {"artefato_id": self.rascunho.pk, **dados}
        return self.client.post(
            "/api/ia/confirmar-estoque/", dados, content_type="application/json"
        )

    def test_grava_quantidade_decimal_revisada(self):
        resposta = self.enviar({"itens": [self.item]})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(EstoqueItem.objects.get().quantidade, Decimal("12.50"))

    def test_identificador_do_rascunho_e_obrigatorio(self):
        resposta = self.client.post(
            "/api/ia/confirmar-estoque/",
            {"itens": [self.item]},
            content_type="application/json",
        )
        self.assertEqual(resposta.status_code, 400)
        self.assertFalse(EstoqueItem.objects.exists())

    def test_item_invalido_impede_todo_o_lote(self):
        for valor in ("NaN", "Infinity", "0", "-1", "0.001", "100000000", "abc"):
            with self.subTest(valor=valor):
                resposta = self.enviar(
                    {"itens": [self.item, {**self.item, "quantidade": valor}]}
                )
                self.assertEqual(resposta.status_code, 400)
                self.assertFalse(EstoqueItem.objects.exists())

    def test_formato_invalido_nao_vira_erro_interno(self):
        for dados in (
            [],
            {"itens": []},
            {"itens": ["ureia"]},
            {"itens": [self.item], "propriedade_id": "abc"},
        ):
            with self.subTest(dados=dados):
                self.assertEqual(self.enviar(dados).status_code, 400)
        self.assertFalse(EstoqueItem.objects.exists())

    def test_reenvio_reutiliza_confirmacao_inclusive_com_itens_corrigidos(self):
        primeira = self.enviar({"itens": [{**self.item, "quantidade": "15"}]})
        segunda = self.enviar({})
        self.assertEqual(primeira.status_code, 200)
        self.assertEqual(segunda.status_code, 200)
        self.assertTrue(segunda.json()["reutilizado"])
        self.assertEqual(primeira.json()["criados"], segunda.json()["criados"])
        self.assertEqual(EstoqueItem.objects.count(), 1)

    def test_reenvio_divergente_nao_duplica(self):
        self.enviar({})
        resposta = self.enviar({"itens": [{**self.item, "quantidade": "99"}]})
        self.assertEqual(resposta.status_code, 409)
        self.assertEqual(EstoqueItem.objects.count(), 1)

    def test_reenvio_em_outra_propriedade_nao_duplica(self):
        self.enviar({})
        outra = Propriedade.objects.create(
            user=self.usuario,
            nome="Segunda fazenda",
            area_total=20,
        )
        resposta = self.enviar({"propriedade_id": outra.pk})
        self.assertEqual(resposta.status_code, 409)
        self.assertEqual(EstoqueItem.objects.count(), 1)

    def test_rascunho_de_outro_usuario_nao_pode_ser_confirmado(self):
        outro = User.objects.create_user("outro-rascunho")
        self.rascunho.user = outro
        self.rascunho.save()
        self.assertEqual(self.enviar({}).status_code, 404)
        self.assertFalse(EstoqueItem.objects.exists())

    def test_novo_documento_nao_sobrescreve_rascunho_anterior(self):
        primeira = self.client.post("/api/ia/imagem-estoque/", {"texto": "Ureia 12 kg"})
        segunda = self.client.post("/api/ia/imagem-estoque/", {"texto": "Milho 15 kg"})
        self.assertEqual(primeira.status_code, 200)
        self.assertEqual(segunda.status_code, 200)
        self.assertNotEqual(
            primeira.json()["artefato_id"], segunda.json()["artefato_id"]
        )
        self.assertEqual(
            self.enviar({"artefato_id": primeira.json()["artefato_id"]}).status_code,
            200,
        )
        self.assertEqual(EstoqueItem.objects.get().nome, "Ureia")

    def test_nao_grava_em_propriedade_de_outro_usuario(self):
        outro = User.objects.create_user("ocr-outro")
        prop = Propriedade.objects.create(user=outro, nome="Outra", area_total=10)
        self.assertEqual(
            self.enviar({"itens": [self.item], "propriedade_id": prop.pk}).status_code,
            403,
        )
        self.assertFalse(EstoqueItem.objects.exists())

    def test_erro_na_segunda_escrita_reverte_a_primeira(self):
        original = EstoqueItem.objects.create
        chamadas = 0

        def criar(**kwargs):
            nonlocal chamadas
            chamadas += 1
            if chamadas == 2:
                raise IntegrityError("Falha simulada")
            return original(**kwargs)

        with (
            patch.object(EstoqueItem.objects, "create", side_effect=criar),
            self.assertRaises(IntegrityError),
        ):
            self.enviar({"itens": [self.item, self.item]})
        self.assertFalse(EstoqueItem.objects.exists())
