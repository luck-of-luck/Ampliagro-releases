"""As perguntas da IA, filtradas pelas culturas que o produtor escolheu.

O QUE ESTE FICHEIRO PROVA
-------------------------
`catalogo_de_capacidades` é o que um agente externo lê em
`amplia://capacidades` antes de sugerir uma acção. Sem filtro, ele via
"Configura a regra que liga o aerador quando o mormaco da tilapia passar de
30 °C" a um produtor que só planta soja — e o agente, que é feito para
obedecer ao que lhe é oferecido, sugere o aerador.

Isto nao e uma preferencia de interface. E' o catalogo, que alimenta a
escolha. Um widget escondido só num sítio e a pergunta noutro faz o produto
dizer duas coisas diferentes sobre a mesma fazenda.

O QUE NÃO ESTÁ AQUI, E PORQUÊ
-----------------------------
`automatizar_sap` (integração SAP/JBS) NÃO foi marcada. A descrição diz
"integracao SAP ERP (JBS, 10M cabecas)" e a JBS é de suínos — mas isso é
saber de fora do código, e a marca precisa de ser dedutível da ficha. Fica
para revisão; enquanto isso aparece a toda a gente, que é a falha ABERTA de
que fala `grupos_da_marca`.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from app.models import Cultura, Propriedade


class FiltroDeCapacidades(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ia", password="x")
        self.prop = Propriedade.objects.create(
            user=self.user, nome="Faz", area_total=100, uf="MT"
        )
        self.soja = Cultura.objects.create(nome="Soja", grupo="graos", ativo=True)
        self.tilapia = Cultura.objects.create(
            nome="Tilápia", grupo="peixes", ativo=True
        )
        self.frango = Cultura.objects.create(nome="Frango", grupo="aves", ativo=True)
        self.vaca = Cultura.objects.create(
            nome="Vaca Leiteira", grupo="leite", ativo=True
        )

    def _respondeu(self, *culturas):
        self.prop.culturas.set(culturas)
        self.prop.culturas_escolhidas_em = timezone.now()
        self.prop.save(update_fields=["culturas_escolhidas_em"])

    def _nomes(self, **kw):
        from app.amplia_mcp.capacidades import catalogo_de_capacidades

        kw.setdefault("user", self.user)
        return {c["capacidade"] for c in catalogo_de_capacidades(**kw)["capacidades"]}

    # ── quem nunca escolheu ──

    def test_conta_antiga_ve_tudo(self):
        """A conta legada não perde capacidades. É a regra dos três estados,
        a mesma das guias — e a mesma razão."""
        de_tudo = self._nomes(filtrar_culturas=False)
        self.assertEqual(self._nomes(), de_tudo)
        self.assertIn("automatizar_aerador", self._nomes())

    # ── vegetal ──

    def test_soja_nao_ve_aerador_nem_debicagem(self):
        self._respondeu(self.soja)
        nomes = self._nomes()
        self.assertNotIn("automatizar_aerador", nomes)  # tilápia
        self.assertNotIn("automatizar_moba", nomes)  # bico do frango
        self.assertNotIn("automatizar_bigbrother", nomes)
        self.assertNotIn("resumo_aquatico", nomes)
        self.assertNotIn("producao_leite", nomes)
        self.assertNotIn("automatizar_piquete", nomes)

    def test_soja_ve_o_que_e_de_lavoura(self):
        self._respondeu(self.soja)
        nomes = self._nomes()
        self.assertIn("automatizar_hedge", nomes)  # soja V0-R8
        self.assertIn("cadastrar_funcionario", nomes)  # de fazenda
        self.assertIn("recomendacao_adubacao", nomes)

    # ── aquicultura ──

    def test_tilapia_ve_aerador_e_resumo(self):
        self._respondeu(self.tilapia)
        nomes = self._nomes()
        self.assertIn("automatizar_aerador", nomes)
        self.assertIn("resumo_aquatico", nomes)
        # Aquicultura não é gado: debicagem é bico, não tilápia.
        self.assertNotIn("automatizar_moba", nomes)
        self.assertNotIn("producao_leite", nomes)
        # E não é lavoura.
        self.assertNotIn("automatizar_hedge", nomes)

    # ── avicultura ──

    def test_frango_ve_debicagem_e_balanca(self):
        self._respondeu(self.frango)
        nomes = self._nomes()
        self.assertIn("automatizar_moba", nomes)
        self.assertIn("automatizar_bigbrother", nomes)
        self.assertNotIn("automatizar_aerador", nomes)
        self.assertNotIn("automatizar_hedge", nomes)

    # ── pecuária ──

    def test_vaca_ve_leite_e_piquete(self):
        self._respondeu(self.vaca)
        nomes = self._nomes()
        self.assertIn("producao_leite", nomes)
        self.assertIn("automatizar_piquete", nomes)
        # Pecuária NÃO é avicultura: "ajustar o bico" não é dela.
        self.assertNotIn("automatizar_moba", nomes)
        self.assertNotIn("automatizar_bigbrother", nomes)

    # ── misto ──

    def test_misto_ve_as_duas(self):
        self._respondeu(self.soja, self.tilapia)
        nomes = self._nomes()
        self.assertIn("automatizar_hedge", nomes)
        self.assertIn("automatizar_aerador", nomes)
        self.assertNotIn("automatizar_moba", nomes)

    # ── respondeu "nenhuma" ──

    def test_escolheu_nenhuma_fica_so_com_o_de_fazenda(self):
        self.prop.culturas_escolhidas_em = timezone.now()
        self.prop.save(update_fields=["culturas_escolhidas_em"])
        nomes = self._nomes()
        for especifica in (
            "automatizar_aerador",
            "automatizar_moba",
            "automatizar_bigbrother",
            "automatizar_piquete",
            "automatizar_hedge",
            "producao_leite",
            "resumo_aquatico",
        ):
            self.assertNotIn(especifica, nomes)
        self.assertIn("cadastrar_funcionario", nomes)
        self.assertIn("listar_tarefas", nomes)

    # ── o filtro viaja com a resposta ──

    def test_a_resposta_diz_que_grupos_foram_usados(self):
        """Sem isto, a IA não sabe se viu 94 capacidades ou 80, e não tem como
        dizer ao produtor 'só mostro o que você cultiva'."""
        from app.amplia_mcp.capacidades import catalogo_de_capacidades

        self._respondeu(self.soja)
        filtro = catalogo_de_capacidades(user=self.user)["filtro"]
        self.assertEqual(filtro["culturas"], ["graos"])

        self.assertIsNone(
            catalogo_de_capacidades(user=self.user, filtrar_culturas=False)["filtro"][
                "culturas"
            ],
            "o catálogo inteiro não devolve grupos",
        )

    # ── higiene do registo ──

    def test_nenhuma_capacidade_sumiu_do_registro(self):
        """O filtro esconde; não apaga. `automatizar_aerador` tem de continuar
        a existir para quando o produtor escolher peixe."""
        from app.ia import registro as reg

        for nome in (
            "automatizar_aerador",
            "automatizar_moba",
            "automatizar_bigbrother",
            "automatizar_piquete",
            "automatizar_hedge",
            "producao_leite",
            "resumo_aquatico",
        ):
            self.assertIn(nome, reg.REGISTO)

    def test_toda_marca_aplica_a_e_conhecida(self):
        """Marca escrita à pressa é o bug silencioso: `aplica_a="aquicola"`
        não dá erro, só deixa de cortar. A CORRIGIR é falhar aberta (não
        filtra), mas o registo tem de ser limpo — por isso este teste."""
        from app.ia import registro as reg

        for nome, spec in reg.REGISTO.items():
            marca = (spec or {}).get("aplica_a")
            self.assertIn(
                marca,
                (None, "vegetal", "animal", "aquatica", "aves"),
                f"{nome} tem aplica_a={marca!r}, que ninguem sabe interpretar",
            )

    def test_a_marca_esta_onde_a_descricao_diz(self):
        """Cada marca precisa de pelo menos UM caso que a confirme.

        E' a defesa contra a marca inventada: marcar `automatizar_aerador`
        como `aves` porque "ave" e "peso" parecem alike. O teste não valida
        que a marca é a certa em agronomia — isso é do domínio do produtor —
        valida que a marca não é ACIDENTAL.
        """
        from app.ia import registro as reg

        for nome, spec in reg.REGISTO.items():
            marca = (spec or {}).get("aplica_a")
            if not marca:
                continue
            texto = " ".join(
                [spec.get("descricao") or ""]
                + [str(e) for e in (spec.get("exemplos") or [])]
            ).lower()
            with self.subTest(intent=nome, marca=marca):
                self.assertTrue(
                    texto,
                    f"{nome} tem marca mas nao tem descricao nem exemplos",
                )
