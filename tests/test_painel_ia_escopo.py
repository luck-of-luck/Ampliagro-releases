"""O painel da IA tem de mostrar a mesma fazenda que o resto do sistema.

O DEFEITO
=========
`app/ia/palco_dados.py` e `app/ia/paginas.py` filtravam o escopo por
``Propriedade.objects.filter(user=user)`` — e o cabeçalho do primeiro
afirmava, com todas as letras, ser "tenancy-safe".

`user` é o DONO. Um servidor e um funcionário não são donos: são ACESSORES.
A propriedade deles entra por ``PerfilUsuario.propriedade_vinculada`` ou por
``Funcionario.propriedade``, e nenhuma das duas caminhos passa por
``Propriedade.user``.

Verificado no ambiente real com ``mecanico.demo``, perfil de servidor
(MECANICA), ligado à Fazenda Modelo (id 14):

    propriedades_visiveis(servidor)  -> [(14, 'Fazenda Modelo')]   ✅
    o_que_existe(servidor)           -> tudo False               ❌
    kpi-caixa(servidor)              -> sem_dado                 ❌

O técnico via a fazenda no resto do produto — e via um painel vazio no
painel da IA, sem uma palavra de aviso. Pior: "sem_dado" é a MESMA coisa que
o painel mostra quando não há lançamentos. São duas mentiras com a mesma
cara, e a segunda (o painel está vazio) levava o servidor a culpar a app em
vez de a ligar à fazenda que lhe estava à vista no menu.

O QUE ESTE TESTE TRAVA
======================
1. O servidor vê a propriedade a que foi ligado, e o painel dele tem dados.
2. A fonte do número diz DE QUEM é a propriedade — um servidor sem nome na
   fonte fica com um número que ninguém pode conferir.
3. O produtor não regrediu: a correção não pode ter trocado um bug por outro.
4. O isolamento NÃO é afrouxado: ver a propriedade ligada não pode dar
   acesso a propriedades de outros produtores.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from app.hierarquia import propriedades_visiveis
from app.ia.paginas import o_que_existe
from app.ia.palco import validar_estrutura
from app.ia.palco_dados import _propriedades_do_usuario, _unica_propriedade, enriquece
from app.models import (
    Cultura,
    Funcionario,
    LancamentoFinanceiro,
    PerfilUsuario,
    Propriedade,
    Safra,
)

User = get_user_model()


class PainelIaRespeitaOEscopoDaHierarquia(TestCase):
    def _perfil(self, user, **campos):
        """Perfil com OS valores deste teste, e o utilizador RECARREGADO.

        Duas coisas, e as duas são o que o sistema real faz:

        1. `get_or_create` sozinho não chega. O sinal `garantir_perfil_usuario`
           cria o perfil no `post_save` do `User`, e o `get_or_create`
           encontra um perfil JÁ EXISTE e devolve-o sem aplicar os `defaults`
           — que é um perfil de produtor.
        2. O utilizador tem de voltar do banco. `user.perfil` é um
           descriptors com cache, e o perfil em memória fica com
           `propriedade_vinculada_id = None` para sempre depois de um
           `get_or_create` que não a preencheu. É o que `app/tests_servidor.py`
           já documenta: "sem recarregar, `propriedades_visiveis` leria…".
        """
        perfil, _ = PerfilUsuario.objects.get_or_create(user=user)
        for campo, valor in campos.items():
            setattr(perfil, campo, valor)
        perfil.save()
        return User.objects.get(pk=user.pk)

    def setUp(self):
        self.produtor = User.objects.create_user("prod_t", "prod_t@t.com", "x")
        self.prop = Propriedade.objects.create(
            user=self.produtor,
            nome="Fazenda do Produtor",
            cidade="Muzambinho",
            uf="MG",
            area_total=Decimal("1200.00"),
        )
        self.cultura = Cultura.objects.create(nome="Soja")
        Safra.objects.create(
            propriedade=self.prop,
            cultura=self.cultura,
            ano=2026,
            area_plantada=Decimal("210.00"),
            area_colhida=Decimal("205.00"),
            producao_total=Decimal("62000.00"),
        )
        LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            data=date(2026, 3, 10),
            tipo="RECEITA",
            valor=Decimal("185000.00"),
        )
        LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            data=date(2026, 4, 10),
            tipo="DESPESA",
            valor=Decimal("42000.00"),
        )

        # O servidor: TEM perfil, TEM área, e está LIGADO a esta propriedade.
        #
        # `get_or_create` e não `create`: o sinal `garantir_perfil_usuario`
        # já cria um perfil no `post_save` de cada `User`, e um `create`
        # directo dá `UNIQUE constraint failed`. Isto não é um contorno —
        # é o que o resto do sistema faz, e um teste que fought o sinal
        # estaria a testar um mundo que não existe.
        self.servidor = self._perfil(
            User.objects.create_user("srv_t", "srv_t@t.com", "x"),
            tipo_usuario="servidor",
            area_servidor="MECANICA",
            propriedade_vinculada=self.prop,
        )

        # A propriedade de OUTRO produtor, que ninguém neste teste pode ver.
        self.outro = User.objects.create_user("outro_t", "outro_t@t.com", "x")
        self.prop_alheia = Propriedade.objects.create(
            user=self.outro,
            nome="Fazenda Alheia",
            cidade="Campinas",
            uf="SP",
            area_total=Decimal("50.00"),
        )
        LancamentoFinanceiro.objects.create(
            propriedade=self.prop_alheia,
            data=date(2026, 3, 10),
            tipo="RECEITA",
            valor=Decimal("999999.00"),
        )

    def _kpi(self, user, tipo):
        ws = validar_estrutura([{"tipo": tipo}])[0]
        out = enriquece(user, [dict(w) for w in ws])
        return out[0].get("config") or {}

    # ───────────────────────────────────────────────────────────────────
    # 1. O servidor vê a fazenda a que foi ligado
    # ───────────────────────────────────────────────────────────────────
    def test_a_hierarquia_ve_a_propriedade_e_o_painel_ia_agora_tambem(self):
        """O defeito exato, verificado nas duas pontas.

        Este teste é a razão de existir: ele afirma o que a hierarquia já
        fazia E o que o painel da IA não fazia. Se alguém voltar a
        `filter(user=user)`, a primeira asserção continua verde e a segunda
        fica vermelha — que é exactamente o que se quer.
        """
        visiveis = list(
            propriedades_visiveis(self.servidor).values_list("id", flat=True)
        )
        self.assertIn(
            self.prop.id,
            visiveis,
            "a hierarquia deixou de considerar a propriedade vinculada. "
            "Se isto falha, o problema é de ligação, não do painel.",
        )

        inv = o_que_existe(self.servidor)
        self.assertTrue(
            inv["propriedade"], "o inventário do painel disse que não há propriedade"
        )
        self.assertTrue(inv["safra"], "o painel disse que não há safras — e há")
        self.assertTrue(
            inv["lancamento"], "o painel disse que não há lançamentos — e há"
        )

    def test_o_servidor_ve_os_numeros_da_fazenda_que_lhe_esta_vinculada(self):
        """O cartão do servidor deixou de dizer "sem dado" indevidamente.

        R$ 185.000 de receita e R$ 42.000 de despesa estão no banco e são da
        fazenda que o perfil diz poder ver. Devolver `sem_dado` aqui não era
        prudência: era a mesma resposta para "não há dados" e "não tens
        acesso", e o produtor não tem como distinguir.
        """
        cfg = self._kpi(self.servidor, "kpi-caixa")

        self.assertEqual(cfg["fonte_dado"], "medido")
        self.assertEqual(cfg["entradas"], 185000.0)
        self.assertEqual(cfg["saidas"], 42000.0)
        self.assertEqual(cfg["saldo"], 143000.0)

    def test_a_fonte_do_numero_diz_de_quem_e_a_propriedade(self):
        """Um número sem nome de fazenda não é auditável.

        A fonte tem de responder a "isto foi lido de onde?" dentro de seis
        meses. Para o produtor é `LancamentoFinanceiro`; para o servidor, que
        não é dono, o nome da fazenda é a única coisa que distingue este
        saldo do saldo de outra pessoa.
        """
        cfg = self._kpi(self.servidor, "kpi-caixa")
        fonte = str(cfg.get("fonte") or "")

        self.assertIn("LancamentoFinanceiro", fonte)
        self.assertIn(
            self.prop.nome,
            fonte,
            "a fonte do número não diz de que fazenda é. Sem isso, um "
            "servidor com cinco fazendas não sabe qual está a ler.",
        )

    def test_a_funcao_de_escopo_e_a_mesma_da_hierarquia(self):
        """Uma fonte de verdade, não uma segunda que diverge em silêncio.

        Duas funções a responder "o que esta pessoa vê" é o que produz a
        falha que corrigimos: a hierarquia ganhou um caminho, o painel ficou
        para trás, e a diferença só apareceu com um servidor real.
        """
        painel = set(
            _propriedades_do_usuario(self.servidor).values_list("id", flat=True)
        )
        hierarquia = set(
            propriedades_visiveis(self.servidor).values_list("id", flat=True)
        )

        self.assertEqual(
            painel,
            hierarquia,
            "o escopo do painel da IA deixou de bater com o da hierarquia. "
            "Um dos dois está desatualizado.",
        )

    # ───────────────────────────────────────────────────────────────────
    # 2. O produtor não regrediu
    # ───────────────────────────────────────────────────────────────────
    def test_o_produtor_continua_a_ver_a_sua_fazenda(self):
        """A correção não pode ter trocado o bug do servidor por um do produtor.

        `propriedades_visiveis` devolve as próprias mais as vinculadas, e as
        próprias entram no primeiro ramo. Este teste trava essa ordem: se um
        dia o filtro passar a exigir perfil, o produtor sem perfil passa a
        ver um painel vazio — e o sinal seria o mesmo do bug anterior.
        """
        inv = o_que_existe(self.produtor)
        self.assertTrue(inv["propriedade"])
        self.assertTrue(inv["safra"])
        self.assertEqual(inv["propriedades"], [self.prop.nome])

        cfg = self._kpi(self.produtor, "kpi-caixa")
        self.assertEqual(cfg["fonte_dado"], "medido")
        self.assertEqual(cfg["saldo"], 143000.0)
        self.assertEqual(
            _unica_propriedade(self.produtor),
            self.prop,
            "a fonte do número do produtor perdeu o nome da fazenda dele.",
        )

    # ───────────────────────────────────────────────────────────────────
    # 3. O isolamento não afrouxa
    # ───────────────────────────────────────────────────────────────────
    def test_ver_a_propriedade_ligada_nao_da_acesso_a_de_outros(self):
        """A correção alarga o ESCOPO, não a PERMISSÃO.

        Este é o teste de segurança do ficheiro. Se `propriedades_visiveis`
        deixar de filtrar o `user` de base, qualquer servidor passa a ver
        todas as fazendas — e a correção do bug 1 vira a porta dos fundos.
        """
        visiveis = list(
            _propriedades_do_usuario(self.servidor).values_list("id", flat=True)
        )

        self.assertIn(self.prop.id, visiveis)
        self.assertNotIn(
            self.prop_alheia.id,
            visiveis,
            "o servidor passou a ver a propriedade de outro produtor.",
        )

    def test_o_nome_da_propriedade_alheia_nao_aparece_em_lado_nenhum(self):
        """Nem nos números, nem na fonte, nem no inventário.

        Um teste de escopo que só olha para o `.values_list("id")` pode
        deixar passar um nome numa string de provenance. Aqui olha-se para
        a resposta inteira.
        """
        for tipo in ("kpi-caixa", "kpi-custo", "kpi-roi", "table-financeiro"):
            cfg = self._kpi(self.servidor, tipo)
            serializado = str(cfg)
            self.assertNotIn(
                self.prop_alheia.nome,
                serializado,
                f"{tipo} passou a expor a propriedade de outro produtor.",
            )
            self.assertNotIn(
                "999999", serializado, f"{tipo} passou a somar dinheiro alheio"
            )

    def test_o_inventario_nao_fala_da_fazenda_alheia(self):
        inv = o_que_existe(self.servidor)
        self.assertNotIn(self.prop_alheia.nome, inv["propriedades"])

    # ───────────────────────────────────────────────────────────────────
    # 4. A outra forma de ligar: pelo FUNCIONÁRIO
    # ───────────────────────────────────────────────────────────────────
    def test_a_propriedade_via_funcionario_tambem_conta(self):
        """Há dois caminhos de ligação, e os dois têm de funcionar.

        Um técnico é muitas vezes ligado por `Funcionario.propriedade` e não
        por `propriedade_vinculada`. Corrigir só o segundo deixa metade dos
        casos de fora — e a falha volta a ser silenciosa.
        """
        func = User.objects.create_user("func_t", "func_t@t.com", "x")
        funcionario = Funcionario.objects.create(
            propriedade=self.prop,
            nome="Carlos",
            cargo="MECANICO",
            salario=Decimal("3800.00"),
            data_admissao=date(2024, 1, 15),
            ativo=True,
        )
        func = self._perfil(
            User.objects.create_user("via_func_t", "via_func_t@t.com", "x"),
            tipo_usuario="servidor",
            area_servidor="MECANICA",
            funcionario=funcionario,
        )
        self.assertIn(
            self.prop.id, _propriedades_do_usuario(func).values_list("id", flat=True)
        )
        self.assertEqual(self._kpi(func, "kpi-caixa")["fonte_dado"], "medido")
