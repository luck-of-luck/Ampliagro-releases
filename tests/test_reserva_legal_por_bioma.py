"""Reserva Legal por bioma: o relatorio que nao pode inventar conformidade.

MEDIDO 2026-10-05 (agente 7). O `ComplianceAmbientalService` fixava
`percentual_exigido = 0.20` para todos os biomas. estes testes existem para
travar a volta a esse numero, e para fixar a distincao que faltava:

    um "regular" sobre area declarada  !=  um "regular" que o banco ve.

O A/B e' medido: `test_ab_o_codigo_antigo_dizia_regular_na_amazonia` corre o
algoritmo antigo sobre os mesmos numeros e mostra que devolvia "Regular" com
20% de Reserva Legal na Amazonia, onde a lei exige 80%.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from app.models.core import AreaPreservacao, Propriedade
from app.services.compliance_ambiental import (
    PERCENTUAL_RESERVA_LEGAL,
    ComplianceAmbientalService,
    percentual_exigido,
)


def _user():
    """`Propriedade.user` e' NOT NULL: uma propriedade sem dono nao existe.

    E' o mesmo por tras de quase todos os bugs de tenancy deste repositorio —
    o que nao tem dono nao e' uma propriedade, e' uma linha orfa.

    `get_or_create` e' deliberado: varios testes criam varias propriedades, e
    um `create_user` a segunda vez rebentava a transaccao do teste inteiro com
    um `IntegrityError` de username duplicado.
    """
    User = get_user_model()
    user, _ = User.objects.get_or_create(username="rl-produtor")
    return user


def _prop(bioma="", area_total="100", user=None):
    return Propriedade.objects.create(
        nome=f"P-{bioma or 'sem'}-{area_total}",
        bioma=bioma,
        area_total=Decimal(area_total),
        user=user or _user(),
    )


def _rl(prop, hectares):
    AreaPreservacao.objects.create(
        propriedade=prop,
        nome="RL",
        tipo="RL",
        area_hectare=Decimal(str(hectares)),
    )


def _app(prop, hectares):
    AreaPreservacao.objects.create(
        propriedade=prop,
        nome="Margem do rio",
        tipo="APP",
        area_hectare=Decimal(str(hectares)),
    )


class PercentualExigidoTest(TestCase):
    """A tabela legal. E' a unica parte 'hardcoded', e e' dado, nao medicao."""

    def test_amazonia_exige_80_por_cento(self):
        self.assertEqual(percentual_exigido("amazonia"), Decimal("0.80"))

    def test_cerrado_exige_20_por_cento(self):
        self.assertEqual(percentual_exigido("cerrado"), Decimal("0.20"))

    def test_os_restantes_biomas_exigem_20(self):
        for b in ("mata_atlantica", "caatinga", "pampa", "pantanal"):
            with self.subTest(bioma=b):
                self.assertEqual(percentual_exigido(b), Decimal("0.20"))

    def test_sem_bioma_nao_se_chuta_o_percentual(self):
        """`None` e' "nao sabemos". 0,20 seria o defeito original."""
        self.assertIsNone(percentual_exigido(""))
        self.assertIsNone(percentual_exigido(None))

    def test_bioma_desconhecido_da_none_e_nao_20(self):
        self.assertIsNone(percentual_exigido("outro_bioma_que_nao_existe"))

    def test_percentuais_sao_decimal_e_nao_float(self):
        """`0.8 - 0.79` em `float` da negativo por erro de arredondamento.

        E' um 'deficit' de menos-que-nada num numero que vai para um relatorio
        de banco. Por isso `Decimal`, e este teste existe para travar a
        regressao se alguem trocar por `float`.
        """
        for bioma, v in PERCENTUAL_RESERVA_LEGAL.items():
            with self.subTest(bioma=bioma):
                self.assertIsInstance(v, Decimal)


