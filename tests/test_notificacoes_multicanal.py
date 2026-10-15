"""`NotificacaoTemplate.canais` e' lido. E diz-se, por canal, o que saiu.

POR QUE ESTE FICHEIRO EXISTE
===========================
MEDIDO 2026-10-05 (agente 7). O campo existe ha muito tempo:

    app/models/financeiro.py:375
        canais = models.JSONField(
            default=list, help_text="Ex: ['push', 'email', 'whatsapp']"
        )

E **nada no codebase iterava essa lista**. A unica accao que envia — `testar`,
em `app/api/views/financeiro_banco.py` — fazia sempre
`send_push_notification(...)`, queimando o canal configurado. Um template com
`canais: ["email"]` registava uma notificacao no painel, nunca mandava email, e
respondia `ok: true`.

E' a mesma classe de defeito do Caderno (o cliente chamava uma rota que nao
existia) e do custo-por-talhao (a coluna `talhao` que o escritor nunca
preenchia): **o esquema promete, o codigo nao cumpre, e nada se queixa.** Um
campo JSON de configuracao sem ninguem que o leia nao e' configuracao — e'
decoracao.

A REGRA DESTE FICHEIRO
======================
Cada canal responde por si. Um template com `["push", "email", "whatsapp"]`
numa instalacao sem backend de email e sem provedor de WhatsApp tem de dizer
**"1 de 3 entregou"** — e dizer porque os outros dois nao. Um dispatcher que
devolvesse um unico booleano repetiria o defeito com mais uma camada: o
produtor veria "ok" e nao saberia que dois dos tres avisos nao foram dados.

O QUE ESTE FICHEIRO NAO PROVA
=============================
Que o WhatsApp funciona. Nao funciona, e `test_whatsapp_diz_o_que_falta` exige
que o dispatcher **diga** que nao ha provedor. Um stub a devolver
`entregue: True` seria o defeito de `nfe.ClienteDFe` e de
`erp_externo.webhook_jbs_abate` — numeros plausiveis sem nada por tras.
"""

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from app.models import Notificacao, NotificacaoTemplate
from app.services.notificacoes import (
    canais_conhecidos,
    disparar_canais,
    send_push_notification,
)


