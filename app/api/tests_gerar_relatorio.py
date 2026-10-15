"""`gerar_relatorio` tem de gerar OU dizer que não gera. Nunca ficar a meio.

A FALHA QUE ESTE TESTE FECHA
============================
A versão anterior criava a linha com `status="processando"` e devolvia. Não
havia task Celery, não havia geração síncrona — apesar do comentário no código
dizer "For now: generate synchronously". O ficheiro nunca era escrito, e
`relatorio_status` respondia `processando` com `arquivo: null` para sempre.

Não é um botão avariado: é um botão que PROMETE um ficheiro e mente sobre o
estado. O produtor vê "a processar", espera, volta, e continua a ver "a
processar" — e a conclusão natural é que o sistema é lento, não que nunca vai
acabar.

Por isso o invariante é fechado: **nenhuma saída de `gerar_relatorio` pode
deixar a linha em `processando`.** Ou `concluido` com ficheiro, ou `erro` com
motivo. O motivo de o teste ser sobre o ESTADO e não sobre o ficheiro é que o
estado é o que o produtor vê.
"""

from django.contrib.auth.models import User
from django.test import TestCase

from app.api.views.relatorios import EXPORTADORES
from app.models import Propriedade, RelatorioGerado, RelatorioTemplate


class GerarRelatorioTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("produtor", password="x")
        self.client.force_login(self.user)
        # Uma propriedade SEM o que exportar. O endpoint responde 400 com "Nenhuma
        # propriedade" quando não há nenhuma — e isso é a resposta certa, não um
        # defeito. Mas para este teste o que interessa é o CAMINHO do ficheiro,
        # por isso a conta tem de ter propriedade para lá chegar.
        Propriedade.objects.create(
            user=self.user, nome="Sítio Boa Vista", area_total="120.00"
        )
        self.template = RelatorioTemplate.objects.create(
            user=self.user, nome="Custo da safra", tipo="financeiro", formato="csv"
        )

    def _pedir(self):
        return self.client.post(
            "/api/relatorio/gerar/",
            {"template_id": self.template.pk, "params": {}},
        )

    def test_nunca_deixa_processando(self):
        """O invariante. Vale para todos os formatos, e tem de continuar valendo
        quando alguém acrescentar um gerador a `EXPORTADORES`."""
        for formato in ("pdf", "excel", "csv"):
            with self.subTest(formato=formato):
                self.template.formato = formato
                self.template.save(update_fields=["formato"])
                r = self._pedir()
                rel = RelatorioGerado.objects.get(pk=r.json()["relatorio_id"])
                self.assertNotEqual(
                    rel.status,
                    "processando",
                    "a linha ficou a meio, que é a falha que este teste fecha",
                )

    def test_sem_gerador_da_erro_com_motivo(self):
        # 501 e não 200. Um 200 com `status: processando` é a mentira; um 501
        # com o motivo é a mesma informação com o código certo.
        r = self._pedir()
        self.assertEqual(r.status_code, 501)
        rel = RelatorioGerado.objects.get(pk=r.json()["relatorio_id"])
        self.assertEqual(rel.status, "erro")
        self.assertTrue(rel.erro_msg.strip())
        # E o motivo tem de dizer o que fazer a seguir. Um erro que só diz que
        # falhou obriga o produtor a procurar a resposta sozinho.
        self.assertIn("export/csv", rel.erro_msg)

    def test_o_status_diz_o_erro_e_nao_promete_ficheiro(self):
        r = self._pedir()
        rel = RelatorioGerado.objects.get(pk=r.json()["relatorio_id"])
        s = self.client.get(f"/api/relatorio/{rel.pk}/status/")
        self.assertEqual(s.status_code, 200)
        self.assertEqual(s.json()["status"], "erro")
        # `arquivo` tem de ser None: é isso que distingue "não gerado" de
        # "gerado e ainda não guardado".
        self.assertIsNone(s.json()["arquivo"])

    def test_template_inexistente_e_404(self):
        r = self.client.post(
            "/api/relatorio/gerar/", {"template_id": 999999, "params": {}}
        )
        self.assertEqual(r.status_code, 404)

    def test_o_ficheiro_que_se_quer_hoje_existe_e_trabalha(self):
        """O que o produtor DEVE usar enquanto não há gerador de template.

        Está aqui para o `erro_msg` não ser uma promessa: o caminho alternativo
        que ele aponta tem de responder 200 e devolver um ficheiro.
        """
        r = self.client.get("/api/export/csv/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r["Content-Type"])
        self.assertIn("attachment", r["Content-Disposition"])

    def test_o_exportador_vazio_e_a_decisao(self):
        # Não é um esquecimento: enquanto `configuracao` não tiver esquema, um
        # gerador seria código para um formato que ninguém definio. O teste
        # acima garante que a sua entrada é o ERRO, e não o `processando`.
        self.assertEqual(EXPORTADORES, {})