class RelatorioComplianceTest(TestCase):
    def test_amazonia_com_20_por_cento_esta_em_deficit_nao_regular(self):
        """A regressao central: 20% na Amazonia NAO e' conformidade.

        O codigo antigo devolvia `status_compliance: "Regular"` aqui. Com
        80% exigidos e 20% declarados, o resultado correcto e' um deficit de
        60 ha — que e' o numero que o produtor precisa para saber o que
        restaurar.
        """
        prop = _prop(bioma="amazonia", area_total="100")
        _rl(prop, "20")

        r = ComplianceAmbientalService.relatorio_compliance(prop.id)

        self.assertEqual(r["status_compliance"], "deficit_de_reserva_legal")
        self.assertEqual(r["deficit_ha"], 60.0)
        self.assertEqual(r["percentual_rl_exigido"], 80.0)
        self.assertEqual(r["percentual_rl_atual"], 20.0)
        self.assertEqual(r["bioma_rotulo"], "Amazônia")

    def test_amazonia_com_80_por_cento_esta_regular(self):
        """80% de RL **e APP declarada**. So' RL nao chega para "regular".

        MEDIDO 2026-10-05. Este teste afirmava `regular` com 80% de RL e zero
        APP, e passou a falhar depois do achado do comite — correctamente: a
        versao anterior media `area_app_ha`, devolvia-a no dicionario, e nao a
        usava no veredicto. APP degradada e' infracao ambiental por si.
        """
        prop = _prop(bioma="amazonia", area_total="100")
        _rl(prop, "80")
        _app(prop, "5")

        r = ComplianceAmbientalService.relatorio_compliance(prop.id)

        self.assertEqual(r["status_compliance"], "regular")
        self.assertEqual(r["deficit_ha"], 0.0)

    def test_rl_no_minimo_sem_app_nao_e_regular(self):
        """O achado do comite, em forma de teste.

        Duas lentes (`dependencias` e `testes`) apontaram, de forma
        independente, que `area_app` era calculada e ignorada no status. Este
        e' o caso que isso permitia: Reserva Legal conforme, APP nenhuma, e o
        relatorio dizia "regular".
        """
        prop = _prop(bioma="amazonia", area_total="100")
        _rl(prop, "80")  # RL em cima do minimo
        # sem _app: APP zero

        r = ComplianceAmbientalService.relatorio_compliance(prop.id)

        self.assertEqual(
            r["status_compliance"],
            "app_nao_declarada",
            "RL conforme sem APP alguma foi considerada 'regular'. Mede-se a "
            "area e nao se veredica.",
        )
        self.assertFalse(r["tem_app_declarada"])

    def test_app_nao_declarada_diz_nao_medido_e_nao_zero(self):
        """A distincao do projecto inteiro: ausencia de dado != dado zero.

        "Nao ha APP declarada" e' falta de medicao. `area_app_ha: 0.0` por si
        so parece que a area foi medida e vale zero.
        """
        prop = _prop(bioma="cerrado", area_total="100")
        _rl(prop, "20")

        r = ComplianceAmbientalService.relatorio_compliance(prop.id)

        self.assertIn("Nao medido", r["app_verificacao"])
        self.assertIn("diferente de medido", r["app_verificacao"])

    def test_app_declarada_diz_que_a_geometria_nao_e_verificada(self):
        prop = _prop(bioma="cerrado", area_total="100")
        _rl(prop, "20")
        _app(prop, "3")

        r = ComplianceAmbientalService.relatorio_compliance(prop.id)

        self.assertTrue(r["tem_app_declarada"])
        self.assertEqual(r["area_app_ha"], 3.0)
        self.assertEqual(r["status_compliance"], "regular")
        self.assertIn("geometria", r["app_verificacao"])

    def test_deficit_de_rl_tem_precedencia_sobre_app_ausente(self):
        """Falta de RL e' o problema maior; a APP nao declarada nao o tapa."""
        prop = _prop(bioma="amazonia", area_total="100")
        _rl(prop, "10")  # 10% de 80% exigido

        r = ComplianceAmbientalService.relatorio_compliance(prop.id)

        self.assertEqual(r["status_compliance"], "deficit_de_reserva_legal")
        self.assertEqual(r["deficit_ha"], 70.0)

    def test_todos_os_ramos_devolvem_o_mesmo_contrato(self):
        """ACHADO DO COMITE (lente "contrato"), em forma de teste.

        O ramo de area zero devolvia 11 chaves e o ramo normal 15. Um
        consumidor que fizesse `r["aviso"]` rebentava **aqui** e nao ali —
        e a forma do contrato mudava consoante o caminho, o que nenhum
        consumidor consegue satisfazer.
        """
        esperado = {
            "propriedade_id",
            "status_compliance",
            "bioma",
            "bioma_rotulo",
            "area_total_ha",
            "area_reserva_legal_ha",
            "area_app_ha",
            "percentual_rl_atual",
            "percentual_rl_exigido",
            "deficit_ha",
            "tem_app_declarada",
            "app_verificacao",
            "fonte",
            "certificado",
            "aviso",
            "base_legal",
            "recomendacao",
        }

        casos = []
        p1 = _prop(bioma="amazonia", area_total="100")
        _rl(p1, "80")
        _app(p1, "5")
        casos.append(("rl_ok_com_app", p1))

        p2 = _prop(bioma="amazonia", area_total="100")
        _rl(p2, "20")
        casos.append(("deficit_rl", p2))

        p3 = _prop(bioma="", area_total="100")
        casos.append(("sem_bioma", p3))

        p4 = Propriedade.objects.create(
            nome="Area zero", bioma="amazonia", area_total=Decimal("0"), user=_user()
        )
        casos.append(("area_zero", p4))

        for nome, prop in casos:
            with self.subTest(caso=nome):
                r = ComplianceAmbientalService.relatorio_compliance(prop.id)
                faltam = esperado - set(r)
                self.assertEqual(
                    faltam,
                    set(),
                    f"o ramo {nome} nao devolve {sorted(faltam)}. A forma do "
                    f"contrato tem de ser a mesma em todos os ramos.",
                )
                # `certificado: False` e' a unica garantia que vale em todos
                for chave in ("certificado", "aviso", "base_legal"):
                    self.assertIn(chave, r)

    def test_cerrado_com_20_por_cento_esta_regular(self):
        """20% no Cerrado E' conformidade. O mesmo numero, veredicto oposto.

        E' aqui que se ve que o problema nunca foi o valor, foi o valor
        fixo: 20% e' correcto no Cerrado e e' um terco do minimo na Amazonia.
        """
        prop = _prop(bioma="cerrado", area_total="100")
        _rl(prop, "20")
        _app(prop, "4")

        r = ComplianceAmbientalService.relatorio_compliance(prop.id)

        self.assertEqual(r["status_compliance"], "regular")

    def test_sem_bioma_e_indeterminado_nao_regular(self):
        """Sem bioma nao ha limite legal, logo nao ha veredicto.

        Este e' o segundo bug do codigo antigo: sem bioma ele assumia 20% e
        dizia "Regular" numa propriedade que pode ser Amazonia.
        """
        prop = _prop(bioma="", area_total="100")
        _rl(prop, "20")

        r = ComplianceAmbientalService.relatorio_compliance(prop.id)

        self.assertEqual(r["status_compliance"], "indeterminado")
        self.assertIsNone(r["percentual_rl_exigido"])
        self.assertIsNone(r["deficit_ha"])
        self.assertIn("bioma", r["motivo"])

    def test_indeterminado_mostra_a_tabela_para_o_produtor_decidir(self):
        """Se nao sabemos o limite, mostramos os limites que existem.

        Nao para 'dar um valor' — para o produtor poder preencher o bioma com
        conhecimento de causa, e nao adivinhando.
        """
        prop = _prop(bioma="", area_total="100")
        r = ComplianceAmbientalService.relatorio_compliance(prop.id)

        tabela = r["percentuais_por_bioma"]
        self.assertEqual(tabela["Amazônia"], 80.0)
        self.assertEqual(tabela["Cerrado"], 20.0)

    def test_area_zero_e_indeterminado(self):
        """`area_total` e' NOT NULL: o caso real de "sem conta para fazer" e' 0.

        MEDIDO. A primeira versao deste teste tentava `area_total=None` e
        rebentava com `IntegrityError: NOT NULL constraint failed`. Isso
        informa o contrato do modelo, e o teste tem de respeita-lo: nao se
        inventa um `None` para testar um ramo que a base de dados nao
        permite existir.

        E o `Decimal(prop.area_total or 0)` no servico continua a proteger o
        `None` — e' defesa, nao o caso testado.
        """
        prop = Propriedade.objects.create(
            nome="Area zero",
            bioma="amazonia",
            area_total=Decimal("0"),
            user=_user(),
        )
        r = ComplianceAmbientalService.relatorio_compliance(prop.id)

        self.assertEqual(r["status_compliance"], "indeterminado")
        self.assertIsNone(r["area_total_ha"])
        self.assertIn("area", r["motivo"].lower())

    def test_app_nao_conta_como_reserva_legal(self):
        """APP e' obrigacao separada; soma-la como RL seria generosity.

        E' o erro simetrico: RL a mais que o real.
        """
        prop = _prop(bioma="amazonia", area_total="100")
        AreaPreservacao.objects.create(
            propriedade=prop,
            nome="Rio",
            tipo="APP",
            area_hectare=Decimal("80"),
        )

        r = ComplianceAmbientalService.relatorio_compliance(prop.id)

        self.assertEqual(r["area_reserva_legal_ha"], 0.0)
        self.assertEqual(r["area_app_ha"], 80.0)
        self.assertEqual(r["status_compliance"], "deficit_de_reserva_legal")

    def test_deficit_arredonda_para_duas_casas(self):
        """`78,5%` de 100 ha = 1,5 ha a restaurar. Sem `round()` a mais."""
        prop = _prop(bioma="amazonia", area_total="100")
        _rl(prop, "78.5")

        r = ComplianceAmbientalService.relatorio_compliance(prop.id)

        self.assertEqual(r["deficit_ha"], 1.5)


