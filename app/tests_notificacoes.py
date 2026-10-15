"""A acção "testar notificação" não pode dar 500 — e não pode mentir.

O QUE ESTE FICHEIRO CONTESTA
===========================
Escrevi-o depois de encontrar `/api/notificacao-templates/<pk>/testar/` a dar
500. A causa era uma linha:

    financeiro_banco.py:242  from app.services.notificacoes import ...
                             ^^^ módulo inexistente

Qualquer POST na rota dava 500, e `test_superficie_servidor.py::SuperficieApiEscritaTest::test_um_500_nao_e_uma_recusa`
existia exactamente para apanhar isso — e falhava, porque o módulo nunca foi
escrito. Um teste que describe um bug por corrigir e continua a falhar é um
teste a dizer que o bug está vivo.

A SEGUNDA COISA, QUE É MAIS IMPORTANTE
======================================
`send_push_notification` é o nome de uma função que não envia push.
`PushSubscription` guarda `endpoint`, `p256dh` e `auth` — as chaves de uma
subscrição VAPID — mas não há `pywebpush` no `requirements.txt`, não há chave
VAPID em lado nenhum, e não há código que as use. A função que "envia push"
não tem para onde enviar.

A tentação, aqui, é devolver `{"enviados": N}` e ficar o assunto arrumado.
Isso é pior: o produtor vê "notificação enviada", fecha o ecrã, e o aviso
nunca chega. A regra deste serviço é que `entregue` é `False` enquanto o Web
Push não existir, e a view diz isso em texto.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from app.models import Notificacao, NotificacaoTemplate, PushSubscription


class TestarNotificacaoTest(TestCase):
    def setUp(self):
        from django.test import Client

        self.api = Client()
        self.superuser = User.objects.create_superuser(
            "root_templates", "root@x.com", "senhaforte123"
        )
        self.comum = User.objects.create_user(
            "comum_templates", "comum@x.com", "senhaforte123"
        )
        self.template = NotificacaoTemplate.objects.create(
            nome="aviso_teste",
            titulo="Alerta de {cultura}",
            mensagem="A {cultura} precisa de {quantidade} kg.",
            nivel="warning",
            variaveis=["cultura", "quantidade"],
        )
        PushSubscription.objects.create(
            user=self.superuser,
            endpoint="https://fcm.googleapis.com/fcm/send/abc123",
            p256dh="BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkrxZJjSgSnfckjBJuBkr3qBUYIHBQFLXYp5Nksh8U",
            auth="8eDyX_uCN0XRhSbY5hs7Hg",
        )

    def _url(self):
        return reverse("notificacao-template-testar", args=[self.template.pk])

    # --- o 500 ------------------------------------------------------------

    def test_a_rota_responde(self):
        """O que antes era 500. Uma acção de diagnóstico que rebenta não diz
        nada sobre o que está a ser diagnosticado."""
        self.api.force_login(self.superuser)
        r = self.api.post(self._url())
        self.assertEqual(
            r.status_code,
            200,
            f"a rota de testar deu {r.status_code}: {r.content[:300]}",
        )

    def test_o_modulo_existe_e_importa_sozinho(self):
        """O bug original era um import de um módulo inexistente. Importá-lo
        directamente é o teste mais próximo do sintoma."""
        from app.services.notificacoes import send_push_notification

        self.assertTrue(callable(send_push_notification))

    # --- o que a resposta diz ---------------------------------------------

    def test_a_resposta_diz_que_web_push_nao_esta_configurado(self):
        """`enviados: 1` seria uma mentira. O que é verdade: uma
        notificação foi registada no painel, e nada foi empurrado."""
        self.api.force_login(self.superuser)
        r = self.api.post(self._url())
        corpo = r.json()
        self.assertFalse(
            corpo.get("web_push_configurado"),
            "o Web Push nao esta configurado; diz-lo nao e' opcional",
        )
        self.assertEqual(corpo.get("entregues"), 0)
        self.assertNotIn(
            "enviados",
            corpo,
            "`enviados` e' o nome de uma entrega que nao aconteceu",
        )

    def test_a_notificacao_foi_registada_no_painel(self):
        """O que acontece de facto: o aviso fica no painel, que é onde o
        produtor o lê."""
        self.api.force_login(self.superuser)
        self.api.post(self._url())
        self.assertEqual(Notificacao.objects.count(), 1)
        n = Notificacao.objects.first()
        self.assertEqual(n.user_id, self.superuser.pk)
        self.assertEqual(n.nivel, "warning")
        # As variáveis foram substituídas — ou não eram variáveis, eram texto.
        self.assertIn("TESTE_cultura", n.mensagem)
        self.assertIn("TESTE_quantidade", n.mensagem)
        self.assertNotIn("{cultura}", n.mensagem)

    # --- a fronteira -----------------------------------------------------

    def test_send_nunca_levanta(self):
        """A regra do serviço. Um `None` onde se espera uma subscrição é
        entrada de bug, e entrada de bug não pode ser um 500."""
        from app.services.notificacoes import send_push_notification

        r = send_push_notification(None, "titulo", "mensagem")
        self.assertFalse(r["ok"])
        self.assertIsNone(r["notificacao_id"])

    def test_send_aceita_o_user_direto(self):
        """A assinatura aceita o objecto para o caller não ir buscar o user à
        mão — e errar aí é notificar a pessoa errada."""
        from app.services.notificacoes import send_push_notification

        r = send_push_notification(self.superuser, "titulo", "mensagem")
        self.assertTrue(r["ok"])
        self.assertEqual(
            Notificacao.objects.get(pk=r["notificacao_id"]).user_id,
            self.superuser.pk,
        )

    def test_nivel_fora_da_lista_caixa_info(self):
        """`nivel="urgent"` é um `ValueError` do Django no `choices`. Um
        500 por escrever "urgent" numa acção de diagnóstico é absurdo."""
        from app.services.notificacoes import send_push_notification

        r = send_push_notification(self.superuser, "t", "m", nivel="urgent")
        self.assertTrue(r["ok"])
        self.assertEqual(Notificacao.objects.get(pk=r["notificacao_id"]).nivel, "info")

    # --- quem pode chamar -------------------------------------------------

    def test_anonimo_nao_chega(self):
        r = self.api.post(self._url())
        self.assertIn(r.status_code, (302, 401, 403))

    def test_a_subscricao_tem_de_ser_de_superuser(self):
        """O filtro `user__is_superuser=True` é o que impede um produtor de
        receber o aviso de teste dos outros. Verifica-se que uma
        subscrição de um produtor comum não é notificada."""
        PushSubscription.objects.create(
            user=self.comum,
            endpoint="https://fcm.googleapis.com/fcm/send/comum999",
            p256dh="BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkrxZJjSgSnfckjBJuBkr3qBUYIHBQFLXYp5Nksh8U",
            auth="8eDyX_uCN0XRhSbY5hs7Hg",
        )
        self.api.force_login(self.superuser)
        self.api.post(self._url())
        self.assertFalse(
            Notificacao.objects.filter(user=self.comum).exists(),
            "o produtor comum nao devia receber o aviso de teste",
        )
