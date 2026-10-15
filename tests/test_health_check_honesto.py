"""Um health check que da verde em cima de stub nao e' um health check.

POR QUE ESTE FICHEIRO EXISTE
===========================
MEDIDO 2026-10-04: `app/services/erp_externo.py:111 health_check()` devolvia

    {"erp_externo": "✅ operacional (3 webhooks stub)"}

Tres coisas erradas numa linha:

1. **"operacional"** e' um veredicto sobre o mundo exterior. Nao havia SAP
   ligado — `webhook_jbs_abate` e' um stub com defaults `None`, e o proprio
   docstring diz "NAO TEM ROTA".
2. **"3 webhooks"** contava funcoes que existem, nao webhooks que responderam.
   Uma funcao que ninguem chama conta igual a uma que responde.
3. O **✅** era o green check que `docs/sistema/7.md` §1 manda nunca escrever
   sobre stub. Um health check e' precisamente o componente que existe para
   este caso nao enganar ninguem — e e' o primeiro a enganar.

O AGRAVANTE
===========
`webhook_jbs_abate` ja tinha sido corrigido *neste* repositorio. O seu
docstring explica, com razao, que "um stub que devolve numeros plausiveis e'
mais perigoso do que um stub que devolve `None`". E mesmo assim, o
`health_check` ao lado continuava a anunciar "✅ operacional".

Alguem pode ter corrigido a funcao e nao o health check. E e' por isso que
este teste existe: `webhook_jbs_abate` pode voltar a ser corrigido, ou nao, e
o health check tem de reflectir a realidade em qualquer dos casos. Um teste
que so verifica a funcao deixa o health check parado no tempo.
"""

from django.test import SimpleTestCase

from app.services.erp_externo import (
    health_check,
    webhook_eurochem_insumo,
    webhook_jbs_abate,
)


class HealthCheckNaoMenteTest(SimpleTestCase):
    def test_o_health_check_nao_da_verde(self):
        estado = health_check()
        texto = " ".join(str(v) for v in estado.values() if isinstance(v, str))

        self.assertNotIn(
            "✅",
            texto,
            "um health check nao escreve um tick verde sobre stub. Ver o "
            "docstring de webhook_jbs_abate, que explica por que razao.",
        )

    def test_o_health_check_diz_que_nao_esta_ligado(self):
        estado = health_check()

        self.assertFalse(
            estado.get("ligado"),
            "o health check afirma que ha integracao onde nao ha. "
            "webhook_jbs_abate nao tem rota — o docstring diz 'NAO TEM ROTA'.",
        )
        self.assertEqual(estado.get("integracoes_com_rota"), 0)

    def test_a_conta_dos_stubs_nao_e_conta_de_respostas(self):
        """`3 stubs` e' honesto. `3 webhooks` nao era.

        A diferenca entre os dois e' a diferenca entre "existem tres
        funcoes neste ficheiro" e "tres sistemas responderam". O health check
        tem de poder dizer a primeira sem parecer que disse a segunda.
        """
        estado = health_check()

        self.assertIn("stubs", estado)
        # O numero de integracoes que responderam e' zero, e o health check
        # tem de o dizer com um zero.
        self.assertIn("integracoes_com_rota", estado)

    def test_o_stub_nao_inventa_numeros(self):
        """O stub devolve `None`, nao cabecas de gado de um artigo.

        Este teste existe porque o valor por omissao ja foi `cabecas=10721000`
        e `recorde=True`, com a fonte escrita como "Globo Rural 2026-09". Um
        default nao pode afirmar um facto sobre o mundo.
        """
        payload = webhook_jbs_abate()

        self.assertIsNone(payload["dados"]["cabecas"])
        self.assertIsNone(payload["dados"]["recorde"])
        self.assertIsNone(payload["dados"]["fonte"])
        self.assertIn("stub", payload["dados"]["status"].lower())

    def test_o_stub_do_insumo_nao_tem_propriedade_alheia_nos_defaults(self):
        """`webhook_eurochem_insumo` tinha `falta="enxofre"`, `suspensos=450`,
        `local="Serra do Salitre"` por omissao.

        Um default e' uma assinatura. Com estes, quem chamasse a funcao sem
        argumentos gravava uma propriedade e um numero de cabeças como se o
        produtor os tivesse dito — e o `health_check` dizia "operacional".

        Este teste e' o gemeo do de cima, para o outro stub: o SAP foi
        corrigido, o Protheus nao foi, e sem um teste que o apanhe volta.
        """
        payload = webhook_eurochem_insumo()

        self.assertIsNone(payload["dados"]["insumo"])
        self.assertIsNone(payload["dados"]["suspensos"])
        self.assertIsNone(payload["dados"]["local"])
        self.assertIsNone(payload["dados"]["fonte"])

    def test_o_stub_do_insumo_nao_recomenda_um_fornecedor(self):
        """A alternativa vinha com nome e data: `"Yara biológicos (Globo Rural
        2026-09)"`.

        Nao se recomenda um fornecedor a um produtor sem consultar o cadastro
        de insumos dele. A referencia a um artigo e' citavel — e nao e' a fonte
        de um dado que este sistema mediu.
        """
        payload = webhook_eurochem_insumo()
        self.assertIsNone(payload["dados"]["alternativa"])