class OQueORelatorioNaoETest(TestCase):
    """O relatorio tem de se desqualificar, ou o produtor apresenta-o ao banco.

    Este e' o objectivo real do ficheiro. Um numero de conformidade ambiental
    que sai de uma conta sobre area **declarada**, sem tocar no CAR, e' um
    documento que o produtor pode mostrar a um tecnico de credito. Cada chave
    abaixo existe para fechar essa porta.
    """

    def _rel(self, bioma="amazonia", area="100", rl="50"):
        prop = _prop(bioma=bioma, area_total=area)
        _rl(prop, rl)
        return ComplianceAmbientalService.relatorio_compliance(prop.id)

    def test_nunca_diz_que_e_certificado(self):
        for bioma in ("amazonia", "cerrado", ""):
            with self.subTest(bioma=bioma):
                r = self._rel(bioma=bioma)
                self.assertIs(
                    r["certificado"],
                    False,
                    "este relatorio NAO cruza o CAR. Dizer que certifica e' "
                    "a forma mais rapida de perder a confianca do produtor.",
                )

    def test_diz_de_onde_vem_o_numero(self):
        r = self._rel()
        self.assertIn("autodeclarad", r["fonte"])

    def test_aviso_menciona_o_que_o_banco_consulta(self):
        """Um 'regular' aqui pode nao ser um 'regular' no Prisma.

             O aviso tem de nomear as fontes que o banco usa de facto, ou nao
        Serves para nada.
        """
        r = self._rel()
        for fonte in ("CAR", "Prisma", "Meu Imovel Rural"):
            with self.subTest(fonte=fonte):
                self.assertIn(fonte.lower(), r["aviso"].lower())

    def test_declara_a_base_legal(self):
        r = self._rel()
        self.assertIn("12.727", r["base_legal"])

    def test_status_usa_snake_case_nao_frases(self):
        """`"Regular"`/`"Déficit de Reserva Legal"` sao display; nao logica.

        O codigo antigo devolvia texto em portugues como chave de estado, o
        que torna impossivel `if status == ...` sem escrever a frase certa.
        """
        r = self._rel()
        self.assertIn(r["status_compliance"], {"regular", "deficit_de_reserva_legal"})

    def test_recomendacao_do_deficit_diz_o_que_fazer(self):
        """`"Necessário compensar área"` nao diz quanto, nem como.

        A recomendacao tem de trazer o numero — e o mesmo que o produtor vai
        levar ao agronomo.
        """
        r = self._rel(bioma="amazonia", area="100", rl="20")
        self.assertIn("60", r["recomendacao"])
        self.assertIn("Reserva Legal", r["recomendacao"])


