"""O simulador de lucro tinha preços inventados — e uma decisão depende deles.

O QUE ERA
---------
`simular_lucro` fazia:

    prod  = _num(params.get("produtividade")) or _num(params.get("produtividade_sc_ha")) or 60
    preco = _num(params.get("preco")) or _num(params.get("preco_sc")) or 150
    custo = _num(params.get("custo_ha")) or 380

E respondia:

    "Simulação 100 ha (60 sc/ha a R$ 150): base R$ 340.000,00;
     pessimista R$ ...; otimista R$ ... Equilíbrio: 63.3 sc/ha."

Três números que o produtor nunca deu, apresentados dentro de uma frase
que parece um cálculo.

POR QUE ISTO É PIOR QUE O `umidade: 50`
---------------------------------------
O `umidade: 50` estava num canto de cartão, e passa despercebido. Uma
simulação de lucro responde a "vale a pena plantar isto?" — e quem lê
"60 sc/ha a R$ 150" sem perceber que foram escolhidos por um `or`
decide o plantio com números inventados. O resultado tem o aspecto de
uma conta feita com dados.

A área é o que o produtor deu (vem do talhão). O resto, ou vem dele, ou o
simulador diz que não sabe.

O `or` TAMBÉM E' UM BUG DE SEPARADO
----------------------------------
`_num("0")` devolve `0.0`, que é falsy. Com `or`, um custo de R$ 0/ha que
o produtor deu — que é uma informação válida — caía no `380` default.
Um zero e' um dado; None é uma ausência. Por isso o teste do zero
existe, e não é um teste de cobertura: é a diferença entre "ninguém disse
nada" e "alguém disse zero".
"""

from django.test import TestCase

from app.ia import intents3


class FakesParametros(dict):
    """Só para readability nos testes — `params` é um dict."""


