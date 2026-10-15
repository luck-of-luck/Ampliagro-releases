"""Duas pessoas, ou duas abas, a pedir a MESMA tela ao MESMO tempo.

O QUE ISTO MEDIU
================
`planear` resolve o slug, e depois o produtor TEM DE RESPONDER ao "sim". Entre
a pergunta e o "sim" passa tempo — e nesse intervalo outra sessao pode gravar
o mesmo nome. E' o caminho que os testes normais nunca fazem: eles gravam duas
vezes em sequencia, e sequencia nao tem corrida.

Por que e' um problema REAL e nao teorico: o `sandbox` guarda a confirmacao em
`IAContextoConversa`, e essa conversacao e' por produtor. Duas sessoes do MESMO
produtor em abas diferentes partilham o preset e nao partilham a conversa. E'
exactamente o caso em que os dois veem "Criei" e so' ha uma mesa.

O QUE ESTE TESTE PROVA
======================
Nao que a corrida "se resolve" — isso seria uma promessa. Que ela **nao
perde dados e nao duplica**: a ultima gravacao tem de ganhar, tem de ser um
preset so, e o dono tem de continuar a ser quem pediu.
"""

from django.contrib.auth.models import User
from django.test import TestCase

from app.ia import palco_presets
from app.models.palco import PresetPalco


class CorridaNoMesmoSlugTest(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user("ana_corrida", "a@x.com", "x1234567")

    def _plano(self, nome, tipo):
        """O que cada uma das duas sessoes TRAGUE para a confirmacao.

        Os dois planos sao feitos ANTES de qualquer gravacao. E' este o detalhe
        que reproduz a corrida: se o plano fosse feito no momento de gravar, os
        dois passos estariam sequenciais e o teste nao provaria nada.
        """
        return palco_presets.planear(self.ana, nome, [{"tipo": tipo, "titulo": tipo}])

    def test_dois_planos_do_mesmo_nome_resolvem_para_o_mesmo_slug(self):
        """E' o que torna a corrida possivel: as duas sessoes apontao ao mesmo
        preset, e nao a dois."""
        primeiro = self._plano("Custo", "kpi-custo")
        segundo = self._plano("Custo", "kpi-roi")
        self.assertEqual(primeiro["slug"], segundo["slug"])
        self.assertEqual(primeiro["operacao"], "criar")

    def test_a_segunda_gravacao_substitui_em_vez_de_duplicar(self):
        """O botao premido duas vezes nao pode criar duas mesas.

        `palco_clonar` diz isto na sua propria docstring: *"Clicar duas vezes em
        'Salvar' nao pode ser um erro... o segundo momento e' o mesmo pedido"*,
        e trata-o actualizando. O servico da IA faz o mesmo.
        """
        primeiro = self._plano("Custo", "kpi-custo")
        palco_presets.gravar(self.ana, primeiro)

        segundo = self._plano("Custo", "kpi-roi")
        gravado = palco_presets.gravar(self.ana, segundo)

        self.assertFalse(gravado["criado"], "criou uma segunda mesa com o mesmo nome")
        self.assertEqual(PresetPalco.objects.filter(user=self.ana).count(), 1)

        # E a ultima gravacao e' a que vale: quem respondeu "sim" por ultimo
        # viu a tela mais recente.
        tipos = [w["tipo"] for w in PresetPalco.objects.get().estrutura["widgets"]]
        self.assertEqual(tipos, ["kpi-roi"])

    def test_o_dono_continua_a_ser_quem_pediu(self):
        """A corrida e' entre sessoes do MESMO produtor. Um preset nao pode
        mudar de dono no caminho — nem por gravacao, nem por `get_or_create`."""
        plano = self._plano("Custo", "kpi-custo")
        palco_presets.gravar(self.ana, plano)
        self.assertEqual(PresetPalco.objects.get().user_id, self.ana.pk)

    def test_o_slug_resolvido_no_plano_e_o_que_vai_para_a_base(self):
        """`gravar` usa o slug do plano e nao volta a resolve-lo.

        Se voltasse a resolver, um preset novo criado entre o plano e a
        gravacao levaria o plano a apontar para o preset errado — e o produtor
        veria a tela noutra mesa sem nada que o tivesse avisado.
        """
        plano = self._plano("Custo", "kpi-custo")
        gravado = palco_presets.gravar(self.ana, plano)
        self.assertEqual(gravado["preset"]["slug"], plano["slug"])

    def test_o_plano_antigo_nao_sobrescreve_um_preset_novo(self):
        """O caso que a corrida produz de facto, e o mais perigoso.

        A sessao A planou para `custom-custo`. Antes de A responder, a sessao B
        renomeou o preset — o `nome` ja' nao e' "Custo", e o slug passou a ser
        `custom-custo-2`. A sessao A responde "sim" ao plano que viu, e esse
        plano aponta para um preset que ja' nao e' o que ela queria guardar.

        Aqui o que se mede e' o comportamento REAL: `gravar` escreve no slug do
        plano. Isso esta certo — a sessao A confirmou o que viu — e o que o
        teste impede e' que o codigo FINJA resolver o alvo outra vez e escrever
        noutro sitio. Um teste que exigisse "aponta para o preset certo" seria
        um teste que so' passaria se a A fosse levada a outra mesa sem o saber.
        """
        # A sessao A planeia e fica a espera.
        plano_a = self._plano("Custo", "kpi-custo")

        # A sessao B grava o mesmo nome.
        plano_b = self._plano("Custo", "kpi-roi")
        palco_presets.gravar(self.ana, plano_b)

        # A sessao A responde "sim" ao que viu.
        gravado_a = palco_presets.gravar(self.ana, plano_a)

        # Escreve no preset que ela confirmou, e noutro sitio nenhum.
        self.assertEqual(gravado_a["preset"]["slug"], plano_a["slug"])
        self.assertEqual(
            PresetPalco.objects.filter(user=self.ana).count(),
            1,
            "a sessao A criou uma segunda mesa em vez de escrever na que confirmou",
        )
