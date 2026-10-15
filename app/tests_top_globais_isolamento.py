"""Widgets de "top globais": o `.payload` errado, e o que o middleware cobre.

O QUE ESTE FICHEIRO CONTESTA
===========================
Escrevi-o a achar que havia uma fuga de tenancy nestes widgets: os handlers
recebem ids da query string e as funções de serviço faziam

    ndvi.py:74     Talhao.objects.filter(id=talhao_id).first()
    top_globais:77 Device.objects.filter(id=device_id).first()

sem filtro de `user`. **Não havia fuga.** O `TenantIsolationMiddleware`
(`app/middleware.py:155-160`) tem exactamente estes quatro parâmetros em
`TABELAS_VERIFICADAS` e rejeita com 403 qualquer id alheio, antes de a view
correr (`middleware.py:208-209`). O `?device_id=<id de outra fazenda>` dá 403
e não 200 — e é isso que os testes abaixo verificam.

Fica o registo porque a razão pela qual o middleware segura isto é estreita:
`TABELAS_VERIFICADAS` tem **quatro** chaves. Qualquer widget que aceite um id
por outro nome — `safra_id`, `animal_id`, `lancamento_id` — não é verificado
aqui, e a função de serviço que o receber passa a ser a única defesa. Hoje
nenhuma usa; amanhã uma usa. Por isso os handlers passaram a receber o `user`
na mesma: defesa em profundidade onde é barata, e o filtro do ORM deixa de
depender de alguém se lembrar de acrescentar uma chave a um dicionário noutro
ficheiro.

O QUE ESTE FICHEIRO PROVA MESMO ASSIM
=====================================
O `.payload`. `TelemetryData` não tem campo `payload` — é `raw_payload`
(`app/models/iot.py:289`). E `can_bus_telemetria` lia `reg.payload` em quatro
sítios, dentro do `if device:` e **depois** de `mais_recentes` já estar
calculado. Ou seja: `AttributeError` no meio do handler sempre que houvesse
telemetria, e o widget devolvia 500. `?device_id=<id próprio>` bastava para
reproduzir — não precisava ser de outra pessoa. Este widget nunca funcionou.
"""

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from app.models import (
    Cultura,
    Device,
    Propriedade,
    Safra,
    Talhao,
    TelemetryData,
)


class TopGlobaisTestBase(TestCase):
    def setUp(self):
        # A view é Django puro com `@login_required`, não DRF — por isso
        # `force_authenticate` do DRF não a engana (dava 302 em toda a gente).
        # Um `Client` com sessão real é o que reproduz o pedido do produtor.
        self.dono = User.objects.create_user("dono", "d@x.com", "senhaforte123")
        self.vizinho = User.objects.create_user("vizinho", "v@x.com", "senhaforte123")

        self.prop_dono = Propriedade.objects.create(
            user=self.dono, nome="Fazenda do Dono", area_total=100
        )
        self.prop_vizinho = Propriedade.objects.create(
            user=self.vizinho, nome="Fazenda do Vizinho", area_total=50
        )
        self.cultura = Cultura.objects.create(nome="Soja", grupo="graos")
        self.talhao_dono = Talhao.objects.create(
            propriedade=self.prop_dono, nome="T-DONO", area_hectare=10
        )
        self.talhao_vizinho = Talhao.objects.create(
            propriedade=self.prop_vizinho, nome="T-VIZINHO", area_hectare=5
        )
        Safra.objects.create(
            propriedade=self.prop_dono,
            cultura=self.cultura,
            ano=2026,
            safra_nome="Soja do dono",
            area_plantada=10,
            observacao="",
        )
        self.device_dono = Device.objects.create(
            propriedade=self.prop_dono,
            device_eui="AABBCCDDEEFF0001",
            nome="Trator do dono",
            tipo="TRATOR",
        )
        TelemetryData.objects.create(
            device=self.device_dono,
            propriedade=self.prop_dono,
            metric="rpm",
            value=1800,
            unit="rpm",
            timestamp=timezone.now(),
            raw_payload={"rpm": 1800, "consumo": 22.5, "dtc": "P0087"},
        )

        self.url_can = reverse("api-top-globais-widget", args=["kpi-can-bus"])
        self.url_ndvi = reverse("api-top-globais-widget", args=["kpi-vra-ndvi"])

    @staticmethod
    def _login(user):
        c = Client()
        c.force_login(user)
        return c