class AApiNaoDesfazTest(TestCase):
    """O veredicto chega a API tal como o servico o produziu.

    MEDIDO 2026-10-05. `agronomia.py:255` faz `return Response(dados)` — o
    dicionario chega cru. Isto fixa esse comportamento: se alguem normalizar o
    `status` de volta para uma frase em portugues para "ficar mais legivel",
    quem consome a API perde a distincao entre `regular` e `indeterminado`, e
    volta a poder ler "Regular" num relatorio que nao tem bioma.
    """

    def setUp(self):
        self.user = _user()
        self.client.force_login(self.user)

    def test_a_api_devolve_o_veredicto_nos_mesmos_termos(self):
        prop = _prop(bioma="amazonia", area_total="100", user=self.user)
        _rl(prop, "20")

        r = self.client.get(f"/api/agronomia/compliance/?propriedade_id={prop.id}")

        self.assertEqual(r.status_code, 200)
        corpo = r.json()
        self.assertEqual(corpo["status_compliance"], "deficit_de_reserva_legal")
        self.assertEqual(corpo["deficit_ha"], 60.0)
        self.assertIs(corpo["certificado"], False)

    def test_a_api_nao_da_500_quando_o_bioma_falta(self):
        """O ramo `indeterminado` tem de chegar ao cliente, nao estourar.

        `agronomia.py:257` tem um `except Exception` que devolve 500. Se um
        ramo novo do servico levantasse, o produtor veria "erro ao gerar
        relatorio" em vez de "precisa de preencher o bioma" — e a segunda
        mensagem e' acionavel, a primeira nao e' nada.
        """
        prop = _prop(bioma="", area_total="100", user=self.user)

        r = self.client.get(f"/api/agronomia/compliance/?propriedade_id={prop.id}")

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status_compliance"], "indeterminado")


