"""Uma pessoa pode ter mais de tres fazendas. E so as que lhe pertencem.

POR QUE ESTE FICHEIRO EXISTE
===========================
MEDIDO 2026-10-05 (agente 7). O Ampliagro nao tinha multi-utilizador por
propriedade. O esquema era de **propriedade**: `Propriedade.user` e' um
`ForeignKey`, e `user.propriedades` sao as fazendas *dele*. Nao havia lugar
para mais ninguem.

O tecto era literal e estava escrito em codigo — `app/hierarquia.py:207`:

    qs = Propriedade.objects.filter(user=user)
    if perfil.propriedade_vinculada_id:      # no max. UMA
        vinc.append(...)
    if perfil.funcionario.propriedade_id:    # no max. UMA
        vinc.append(...)
    # 1 + 1 + 1 = 3. Sem excecao, sem caminho para a quarta.

Tres e' pequeno o suficiente para passar despercebido num teste e grande o
suficiente para fechar o produto. Um agronomo com 12 clientes, um contador
que serve 40 fazendas, uma familia com 4 — todos batem num tecto de 3.

E e' o modo como os concorrentes crescem: o Aegro vende "gerencie multiplos
clientes com eficiencia"; a Lucro Rural vende "produtor **e** contador" como
dois papeis na mesma propriedade. `docs/sistema/7.md` §11 P1-2.

O QUE ESTE FICHEIRO TRAVA
=========================
1. Dez fazendas, um utilizador, sem tecto.
2. Membro ve **so** as suas, nunca as do dono — a nivel do dado, nao do
   queryset, porque "so desfazer a duvida a nivel do dado" e' a unica forma
   de provar que um filtro de acesso nao vaza.
3. `ativo=False` retira o acesso (revogacao sem apagar historico).
4. Os caminhos antigos (vinculo de servidor, funcionario) continuam a
   funcionar: a mudanca e' **aditiva** e nao pode quebrar quem ja tinha
   acesso.
5. Um `User` novo, sem membro nenhum, nao ve nada de ninguem.

O QUE ESTE FICHEIRO NAO FAZ, E DE PROPOSITO
=============================================
Nao trata `PerfilUsuario` ausente como o caminho de acesso. Um `User` sem
perfil e' um estado que o sistema **impede** por construcao — o sinal
`garantir_perfil_usuario` (`app/signals.py`) cria o perfil a cada conta nova.
Um teste que constroi "um user sem perfil" teria de desligar o sinal para
passar, e um teste que precisa de desligar o sinal para passar esta a testar
o sinal ao contrario. Este ficheiro testa o caso que existe: conta nova,
perfil criado pelo sinal, **nenhum membro** — e a resposta tem de ser zero.
"""

from django.contrib.auth.models import User
from django.test import TestCase

from app import hierarquia
from app.models import MembroPropriedade, Propriedade

#: Import por modulo, e nao `from ... import nome`. Chamar
#: `hierarquia.propriedades_visiveis(...)` torna a origem do acesso visivel na
#: linha da chamada: se a porta mudar de sitio, o teste quebra em vez de
#: continuar a usar um nome antigo que ja nao e' o mesmo.
visiveis_de = hierarquia.propriedades_visiveis


def _ids(user):
    return set(visiveis_de(user).values_list("id", flat=True))


def _perfil(user):
    """Devolve o `PerfilUsuario`, criando-o se o sinal ainda nao o criou."""
    from app.models import PerfilUsuario

    perfil, _ = PerfilUsuario.objects.get_or_create(user=user)
    return perfil


class TectoDeTresTest(TestCase):
    """O numero que fez este ficheiro."""

    def setUp(self):
        self.consultor = User.objects.create_user("agr12", password="x1234567")
        _perfil(self.consultor)

        # Doze fazendas de doze produtores diferentes — um agroconsultor a
        # serio. Antes disto `propriedades_visiveis` devolvia 3.
        self.clientes = []
        for i in range(12):
            dono = User.objects.create_user(f"cli{i}", password="x1234567")
            self.clientes.append(
                Propriedade.objects.create(
                    user=dono, nome=f"Fazenda Cliente {i:02d}", area_total=100
                )
            )

    def test_dez_fazendas_nao_batem_em_tecto_de_tres(self):
        for prop in self.clientes:
            MembroPropriedade.objects.create(
                propriedade=prop, user=self.consultor, papel="CONSULTOR"
            )

        self.assertEqual(
            visiveis_de(self.consultor).count(),
            12,
            "um consultor com 12 clientes so ve parte deles. E' o tecto de 3 "
            "da §11 P1-2, e e' o motivo de o modelo existir.",
        )

    def test_o_membro_tem_de_ser_ativo_para_contar(self):
        """`ativo=False` nao e' podar: e' revogar.

        Apagar a linha perde a data de convite e o papel que a pessoa tinha.
        Um produtor que saiu e' melhor `ativo=False`: a saida fica escrita.
        """
        membro = MembroPropriedade.objects.create(
            propriedade=self.clientes[0], user=self.consultor, papel="CONSULTOR"
        )
        self.assertIn(self.clientes[0].id, _ids(self.consultor))

        membro.ativo = False
        membro.save()

        self.assertNotIn(self.clientes[0].id, _ids(self.consultor))


