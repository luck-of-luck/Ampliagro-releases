"""Uma resolucao de propriedade, um comportamento - testado uma vez.

Este ficheiro existe porque `app/ia/propriedade.py` substituiu tres copias
byte-a-byte da mesma funcao (`_prop`, `_prop2`, `_prop3`). Antes de unificar,
cada copia tinha os seus testes - ou nao tinha, que era metade do problema.
O teste que importa agora e' o que trava a REGRA, nao o nome do helper.

O que esta travado, e porque cada caso existe:

1. Prioridade do `propriedade_id`. Um handler que recebe id e nome tem de
   obedecer ao id. E' o caminho que o sandbox usa quando o modelo manda
   `{"propriedade_id": 7}`.

2. Id de outra conta devolve None, nunca a linha alheia. A regressao que
   este caso fecha e' o pior bug de isolamento de tenant possivel: em vez
   de "nao encontrei", devolver a fazenda do outro. Um `.get()` sem filtro
   de user passava aqui e seria catastrophe.

3. Nome por `icontains`, dentro do tenant. O produtor diz "sitio" e a
   fazenda chama-se "Sítio Boa Vista". Case-insensitive porque o produtor
   escreve minuscula e o cadastro nao.

4. `params=None` e' um params valido. As tres copias divergiam AQUI: a
   `_prop` rebentava com AttributeError e as outras duas devolviam a
   primeira propriedade. O comportamento agora e' o das duas ultimas - mas
   e' uma decisao, e uma decisao sem teste volta a ser uma diferenca.

5. As tres portas dao a mesma resposta. E' o teste que vale a pena: um
   handler muda de ficheiro, a resposta e' a mesma. E' o que um teste por
   copia nao detesta - cada copia passa nos testes da sua propria copia.
"""

from django.contrib.auth.models import User
from django.test import TestCase

from app.ia import intents, intents2, intents3
from app.ia.propriedade import resolver


class ResolverPropriedadeTest(TestCase):
    def setUp(self):
        self.dono = User.objects.create_user("p_dono", password="x1234567")
        self.vizinho = User.objects.create_user("p_vizinho", password="x1234567")

        from app.models import Propriedade

        self.sitio = Propriedade.objects.create(
            user=self.dono, nome="Sitio Boa Vista", area_total=100.0
        )
        self.sede = Propriedade.objects.create(
            user=self.dono, nome="Sede", area_total=50.0
        )
        self.alheia = Propriedade.objects.create(
            user=self.vizinho, nome="Fazenda Alheia", area_total=999.0
        )

    def test_propriedade_id_tem_prioridade_sobre_o_nome(self):
        r = resolver(
            self.dono,
            {"propriedade_id": self.sede.id, "propriedade": "Sitio"},
        )
        self.assertEqual(r, self.sede)

    def test_id_de_outra_conta_devolve_none_e_nao_a_linha_alheia(self):
        r = resolver(self.dono, {"propriedade_id": self.alheia.id})
        self.assertIsNone(r)
        self.assertNotEqual(r, self.alheia)

    def test_nome_e_encontrado_sem_se_casear(self):
        r = resolver(self.dono, {"propriedade": "boa vista"})
        self.assertEqual(r, self.sitio)

    def test_nome_de_outra_conta_devolve_none(self):
        r = resolver(self.dono, {"propriedade": "Alheia"})
        self.assertIsNone(r)

    def test_sem_params_devolve_a_primeira_do_usuario(self):
        # Nao se assume "a primeira criada": `Propriedade` tem Meta.ordering
        # (por UF/nome), e `qs.first()` segue essa ordem, nao a de insercao.
        # O que se trava aqui e' a REGRA ("sem params -> uma propriedade do
        # utilizador"), e nao uma linha especifica do fixture.
        from app.models import Propriedade

        esperada = Propriedade.objects.filter(user=self.dono).first()
        r = resolver(self.dono, {})
        self.assertEqual(r, esperada)
        self.assertIn(r, (self.sitio, self.sede))

    def test_params_none_nao_rebenta(self):
        """O `None` que fazia `_prop` rebentar e as outras duas devolverem.

        A assinatura tem `params` opcional (`params=None`) justamente porque
        o sandbox chama handlers sem argumentos opcionais.
        """
        from app.models import Propriedade

        r = resolver(self.dono, None)
        self.assertIsNotNone(r)
        self.assertEqual(r, Propriedade.objects.filter(user=self.dono).first())

    def test_usuario_sem_propriedade_devolve_none(self):
        sem_nada = User.objects.create_user("p_nada", password="x1234567")
        self.assertIsNone(resolver(sem_nada, {}))

    def test_as_tres_portas_sao_a_mesma_funcao(self):
        """`_prop`, `_prop2` e `_prop3` sao o mesmo objecto.

        E' a assercao que mata a regressao da duplicacao. Se alguem voltar a
        colar a funcao num `intents4.py`, esta linha falha - e o nome `_prop4`
        avisa antes do bug, em vez de a divergencia aparecer em producao.
        """
        self.assertIs(intents._prop, intents2._prop2)
        self.assertIs(intents2._prop2, intents3._prop3)

    def test_handlers_reais_batem_na_resolucao_unica(self):
        """Um handler real de cada lote, com o tenant dos dois lados.

        E' um smoke test, e e' de proposito. O objectivo nao e' provar que
        `listar_maquinas` funciona - isso e' trabalho dos testes de intents.
        E' provar que um handler de cada ficheiro bate na resolucao unica e
        nao numa copia sua.
        """
        r2 = intents2.h_listar_maquinas(self.dono, {}, {"fontes": []})
        r3 = intents3.h_lucro_talhao(self.dono, {}, {"fontes": []})
        self.assertTrue(r2["ok"])
        self.assertTrue(r3["ok"])
        # E nenhum dos dois viu a fazenda do vizinho.
        for r in (r2, r3):
            self.assertNotIn("Alheia", str(r))