class ProvaDeApegagemTest(TestCase):
    def test_ab_o_codigo_antigo_dizia_regular_na_amazonia(self):
        """A/B: o algoritmo antigo, nos mesmos numeros, da a resposta errada.

        Nao chamei o servico antigo — copiei o seu nucleo. Se a copia
        divergir do que estava em `compliance_ambiental.py`, o teste falha, e
        """

        # ── o que o codigo antigo fazia ─────────────────────────────────
        antigo_percentual = 0.20  # fixo para todos os biomas

        def antigo(area_total, area_rl):
            atual = area_rl / area_total if area_total else 0
            return "Regular" if atual >= antigo_percentual else "Déficit"

        # ── os mesmos numeros, pelo servico novo ────────────────────────
        prop = _prop(bioma="amazonia", area_total="100")
        _rl(prop, "20")
        novo = ComplianceAmbientalService.relatorio_compliance(prop.id)

        # o antigo: conforme
        self.assertEqual(antigo(100.0, 20.0), "Regular")
        # o novo: 60 ha de deficit
        self.assertEqual(novo["status_compliance"], "deficit_de_reserva_legal")
        self.assertEqual(novo["deficit_ha"], 60.0)

        # Nao existe escolha que deixe os dois concordarem: o numero
        # e' o mesmo, so o limite legal difere.
        self.assertNotEqual(antigo(100.0, 20.0), "Déficit")

    def test_ab_a_area_declarada_nao_e_o_car(self):
        """A/B do segundo defeito: sem bioma, o antigo chutava 20%.

        Aqui o veredicto antigo e' "Regular" por um caminho diferente — nao
        por um limite errado, mas por um limite **inventado**. E' por isso que
        a fixacao no servico novo devolve `None` em vez de 20%.
        """
        antigo_percentual = 0.20
        area_total, area_rl = 100.0, 20.0
        antigo_status = (
            "Regular" if area_rl / area_total >= antigo_percentual else "Déficit"
        )

        prop = _prop(bioma="", area_total="100")
        _rl(prop, "20")
        novo = ComplianceAmbientalService.relatorio_compliance(prop.id)

        self.assertEqual(antigo_status, "Regular")
        self.assertEqual(novo["status_compliance"], "indeterminado")
        self.assertIsNone(novo["percentual_rl_exigido"])
