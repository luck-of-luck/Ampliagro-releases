from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from app.models import LancamentoFinanceiro, LinhaFinanceiraImportada, Propriedade
from app.services.importacao_financeira import importar_lancamentos_csv


class ImportacaoFinanceiraCSVTest(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user("importador_csv")
        self.propriedade = Propriedade.objects.create(
            user=self.usuario, nome="Fazenda CSV", area_total=100
        )
        self.csv = "id;data;valor;descricao\nA;15/03/2026;100,00;Venda\nB;16/03/2026;-20,50;Compra"

    def importar(self, csv=None, **kwargs):
        parametros = {
            "usuario": self.usuario,
            "propriedade_id": self.propriedade.pk,
            "origem": "Sistema anterior",
            "arquivo": "historico.csv",
            "conteudo": (csv or self.csv).encode(),
        }
        parametros.update(kwargs)
        return importar_lancamentos_csv(**parametros)

    def test_grava_e_registra_origem_sem_inventar_pagamento_ou_classificacao(self):
        resultado = self.importar()
        self.assertEqual(resultado, {"criados": 2, "existentes": 0, "total": 2})
        trilha = LinhaFinanceiraImportada.objects.get(id_externo="B")
        self.assertEqual(trilha.fonte_dado, "declarado")
        self.assertEqual(trilha.importado_por, self.usuario)
        self.assertEqual(trilha.lancamento.valor, Decimal("20.50"))
        self.assertEqual(trilha.lancamento.tipo, "DESPESA")
        self.assertFalse(trilha.lancamento.pago)
        self.assertEqual(trilha.lancamento.tipo_lancamento_lcdpr, "")

    def test_reenvio_normalizado_preserva_edicao_posterior(self):
        self.importar()
        item = LinhaFinanceiraImportada.objects.get(id_externo="A").lancamento
        item.descricao = "Revisado pelo produtor"
        item.save()
        resultado = self.importar(self.csv.replace("100,00", "100"))
        self.assertEqual(resultado["existentes"], 2)
        self.assertEqual(LancamentoFinanceiro.objects.count(), 2)
        item.refresh_from_db()
        self.assertEqual(item.descricao, "Revisado pelo produtor")

    def test_conflito_reverte_linhas_novas_do_lote(self):
        self.importar()
        with self.assertRaises(ValidationError):
            self.importar(
                "id;data;valor;descricao\nC;15/03/2026;10;Nova\nA;15/03/2026;900;Venda"
            )
        self.assertEqual(LancamentoFinanceiro.objects.count(), 2)
        self.assertEqual(LinhaFinanceiraImportada.objects.count(), 2)

    def test_outro_usuario_nao_importa(self):
        outro = User.objects.create_user("outro_csv")
        with self.assertRaises(PermissionDenied):
            self.importar(usuario=outro)
        self.assertFalse(LancamentoFinanceiro.objects.exists())

    def test_linha_invalida_reverte_tudo(self):
        for antes, depois in (
            ("-20,50", "NaN"),
            ("-20,50", "0,001"),
            ("16/03/2026", "30/02/2026"),
            ("B;", "A;"),
        ):
            with self.subTest(depois=depois), self.assertRaises(ValidationError):
                self.importar(self.csv.replace(antes, depois))
            self.assertFalse(LancamentoFinanceiro.objects.exists())

    def test_mesmo_id_em_outra_origem_nao_colide(self):
        self.importar()
        resultado = self.importar(origem="Outro sistema")
        self.assertEqual(resultado["criados"], 2)

    def test_central_importa_e_mostra_erro_sem_gravacao_parcial(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.force_login(self.usuario)
        url = f"/gestao/central/?propriedade={self.propriedade.pk}&ano=2026"
        resposta = self.client.post(
            url,
            {
                "secao": "importacao_csv",
                "origem": "Sistema anterior",
                "arquivo": SimpleUploadedFile("dados.csv", self.csv.encode()),
            },
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(LancamentoFinanceiro.objects.count(), 2)
        pagina = self.client.get(url)
        self.assertContains(pagina, "Declarado · Sistema anterior · ID A")
        resposta = self.client.post(
            url,
            {
                "secao": "importacao_csv",
                "origem": "Sistema anterior",
                "arquivo": SimpleUploadedFile(
                    "dados.csv", self.csv.replace("100,00", "999,00").encode()
                ),
            },
        )
        self.assertContains(resposta, "conteúdo diferente", status_code=400)
        self.assertEqual(LancamentoFinanceiro.objects.count(), 2)
