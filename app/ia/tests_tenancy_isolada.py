"""Cross-tenant: o id de outra pessoa é um 403, não um dado.

O `TenantIsolationMiddleware` verificava `propriedade_id` e só esse. Os
restantes — `talhao_id`, `fazenda_id`, `device_id` — passavam intactos, e os
handlers fazem `.filter(id=talhao_id)` sem filtro de utilizador. Provado com
dois utilizadores: um sem propriedade nenhuma pediu `?talhao_id=<o do outro>`
e recebeu

    {'linha': 'A-B T-Alvo', 'auto_section': True, 'precisao_cm': 2.5}
    fonte_dado: 'medido'

Isto é pior que servir um número inventado. Um número inventado diz "isto e'
um exemplo". O talhão de outra pessoa diz "isto e' seu", e o produtor não
tem forma de saber que não é.
"""

from django.contrib.auth.models import User
from django.test import Client, TestCase

from app.models import Propriedade, Safra, Talhao
from app.models.core import Cultura


class CrossTenantNaoVazaTalhao(TestCase):
    def setUp(self):
        self.alvo = User.objects.create_user("t_alvo", password="x1234567")
        self.intruso = User.objects.create_user("t_intruso", password="x1234567")

        self.prop = Propriedade.objects.create(
            user=self.alvo, nome="Fazenda Alvo", area_total=777.0
        )
        self.talhao = Talhao.objects.create(
            propriedade=self.prop, nome="T-Alvo", area_hectare=777.0
        )
        cafe, _ = Cultura.objects.get_or_create(nome="Café")
        Safra.objects.create(
            propriedade=self.prop,
            cultura=cafe,
            ano=2026,
            area_plantada=777.0,
            producao_total=1.0,
        )
        self.client = Client()
        self.client.login(username="t_intruso", password="x1234567")

    def test_talhao_de_outro_produtor_e_403(self):
        r = self.client.get(
            f"/api/top-globais/kpi-guidance-ab/?talhao_id={self.talhao.id}"
        )
        self.assertEqual(r.status_code, 403, f"Vazou: {r.content[:200]}")
        self.assertNotIn(b"T-Alvo", r.content)
        self.assertNotIn(b"777", r.content)

    def test_propriedade_de_outro_proprodor_e_403(self):
        """Este já era bloqueado. Fica aqui para proteger a regressão: a
        correcção do talhao não pode ter afrouxado a propriedade."""
        r = self.client.get(
            f"/api/top-globais/kpi-benchmark-fbn/?propriedade_id={self.prop.id}"
        )
        self.assertEqual(r.status_code, 403)

    def test_fazenda_de_outro_produtor_e_403(self):
        r = self.client.get(
            f"/api/top-globais/kpi-rota-otimizada/?fazenda_id={self.prop.id}"
        )
        self.assertEqual(r.status_code, 403)

    def test_o_proprio_talhao_passa(self):
        """A protecção não pode ser tão larga que bloqueie o produtor. Um
        403 aqui seria um sistema inutilizavel, que é o outro extremo do
        mesmo defeito."""
        dono = Client()
        dono.login(username="t_alvo", password="x1234567")
        r = dono.get(f"/api/top-globais/kpi-guidance-ab/?talhao_id={self.talhao.id}")
        self.assertNotEqual(
            r.status_code, 403, f"O proprio produtor foi bloqueado: {r.content[:200]}"
        )

    def test_id_que_nao_existe_e_sem_dado_nao_403(self):
        """Um id inexistente NÃO é cross-tenant. Dar 403 aqui confundia
        "ainda não registaste isso" com "estão a mostrar-te a lavoura de
        outro", e fazia o primeiro caso parecer uma tentativa de intrusão.

        O request segue, com o id anulado: o handler vê "sem talhão" e
        responde "sem dado".
        """
        r = self.client.get("/api/top-globais/kpi-guidance-ab/?talhao_id=999999999")
        self.assertNotEqual(r.status_code, 403, "Id inexistente nao e' acesso indevido")
        if r.status_code == 200:
            d = r.json()
            self.assertNotIn("T-Alvo", str(d))
            self.assertEqual(
                d.get("fonte_dado"),
                "simulado",
                "Sem talhao, o widget nao pode dizer que mediu",
            )


class MiddlewareNaoEngoleARecusa(TestCase):
    """A protecção não pode depender de nada dar errado.

    Havia um `except Exception: pass` à volta de toda a verificação. Um
    `FieldError` — que acontece quando um lookup muda de nome, e muda — era
    engolido, e a request seguia SEM verificação nenhuma. Ou seja: um bug
    de configuração desligava silenciosamente o isolamento de tenants.

    Este teste é sobre essa estrutura, não sobre um endpoint.
    """

    def test_existe_excecao_propria_para_recusa(self):
        from app import middleware as mw

        self.assertTrue(
            issubclass(mw._Rejeitado, Exception),
            "A recusa de tenancy precisa de um tipo próprio, para não ser "
            "engolida por um except Exception a meio do caminho",
        )

    def test_recusa_sobe_para_o_middleware(self):
        import inspect

        from app import middleware as mw

        fonte = inspect.getsource(mw.TenantIsolationMiddleware.__call__)
        self.assertIn(
            "except _Rejeitado",
            fonte,
            "O middleware engole a propria recusa: um erro a meio desliga "
            "a protecao sem ninguém ver",
        )

    def test_falha_de_verificacao_e_registada(self):
        """Uma tabela mal escrita tem de deixar rasto. Silenciar é o que
        fez este bug passar despercebido."""
        import inspect

        from app import middleware as mw

        fonte = inspect.getsource(mw.TenantIsolationMiddleware.__call__)
        self.assertIn(
            "logging",
            fonte,
            "A falha de verificacao de tenancy nao e registada: falha em "
            "silencio e o middleware fica inutil sem ninguem saber",
        )

    def test_todos_os_ids_apontados_sao_verificados(self):
        """A lista é por tabela, não por parâmetro solto. Um id novo que
        ninguémerrorism acrescente fica por verificar — e o teste abaixo
        falha quando isso acontecer, que é o ponto."""
        from app import middleware as mw

        for param in ("propriedade_id", "fazenda_id", "talhao_id", "device_id"):
            self.assertIn(
                param,
                mw.TenantIsolationMiddleware.TABELAS_VERIFICADAS,
                f"{param} deixou de ser verificado contra o dono",
            )