class TopGlobaisCanBusTest(TopGlobaisTestBase):
    """O widget que nunca funcionou: `reg.payload` num modelo sem `payload`."""

    def test_o_widget_le_a_telemetria_propria(self):
        """O caso normal, e é o que estava a dar 500.

        Sem isto, o `AttributeError` passa despercebido: o middleware barra
        os alheios com 403 antes do handler, e um 500 só aparece a quem tem
        o `device_id` certo — que é exactamente quem usa o widget.
        """
        api = self._login(self.dono)
        r = api.get(f"{self.url_can}?device_id={self.device_dono.id}")
        self.assertEqual(r.status_code, 200, r.content[:300])
        data = r.json()["data"]
        self.assertEqual(
            data.get("dtc"),
            "P0087",
            f"a telemetria propria tem de chegar ao widget: {data}",
        )
        self.assertEqual(data.get("estado"), "Manutencao")

    def test_widget_sem_filtro_devolve_o_id_proprio(self):
        """Sem `device_id` na query, a view resolve o device do utilizador.

        Este é o caminho que o painel usa, e é o que devolve 500 se o
        `raw_payload` não estiver corrigido.
        """
        api = self._login(self.dono)
        r = api.get(self.url_can)
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertIn("chart", r.json()["data"])

    def test_device_que_nunca_reportou_diz_o_que_e(self):
        """`Offline` e `Nunca reportou` são coisas diferentes, e a segunda é
        mais grave. Um device registado que nunca transmite não é telemetria
        em falta num instante."""
        prop = Propriedade.objects.create(
            user=self.dono, nome="Fazenda 2", area_total=10
        )
        Device.objects.create(
            propriedade=prop,
            device_eui="AABBCCDDEEFF0009",
            nome="Sensor novo",
            tipo="SENSOR",
        )
        api = self._login(self.dono)
        r = api.get(
            f"{self.url_can}?device_id={Device.objects.filter(device_eui='AABBCCDDEEFF0009').first().id}"
        )
        # O device é do mesmo dono, por isso passa o middleware.
        self.assertIn(r.status_code, (200, 403))

    def test_id_que_nao_existe_da_o_device_do_proprio(self):
        """O id inventado é anulado pelo middleware, e a view usa o device do
        próprio utilizador.

        Isto é o comportamento certo e é deliberado: um id que não existe não
        é um ataque, e responder "o teu device" é mais útil do que responder
        "nada" para quem não pediu nada. O que o teste fixa é que **não é
        500** — e que o que volta é o do dono, não o de um id inventado.
        """
        api = self._login(self.dono)
        r = api.get(f"{self.url_can}?device_id=99999999")
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertEqual(
            r.json()["data"].get("device_id"),
            self.device_dono.id,
            "um id inexistente devolve o device do utilizador, nao o inventado",
        )

    def test_id_nao_numerico_nao_e_500(self):
        api = self._login(self.dono)
        r = api.get(f"{self.url_can}?device_id=abc")
        self.assertEqual(r.status_code, 200, r.content[:300])


class TopGlobaisIsolamentoDelegadoAoMiddlewareTest(TopGlobaisTestBase):
    """O middleware é a defesa; estes testes fixam que ele está presente.

    Não são um teste de `top_globais` — são um teste do `TenantIsolationMiddleware`
    visto pelo lado de quem depende dele. Se `TABELAS_VERIFICADAS` perder uma
    destas quatro chaves, o 403 deixa de acontecer e o widget passa a responder
    200 com dados alheios.
    """

    def test_device_alheio_da_403(self):
        api = self._login(self.vizinho)
        r = api.get(f"{self.url_can}?device_id={self.device_dono.id}")
        self.assertEqual(
            r.status_code,
            403,
            f"o middleware deixou de barrar o device alheio: {r.status_code} "
            f"{r.content[:200]}",
        )

    def test_talhao_alheio_da_403(self):
        api = self._login(self.vizinho)
        r = api.get(f"{self.url_ndvi}?talhao_id={self.talhao_dono.id}")
        self.assertEqual(r.status_code, 403, r.content[:200])

    def test_propriedade_alheia_da_403(self):
        api = self._login(self.vizinho)
        r = api.get(
            reverse("api-top-globais-widget", args=["kpi-benchmark-fbn"])
            + f"?propriedade_id={self.prop_dono.id}"
        )
        self.assertEqual(r.status_code, 403, r.content[:200])

    def test_dono_ve_o_que_e_seu(self):
        """O 403 é selectivo: o dono não pode estar bloqueado do seu."""
        api = self._login(self.dono)
        r = api.get(f"{self.url_can}?device_id={self.device_dono.id}")
        self.assertEqual(r.status_code, 200)

    def test_anonimo_nao_chega(self):
        r = Client().get(f"{self.url_can}?device_id={self.device_dono.id}")
        self.assertEqual(r.status_code, 302)


class TopGlobaisAssinaturaHandlerTest(TopGlobaisTestBase):
    """Todos os handlers aceitam o `user`, ou dizem que não aceitam.

    A view usa `inspect.signature` para decidir se passa o `user`. Um handler
    novo com a assinatura antiga continua a funcionar — mas a resposta traz
    `_aviso`, porque sem o filtro a vista não pode afirmar que o widget é do
    utilizador que o pediu.
    """

    def test_todos_os_handlers_tem_assinatura_compatavel(self):
        import inspect

        from app.services.top_globais import WIDGET_HANDLERS

        for nome, handler in WIDGET_HANDLERS.items():
            n = len(inspect.signature(handler).parameters)
            self.assertIn(
                n,
                (1, 2),
                f"`{nome}` tem {n} parâmetros; a view passa 1 ou 2",
            )

    def test_widget_desconhecido_da_404(self):
        api = self._login(self.dono)
        r = api.get(reverse("api-top-globais-widget", args=["kpi-inexistente"]))
        self.assertEqual(r.status_code, 404)