class TestSimuladorNaoAssumePrecos(TestCase):
    def _chama(self, **params):
        from app.models.core import Propriedade, Talhao

        # Uma propriedade real: o handler lê `propriedade_id` e resolve o
        # talhão. Um duplo aqui exigiria reproduzir `_prop3`, que é
        # lógica de negocio com tenancy — e o que se quer testar é a
        # ausência de defaults, não a resolução da propriedade.
        user = self._utilizador()
        prop = Propriedade.objects.create(
            user=user, nome="Faz Teste Sim", area_total=100
        )
        Talhao.objects.create(
            propriedade=prop,
            nome="T1",
            area_hectare=100,
            cultura_atual=None,
        )
        params = dict(params)
        params["propriedade_id"] = str(prop.id)
        # A área é o ÚNICO dado que o produtor deu na conversa, e o handler
        # lê-a dos params. Sem ela, sai antes do código que este teste
        # quer exercitar — e o teste passa a medir a guarda da área em vez
        # dos defaults.
        params.setdefault("area_ha", "100")
        ctx = {"fontes": [], "passos": []}
        r = intents3.h_simular_cenario(user, params, ctx)
        return r

    def _utilizador(self):
        from django.contrib.auth.models import User

        nome = "teste-sim-lucro"
        u = User.objects.filter(username=nome).first()
        if u:
            return u
        return User.objects.create_user(username=nome, password="x")

    # ── o defeito ─────────────────────────────────────────────────────────

    def test_sem_preco_nao_simula(self):
        """O teste central. Antes, respondia com uma simulacao completa."""
        r = self._chama()
        self.assertFalse(r["ok"], "simulou sem nenhum dado do produtor")

    def test_diz_o_que_falta(self):
        r = self._chama()
        self.assertIn("produtividade", r["erro"].lower())
        self.assertIn("preco", r["erro"].lower().replace("ç", "c"))
        self.assertIn("custo", r["erro"].lower())

    def test_nao_inventa_o_ponto_de_equilibrio(self):
        """`Equilíbrio: 63.3 sc/ha` era um numero inventado, e o mais
        perigoso dos tres: e' um numero de decisao."""
        r = self._chama()
        texto = r.get("resposta", "") + r.get("erro", "")
        self.assertNotIn("Equilíbrio", texto)
        self.assertNotIn("Equil", texto)

    def test_a_resposta_nao_tem_nenhum_dos_defaults(self):
        r = self._chama()
        texto = r.get("resposta", "")
        for valor in ("60 sc/ha", "R$ 150", "380"):
            self.assertNotIn(valor, texto, f"o default {valor} sobreviveu")

    # ── o inverso: quando há dados, simula ─────────────────────────────────

    def test_com_todos_os_dados_simula(self):
        r = self._chama(produtividade="50", preco="120", custo_ha="300")
        self.assertTrue(r["ok"], r.get("erro"))
        self.assertIn("Simulação", r["resposta"])

    def test_aceita_o_alias_de_produtividade(self):
        r = self._chama(produtividade_sc_ha="50", preco="120", custo_ha="300")
        self.assertTrue(r["ok"], r.get("erro"))

    def test_aceita_o_alias_de_preco(self):
        r = self._chama(produtividade="50", preco_sc="120", custo_ha="300")
        self.assertTrue(r["ok"], r.get("erro"))

    def test_so_um_dado_em_falta_basta_para_nao_simular(self):
        r = self._chama(produtividade="50", preco="120")
        self.assertFalse(r["ok"])
        self.assertIn("custo", r["erro"].lower())

    # ── o `or` a mais: zero é um dado ─────────────────────────────────────

    def test_um_custo_zero_e_respeitado(self):
        """`or 380` transformava um zero que o produtor deu em 380.

        R$ 0/ha é uma informação real (lavoura propria, custo de
        opportunity zero). Tratar como "nao disse nada" e' o mesmo
        defeito, com o sinal trocado.
        """
        r = self._chama(produtividade="50", preco="120", custo_ha="0")
        self.assertTrue(r["ok"], f"rejeitou um custo de 0: {r.get('erro')}")
        self.assertEqual(r["dados"]["base"]["custo_ha"], 0.0)

    def test_uma_produtividade_zero_e_respeitada(self):
        r = self._chama(produtividade="0", preco="120", custo_ha="300")
        self.assertTrue(r["ok"], f"rejeitou produtividade 0: {r.get('erro')}")
        self.assertEqual(r["dados"]["base"]["produtividade_sc_ha"], 0.0)

    def test_um_preco_zero_e_respeitado(self):
        r = self._chama(produtividade="50", preco="0", custo_ha="300")
        self.assertTrue(r["ok"], f"rejeitou preco 0: {r.get('erro')}")
        self.assertEqual(r["dados"]["base"]["preco_sc"], 0.0)

    def test_cadeia_nao_faz_eco_no_num(self):
        """0 sc/ha a 120, custo 300 -> simula o que lhe foi dito.

        Com `or`, o 0 caia no default seguinte e o numero devolvido
        mentia sobre o que a pessoa escreveu.
        """
        r = self._chama(produtividade="0", preco="120", custo_ha="300")
        base = r["dados"]["base"]
        self.assertEqual(base["produtividade_sc_ha"], 0.0)
        self.assertEqual(base["preco_sc"], 120.0)
        self.assertEqual(base["custo_ha"], 300.0)


class TestONumDevolveAusenciaEZero(TestCase):
    """`_num` é a fronteira: onde `None` (ausência) se separa de 0 (dado)."""

    def test_ausencia_e_none(self):
        self.assertIsNone(intents3._num(None))
        self.assertIsNone(intents3._num(""))

    def test_zero_e_zero_e_nao_none(self):
        self.assertEqual(intents3._num("0"), 0.0)
        self.assertEqual(intents3._num(0), 0.0)

    def test_texto_sem_numero_e_none(self):
        self.assertIsNone(intents3._num("muito bom"))

    def test_formato_brasileiro(self):
        self.assertEqual(intents3._num("1.200,50"), 1200.5)