class MembroNaoEHerdeiroTest(TestCase):
    """Ser membro de uma fazenda nao da acesso as outras do mesmo dono.

    Este e' o teste que impede que a feature nova vire uma fuga. Um modelo de
    acesso onde o acesso se propaga por "o dono" seria o mesmo erro do
    `talhao_id` do Caderno: acesso que nao foi pedido.
    """

    def setUp(self):
        self.dono = User.objects.create_user("dono", password="x1234567")
        _perfil(self.dono)
        self.gerente = User.objects.create_user("gerente", password="x1234567")
        _perfil(self.gerente)

        self.a = Propriedade.objects.create(
            user=self.dono, nome="Fazenda A", area_total=100
        )
        self.b = Propriedade.objects.create(
            user=self.dono, nome="Fazenda B", area_total=100
        )

        # O gerente entra so na A. E' o que um administrador de fazenda faz.
        MembroPropriedade.objects.create(
            propriedade=self.a, user=self.gerente, papel="ADMIN"
        )

    def test_membro_da_A_nao_ve_a_B(self):
        ids = _ids(self.gerente)
        self.assertIn(self.a.id, ids)
        self.assertNotIn(
            self.b.id,
            ids,
            "o gerente da Fazenda A viu a Fazenda B. O acesso tem de vir da "
            "linha de membro, nunca do facto de o dono ser o mesmo.",
        )

    def test_o_dono_continua_a_ver_as_suas_duas(self):
        ids = _ids(self.dono)
        self.assertIn(self.a.id, ids)
        self.assertIn(self.b.id, ids)

    def test_a_isolamento_agrega_ao_nivel_do_lancamento(self):
        """A prova vai ate ao dado.

         Um filtro de acesso pode estar certo no queryset e ser furado a jus
        ante, se alguma view confiar so em `propriedade_id` do request. Por isso
         o teste cria lancamentos nas duas fazendas e le os que o membro
         alcança.
        """
        from app.models import LancamentoFinanceiro

        for prop, valor in ((self.a, 100), (self.b, 999)):
            LancamentoFinanceiro.objects.create(
                propriedade=prop,
                data="2026-03-01",
                categoria="Custo",
                tipo="DESPESA",
                valor=valor,
                descricao="Teste",
                pago=True,
            )

        props = visiveis_de(self.gerente)
        valores = set(
            LancamentoFinanceiro.objects.filter(propriedade__in=props).values_list(
                "valor", flat=True
            )
        )

        self.assertIn(100, valores)
        self.assertNotIn(
            999,
            valores,
            "o membro da Fazenda A leu o lancamento de 999 da Fazenda B.",
        )


class CaminhosAntigosNaoQuebraramTest(TestCase):
    """A mudanca e' aditiva. Quem tinha acesso antes, continua a ter."""

    def setUp(self):
        self.user = User.objects.create_user("servidor", password="x1234567")
        self.outro = User.objects.create_user("outro", password="x1234567")

        self.propria = Propriedade.objects.create(
            user=self.user, nome="A Minha", area_total=100
        )
        self.do_servidor = Propriedade.objects.create(
            user=self.outro, nome="A Do Servidor", area_total=100
        )

    def test_o_vinculo_do_servidor_ainda_da_acesso(self):
        """`perfil.propriedade_vinculada_id` — o caminho legado.

        Nao foi removido de proposito: e' usado por sinais e por `pode_acessar`.
        Removê-lo seria um atalho curto que quebraria quem tem acesso por ele.
        """
        perfil = _perfil(self.user)
        perfil.propriedade_vinculada = self.do_servidor
        perfil.save()

        ids = _ids(self.user)

        self.assertIn(self.propria.id, ids)
        self.assertIn(
            self.do_servidor.id,
            ids,
            "o vinculo legado do servidor deixou de funcionar. A fonte nova "
            "soma-se a antiga; nao a substitui.",
        )

    def test_conta_nova_sem_membro_nao_ve_nada(self):
        """Uma conta recem-criada nao ve fazendas de ninguem.

        O sinal `garantir_perfil_usuario` garante que a conta nova tem perfil,
        por isso "sem perfil" nao e' um estado que este sistema tenha. O caso
        que existe — perfil criado, **nenhum membro** — tem de devolver zero.
        """
        recem = User.objects.create_user("recem", password="x1234567")
        ids = _ids(recem)

        self.assertEqual(
            ids,
            set(),
            "uma conta nova, sem membro em nenhuma propriedade, devolveu fazendas.",
        )