class DespachoMulticanalTest(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("joao", "joao@exemplo.com.br", "x1234567")
        self.user = User.objects.create_user("maria", password="x1234567")

    def test_o_campo_canais_e_agora_lido(self):
        """Um canal pedido tem de chegar ao handler. Este e' o teste da promessa."""
        r = disparar_canais(["inapp"], self.user, "Aviso", "O talhao 3 esta seco")

        self.assertTrue(r["ok"])
        self.assertIn("inapp", r["por_canal"])
        self.assertTrue(r["por_canal"]["inapp"]["entregue"])
        self.assertEqual(Notificacao.objects.filter(user=self.user).count(), 1)

    def test_push_e_email_nao_e_o_mesmo_que_inapp(self):
        """`push` nao e' atalho para `inapp`. E' uma distincao que custou uma
        mentira.

        A primeira versao deste dispatcher mapeava `push` para o registo no
        painel e respondia `entregue: True` a um pedido de Web Push — que
        nunca saiu do servidor. O nome do canal e' o que o produtor le na
        configuracao; um `push` que "entrega" no painel e' pior do que um
        `push` que nao entrega, porque parece funcionar.

        Web Push nao existe neste projecto: nao ha `pywebpush` nem `vapid` no
        `requirements.txt`, e nao ha chave VAPID. Por isso `push` responde
        `entregue: False` com o motivo — e `inapp` e' o que registra.
        """
        r = disparar_canais(["push"], self.user, "Aviso", "texto")

        self.assertFalse(
            r["por_canal"]["push"]["entregue"],
            "`push` disse que entregou. Nao ha Web Push configurado — nada "
            "saiu do servidor.",
        )
        self.assertIn("Web Push nao configurado", r["por_canal"]["push"]["motivo"])
        self.assertEqual(
            Notificacao.objects.count(),
            0,
            "`push` registou no painel. Quem registra no painel e' `inapp`.",
        )

    def test_inapp_registra_e_diz_que_entregou(self):
        """O unico canal que entrega hoje, e diz que entrega."""
        r = disparar_canais(["inapp"], self.user, "Aviso", "texto")

        self.assertTrue(r["por_canal"]["inapp"]["entregue"])
        self.assertEqual(Notificacao.objects.count(), 1)

    def test_varios_canais_e_um_por_canal(self):
        """4 pedidos, 4 respostas, com `entregue` a falar de cada um.

        `entregue` no topo e' verdadeiro se **pelo menos um** entregou. Aqui so
        o `inapp` entrega, e o dispatcher tem de o dizer sem esconder os tres
        que nao entregaram.
        """
        r = disparar_canais(
            ["inapp", "push", "email", "whatsapp"], self.user, "Aviso", "texto"
        )

        self.assertEqual(set(r["por_canal"]), {"inapp", "push", "email", "whatsapp"})
        self.assertTrue(r["entregue"])
        self.assertTrue(r["por_canal"]["inapp"]["entregue"])
        for canal in ("push", "email", "whatsapp"):
            self.assertFalse(
                r["por_canal"][canal]["entregue"],
                f"{canal} disse que entregou e nao ha provedor para ele.",
            )
        for canal, detalhe in r["por_canal"].items():
            self.assertIn("motivo", detalhe, f"{canal} nao diz o que aconteceu")

    def test_email_sem_backend_real_nao_diz_que_entregou(self):
        """`EMAIL_BACKEND` de teste nao envia nada.

        O repo so tem `console` (dev) e `locmem` (test) — nao ha backend de
        producao. Dizer "email enviado" com um destes seria inventar a
        entrega, que e' o que o resto deste repositorio nao faz.
        """
        r = disparar_canais(["email"], self.u, "Aviso", "texto")

        self.assertFalse(r["por_canal"]["email"]["entregue"])
        self.assertIn("nao entrega", r["por_canal"]["email"]["motivo"])

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_utilizador_sem_email_diz_que_nao_tem_destinatario(self):
        sem_email = User.objects.create_user("sem", password="x1234567")
        r = disparar_canais(["email"], sem_email, "Aviso", "texto")

        self.assertFalse(r["por_canal"]["email"]["entregue"])
        self.assertIn("email", r["por_canal"]["email"]["motivo"])

    def test_whatsapp_diz_o_que_falta_e_nao_finge(self):
        """O canal onde a competencia investe, e que aqui nao existe.

        `grep whatsapp|twilio|wablas` em `app/` da so a string de ajuda do
        proprio campo que este ficheiro testa. O dispatcher tem de dizer
        isso, com o que falta para o ligar.
        """
        r = disparar_canais(["whatsapp"], self.user, "Aviso", "texto")

        detalhe = r["por_canal"]["whatsapp"]
        self.assertFalse(detalhe["entregue"])
        self.assertIn("nao configurado", detalhe["motivo"])
        # Antes exigia a palavra "provedor". Agora exige que a mensagem NOMEIE
        # o que falta — e' a mesma garantia com mais informacao: um produtor
        # que le "faltam: WHATSAPP_ACCESS_TOKEN, ... " sabe o que resolver.
        for chave in ("WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID"):
            self.assertIn(
                chave,
                detalhe["motivo"],
                "a mensagem tem de dizer COMO se liga, nao so que falta algo",
            )

    def test_canal_desconhecido_e_dito_nao_ignorado(self):
        """Um nome errado tem de aparecer na resposta.

        Silenciar um canal desconhecido seria a mesma classe de bug: o
        produtor acredita que configurou e nao aconteceu nada.
        """
        r = disparar_canais(["telepatia"], self.user, "A", "B")

        self.assertFalse(r["ok"])
        self.assertEqual(r["desconhecidos"], ["telepatia"])
        self.assertIn("desconhecido", r["por_canal"]["telepatia"]["motivo"])

    def test_sem_canais_nao_assume_um(self):
        """`default=list` significa "ninguem escolheu". Nao e' "in-app".

        Sem lista, o dispatcher nao adivinha. Adivinhar seria fazer o
        produtor receber avisos num canal que nao pediu.
        """
        r = disparar_canais([], self.user, "Aviso", "texto")

        self.assertFalse(r["ok"])
        self.assertFalse(r["entregue"])
        self.assertEqual(Notificacao.objects.count(), 0)
        self.assertIn("nao tem canais", r["motivo"])

    def test_string_solta_e_aceite(self):
        """`canais: "push"` (string em vez de lista) nao pode rebentar.

        E' um JSONField: o `admin` aceita uma string, e um dispatcher que
        presume lista devolve `TypeError` — e um 500.
        """
        r = disparar_canais("push", self.user, "Aviso", "texto")

        self.assertTrue(r["ok"])
        self.assertEqual(r["pedidos"], ["push"])

    def test_o_dispatcher_nunca_levanta(self):
        """Regra do modulo: quem chama e' UI ou agente.

        Um handler partido tem de dar `entregue: False` com motivo, nao
        rebentar o pedido que o disparou.

        Nota sobre *onde* se faz o patch: `_HANDLERS` guarda referencias
        directas as funcoes, por isso trocar `mod._disparar_inapp` nao afecta
        o mapa — o teste anterior achava que o tinha partido e o dispatcher
        entregava na mesma. Patch no dicionario, que e' o que o dispatcher
        consulta de facto.
        """
        from app.services import notificacoes as mod

        def explode(*_a, **_k):
            raise RuntimeError("canal partido")

        mod._HANDLERS["inapp"] = explode
        try:
            r = mod.disparar_canais(["inapp"], self.user, "A", "B")
        finally:
            mod._HANDLERS["inapp"] = mod._disparar_inapp

        self.assertFalse(r["entregue"])
        self.assertIn("RuntimeError", r["por_canal"]["inapp"]["motivo"])

    def test_os_canais_conhecidos_sao_documentados(self):
        """A lista que o modelo sugere tem de existir de facto.

        Se o `help_text` sugerir um canal que o dispatcher nao conhece, o
        produtor escreve, nao acontece nada, e o bug volta — por outra porta.
        """
        for canal in canais_conhecidos():
            self.assertIn(canal, ("inapp", "push", "email", "whatsapp"))

    def test_o_nivel_cai_a_info_quando_e_desconhecido(self):
        """`nivel` tem `choices` no modelo; escrever "urgent" daria 500 no DB."""
        r = disparar_canais(["inapp"], self.user, "A", "B", nivel="urgent")

        self.assertTrue(r["ok"])
        self.assertEqual(Notificacao.objects.get().nivel, "info")


class SendPushContinuaIgualTest(TestCase):
    """`send_push_notification` nao foi decomposto — e nao deve ser.

    Seis pontos do projecto chamam-no directamente (`proativo.py`,
    `alert_engine.py`, `gerar_alertas.py`, `signals.py`, `user.py`). Se
    passasse a exigir `canais`, quebro seis call sites para nao ganhar nada:
    `disparar_canais` cobre o caminho novo, e este continua a cobrir o
    registo in-app de quem ja sabia o que queria.
    """

    def test_continua_a_devolver_o_que_aconteceu(self):
        u = User.objects.create_user("direto", password="x1234567")
        r = send_push_notification(u, "Titulo", "Mensagem")

        self.assertTrue(r["ok"])
        self.assertFalse(r["entregue"])
        self.assertEqual(Notificacao.objects.count(), 1)


class TestarUsaOsCanaisDoTemplateTest(TestCase):
    """A accao `testar` itera `template.canais`, e devolve o resultado por canal.

    Este e' o ponto onde o defeito era visivel ao produtor: `POST
    /api/notificacao-templates/<pk>/testar/` com um template `["email"]`
    respondia `ok: true` sem nunca tocar num email.
    """

    def setUp(self):
        from app.models import PushSubscription

        self.superuser = User.objects.create_superuser(
            "admin", "admin@exemplo.com.br", "x1234567"
        )
        PushSubscription.objects.create(
            user=self.superuser,
            endpoint="https://exemplo.test/push/1",
            p256dh="k",
            auth="a",
        )
        self.template = NotificacaoTemplate.objects.create(
            nome="Aviso de teste",
            titulo="Alerta",
            mensagem="A safra de {cultura}",
            # `variaveis` e' o que faz a substituicao. Sem esta lista o
            # `{cultura}` fica literal — e foi o que este teste apanhou na
            # primeira versao: um template sem variaveis nao tem o que
            # substituir, e o teste escrevia "TESTE_cultura" na assercao sem
            # nunca o ter pedido.
            variaveis=["cultura"],
            # `inapp` e' o canal que **entrega** hoje (registo no painel).
            # `push` e' Web Push, que nao existe — e por isso vai na lista: o
            # template tem de mostrar os dois, um a entregar e outro nao, e o
            # `por_canal` tem de os distinguir.
            canais=["inapp", "push", "email", "whatsapp"],
        )
        self.client.force_login(self.superuser)

    def test_a_resposta_tem_o_por_canal(self):
        r = self.client.post(f"/api/notificacao-templates/{self.template.id}/testar/")

        self.assertEqual(r.status_code, 200, r.content[:200])
        corpo = r.json()

        self.assertEqual(
            corpo["canais_configurados"],
            ["inapp", "push", "email", "whatsapp"],
        )
        # `por_canal` leva uma **lista por canal**: uma entrada por
        # destinatario, porque o mesmo aviso vai para varias subscricoes e nem
        # todas vao entregar. Com um destinatario (o superuser) a lista tem um.
        for canal in ("inapp", "push", "email", "whatsapp"):
            self.assertIn(canal, corpo["por_canal"])

        inapp = corpo["por_canal"]["inapp"][0]
        push = corpo["por_canal"]["push"][0]
        email = corpo["por_canal"]["email"][0]
        whats = corpo["por_canal"]["whatsapp"][0]

        # 1 de 4: so o painel entrega.
        self.assertTrue(inapp["entregue"])
        self.assertFalse(push["entregue"])
        self.assertFalse(email["entregue"])
        self.assertFalse(whats["entregue"])
        self.assertIn("motivo", whats)

        # E `entregues` conta **entregas ao dispositivo**, que sao zero: nem o
        # painel nem o resto sao uma entrega ao telefone. E' o sentido que este
        # campo sempre teve, e que `app/tests_notificacoes.py` trava.
        self.assertEqual(
            corpo["entregues"],
            0,
            "`entregues` contou um registo no painel como entrega ao "
            "dispositivo. Nada saiu do servidor.",
        )

    def test_a_variavel_do_template_e_substituida(self):
        self.client.post(f"/api/notificacao-templates/{self.template.id}/testar/")

        registada = Notificacao.objects.get()
        self.assertIn("TESTE_cultura", registada.mensagem)
        self.assertNotIn("{cultura}", registada.mensagem)
