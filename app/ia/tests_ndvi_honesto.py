"""NDVI é uma medição. Um hash não é.

`NDVIService.process_talhao_ndvi` devolvia
`max(0.4, min(0.88, 0.55 + sha256(talhao_id-semana) % 300 / 1000))`. Não havia
uma única chamada à Copernicus no repositório — o nome "Sentinel-2" vivia no
`return`.

O que tornava isso grave não era o número: era a etiqueta. O heatmap
desenhava esse valor a cheio, com o veredicto agronómico ("Excelente" /
"Atenção (Baixo Vigor)") ao lado e a frase `Sentinel-2 L2A • nuvens 12%`
impressa por baixo. Um produtor a decidir irrigar por aquela cor estava a
olhar para uma imagem de satélite falsificada com o carimbo do satélite
verdadeiro.

A docstring chegou a escrever "NDVI real por talhão". Não usava.
"""

import os
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase

from app.models import Propriedade, Talhao


class NdviNaoEUmHash(TestCase):
    def test_modulo_nao_importa_hashlib(self):
        """`hashlib` saiu. A sua presença seria o sintoma do defeito:
        um valor derivado de um id não é uma medicao da planta.

        Procura-se no AST, e não no texto: o docstring deste serviço nomeia
        o `sha256` para explicar o que mudou, e um teste que lesse o
        ficheiro inteiro falharia por causa da propria explicação.
        """
        import ast
        import inspect

        from app.services import ndvi

        arvore = ast.parse(inspect.getsource(ndvi))
        importados = set()
        for no in ast.walk(arvore):
            if isinstance(no, ast.Import):
                importados.update(a.name.split(".")[0] for a in no.names)
            elif isinstance(no, ast.ImportFrom) and no.module:
                importados.add(no.module.split(".")[0])

        self.assertNotIn(
            "hashlib",
            importados,
            "ndvi voltou a importar hashlib: volta a fabricar a medicao a partir do id",
        )

    def test_sem_credencial_nao_ha_ndvi(self):
        from app.services.ndvi import NDVIService

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("COPERNICUS_USER", None)
            os.environ.pop("COPERNICUS_PASSWORD", None)
            d = NDVIService.process_talhao_ndvi(1)

        self.assertIsNone(d["ndvi_medio"], "NDVI numerico sem fonte Copernicus")
        self.assertIsNone(d["cobertura_nuvens"], "nuvens inventadas")
        self.assertIsNone(d["satelite"], "carimbo de satellite sem satelite")
        self.assertIsNone(d["sanidade"], "veredicto agronomico sem medicao")
        self.assertIsNone(d["data_captura"], "data de captura de um dado inexistente")
        self.assertEqual(d["fonte_dado"], "indisponivel")
        self.assertTrue(d["motivo"], "indisponivel sem motivo")

    def test_credencial_presente_nao_e_o_que_carimba(self):
        """O bug anterior no `top_globais` marcava 'medido' so porque a
        variavel de ambiente existia. Ter a chave no `.env` nao descarrega
        um pixel."""
        from app.services.ndvi import NDVIService

        with patch.dict(
            os.environ,
            {"COPERNICUS_USER": "u", "COPERNICUS_PASSWORD": "p"},
            clear=False,
        ):
            d = NDVIService.process_talhao_ndvi(1)

        self.assertNotEqual(
            d["fonte_dado"],
            "medido",
            "Credencial configurada foi tomada como medicao feita",
        )
        self.assertIsNone(d["ndvi_medio"])


class HeatmapNaoDesenhaSateliteFalso(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("t_ndvi", password="x1234567")
        self.prop = Propriedade.objects.create(
            user=self.user, nome="F", area_total=10.0
        )
        self.talhao = Talhao.objects.create(
            propriedade=self.prop, nome="T1", area_hectare=10.0
        )
        self.client = Client()
        self.client.login(username="t_ndvi", password="x1234567")

    def test_sem_ndvi_o_svg_diz_sem_ndvi(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("COPERNICUS_USER", None)
            os.environ.pop("COPERNICUS_PASSWORD", None)
            r = self.client.get(f"/api/talhao/{self.talhao.id}/ndvi-heatmap/")

        self.assertEqual(r.status_code, 200)
        corpo = r.content.decode("utf-8")
        self.assertIn("Sem NDVI", corpo)
        # O carimbo do satelite nao pode aparecer sem satelite.
        self.assertNotIn("Sentinel-2 L2A •", corpo)
        for veredicto in ("Excelente", "Bom", "Atenção (Baixo Vigor)"):
            self.assertNotIn(
                f">{veredicto}<", corpo, f"Veredicto '{veredicto}' sem medicao"
            )

    def test_payload_diz_indisponivel(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("COPERNICUS_USER", None)
            os.environ.pop("COPERNICUS_PASSWORD", None)
            r = self.client.get(f"/api/agronomia/ndvi/?talhao_id={self.talhao.id}")

        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertIsNone(d["ndvi_medio"])
        self.assertEqual(d["fonte_dado"], "indisponivel")
        self.assertTrue(d["motivo"])
