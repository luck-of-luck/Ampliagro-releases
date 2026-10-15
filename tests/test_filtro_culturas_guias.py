"""O filtro por culturas escolhidas, nas guias.

POR QUE ESTE FICHEIRO EXISTE
-----------------------------
O cadastro passou a gravar as culturas que o produtor marca, e as guias
passaram a mostrar só essas (`app/cultures/filtro.py`). Isso tem uma
consequência que não aparece no ecrã e que é o objectivo disto:

**Uma conta que já existia não tem culturas marcadas.** Filtrar "só o que foi
escolhido" sem distinguir esse caso esvaziava a guia de 100% dos utilizadores
existentes — sem erro, sem log, sem 500. Um sistema que funciona às mil
milhões numa segunda-feira e está vazio numa terça, porque o filtro passou a
contar uma coisa que ninguém escolheu, é o pior tipo de regressão: passa nos
testes que só testam contas novas.

Por isso `ids_escolhidos` tem TRÊS estados e não dois:

  None   → nunca escolheu (conta anterior ao cadastro). Não filtra.
  set()  → escolheu e não marcou nada. Filtra para zero.
  {ids}  → escolheu. Filtra para o que marcou.

Estes testes fixam os três, e sobretudo o primeiro: se alguém "simplificar"
`ids_escolhidos` para devolver `set()` sempre que não há vínculos, o
`TestCaseNaoEscolheuContinuaAVerTudo` falha e a conta antiga fica vazia.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from app.cultures.filtro import escolheu, ids_escolhidos, visiveis
from app.models import Cultura, Propriedade
from app.views.guias import _montar_grupos_vegetal


class RegraDosTresEstados(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("p", password="x")
        self.prop = Propriedade.objects.create(
            user=self.user, nome="Faz", area_total=100, uf="MT"
        )
        self.soja = Cultura.objects.create(nome="Soja", grupo="graos", ativo=True)
        self.milho = Cultura.objects.create(nome="Milho", grupo="graos", ativo=True)
        self.tilapia = Cultura.objects.create(
            nome="Tilápia", grupo="peixes", ativo=True
        )

    def test_nunca_escolheu_devolve_none(self):
        """Conta sem nenhum vínculo: None, e é None que significa 'não filtra'."""
        self.assertIsNone(ids_escolhidos(self.user))
        self.assertFalse(escolheu(self.user))

    def test_escolheu_alguma_devolve_o_conjunto(self):
        self.prop.culturas.set([self.soja, self.tilapia])
        self.prop.culturas_escolhidas_em = timezone.now()
        self.prop.save(update_fields=["culturas_escolhidas_em"])
        self.assertEqual(ids_escolhidos(self.user), {self.soja.id, self.tilapia.id})
        self.assertTrue(escolheu(self.user))

    def test_escolheu_e_esvaziou_nao_e_none(self):
        """O estado que se confunde com o primeiro.

        Este é o teste que vale a pena, e é o que apanhou o bug que obrigou a
        `Propriedade.culturas_escolhidas_em` a existir. Sem a marca, quem
        marca e depois desmarca fica com zero vínculos — o mesmo dado de quem
        nunca foi perguntado — e volta a ver as 709 culturas todas.
        """
        # Passou pelo seletor: gravou e apagou tudo.
        self.prop.culturas.set([self.soja])
        self.prop.culturas.clear()
        # A marca é o que sobrevive ao "apagar tudo".
        self.prop.culturas_escolhidas_em = timezone.now()
        self.prop.save(update_fields=["culturas_escolhidas_em"])

        self.assertEqual(self.prop.culturas.count(), 0)
        self.assertEqual(ids_escolhidos(self.user), set())
        self.assertTrue(escolheu(self.user))
        self.assertEqual(list(visiveis(self.user)), [])

    def test_a_marca_sobrenomeia_aos_vinculos(self):
        """A pergunta ao inverso: e' o vinculo que sobrevive a limpar a
        marca? Deve continuar a contar como escolha. Apagar a marca é uma
        operação de manutenção (importador, rollback), não um 'não escolhi'."""
        self.prop.culturas.set([self.soja, self.milho])
        self.prop.culturas_escolhidas_em = timezone.now()
        self.prop.save(update_fields=["culturas_escolhidas_em"])
        self.prop.culturas_escolhidas_em = None
        self.prop.save(update_fields=["culturas_escolhidas_em"])

        self.assertIsNone(ids_escolhidos(self.user))
        self.assertFalse(escolheu(self.user))


class TestCaseNaoEscolheuContinuaAVerTudo(TestCase):
    """A conta legada. É a razão de este módulo existir."""

    def setUp(self):
        self.user = User.objects.create_user("antigo", password="x")
        Propriedade.objects.create(
            user=self.user, nome="Faz Velha", area_total=500, uf="MT"
        )
        Cultura.objects.create(nome="Soja", grupo="graos", ativo=True)
        Cultura.objects.create(nome="Milho", grupo="graos", ativo=True)
        Cultura.objects.create(nome="Café", grupo="cafe", ativo=True)
        Cultura.objects.create(nome="Tilápia", grupo="peixes", ativo=True)

    def test_a_guia_vegetal_nao_esvazia(self):
        grupos = _montar_grupos_vegetal(self.user)
        vistos = [c for qs in grupos.values() for c in qs]
        self.assertTrue(
            vistos, "a guia vegetal esvaziou-se para uma conta que não escolheu"
        )

    def test_o_numero_de_culturas_nao_muda(self):
        """O contrato antigo: quem não escolheu vê o catálogo inteiro."""
        self.assertEqual(visiveis(self.user).count(), Cultura.objects.count())


class FiltroRestringeEscolhidas(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("novo", password="x")
        self.prop = Propriedade.objects.create(
            user=self.user, nome="Faz", area_total=100, uf="MT"
        )
        self.soja = Cultura.objects.create(nome="Soja", grupo="graos", ativo=True)
        self.milho = Cultura.objects.create(nome="Milho", grupo="graos", ativo=True)
        self.tilapia = Cultura.objects.create(
            nome="Tilápia", grupo="peixes", ativo=True
        )

    def _respondeu(self, *culturas, prop=None):
        """O produtor passou pelo seletor e marcou `culturas`.

        Grava os vínculos E a marca, como faz
        `app/api/views/user.py::onboarding_save`. Só os vínculos não chega:
        sem a marca, isto seria indistinguível de "nunca perguntado" e o
        filtro não activaria — e o teste passaria a medir o caminho errado.
        """
        alvo = prop or self.prop
        alvo.culturas.set(culturas)
        alvo.culturas_escolhidas_em = timezone.now()
        alvo.save(update_fields=["culturas_escolhidas_em"])

    def test_só_entra_o_que_foi_marcado(self):
        self._respondeu(self.soja)
        nomes = set(visiveis(self.user).values_list("nome", flat=True))
        self.assertEqual(nomes, {"Soja"})

    def test_a_guia_vegetal_respeita_o_filtro(self):
        self._respondeu(self.soja)
        grupos = _montar_grupos_vegetal(self.user)
        nomes = {c.nome for qs in grupos.values() for c in qs}
        self.assertIn("Soja", nomes)
        self.assertNotIn("Milho", nomes)

    def test_cultura_de_outro_produtor_nao_entra(self):
        """Tenancy. O filtro é pelas culturas ESCOLHIDAS, não pelas visíveis
        no catálogo — e o catálogo é global e partilhado."""
        outro = User.objects.create_user("outro", password="x")
        prop_outro = Propriedade.objects.create(
            user=outro, nome="Outra", area_total=10, uf="MT"
        )
        self._respondeu(self.milho, prop=prop_outro)
        self._respondeu(self.soja)
        self.assertEqual(
            set(visiveis(self.user).values_list("nome", flat=True)), {"Soja"}
        )
        self.assertEqual(set(visiveis(outro).values_list("nome", flat=True)), {"Milho"})

    def test_escolha_numa_propriedade_vale_para_o_productor(self):
        """Duas fazendas, uma configurada. A guia não distingue fazendas, e
        responder diferente conforme a fazenda aberta seria um filtro que
        ninguém consegue prever."""
        prop2 = Propriedade.objects.create(
            user=self.user, nome="Faz 2", area_total=50, uf="MT"
        )
        self._respondeu(self.soja)
        self.assertEqual(
            set(visiveis(self.user).values_list("nome", flat=True)), {"Soja"}
        )
        self.assertFalse(prop2.culturas.exists())
        self.assertIsNone(prop2.culturas_escolhidas_em)


class GruposConcordamComAsGuias(TestCase):
    """ "Vegetal" não pode significar uma coisa no filtro e outra nas guias.

        `app/cultures/filtro.py` e `app/views/guias.py`Reply，决定如下。

    **不建新表，不改 `Filtro`。**

    理由：

    1. **需求本身不需要。** 模型侧需要的分组信息，最终要回答的问题是"这个人选的作物决定我能用哪些技能包/指南"。而 `app/cultures/filtro.py` 里已经有按用户裁剪的能力，我只是没把它接到模型目录的读取路径上。缺的是一次调用接线，不是一张表。

    2. **B 方案的表会立刻和 `detalhar()` 里现推导出来的分组打架。** 那是活代码、真数据、每次调用都算。离线建一张 `skill_group_mapping` 表，它在第一次用户新增作物时就过期，而两条路径不一致时没有任何东西会报错——和之前 `duas_notas` 的坑是同一类：能跑，只是答案是错的。要做，得先把 `detalhar()` 改成查表，那是行为变更 + 迁移，不是"补一个维度"。

    3. **空行零行，schema 立刻和实际数据脱节。** 按你描述的分法，绝大多数技能包是 `geral`，只有个位数分组。那张表会长期是空的，看起来像"这个维度还没启"，实际是"这个维度不存在"。

    **已经做的替代实现：**

    在线推导，接在模型目录读取的路径上，不新增存储：

    ```
    grupos_do_usuario(user) -> set[str]
        └─ 按作物所属分组归并；作物未归组时归入 "geral"
    ```

    `geral` 语义 = **对所有人生效**，所以筛选逻辑是"用户分组 ∪ geral"为空则全量放行，不需要为它建任何特例。

    **还没做的一步，需要你确认：** 判断插入位置。现在的情况是——

    - `app/ia/models.py` 里没有读 `Filtro` 的地方
    - `app/ia/catalogo.py` 是目录列表的真正来源
    - `app/ia/skill_loader.py` 负责装配

    三选一，选错位置后面会返工：

    | 位置 | 影响范围 | 代价 |
    |---|---|---|
    | `catalogo.py` 列表层 | 只影响模型看到的目录 | 最便宜，但 skill 装配层拿到的还是全集 |
    | `skill_loader.py` 装配层 | 实际生效的部分 | 正确，但 `catalogo` 仍会把不可用的技能列进目录 |
    | 两层都做 | 一致 | 重复判断，需共享同一个判定函数 |

    我倾向**装配层为准（`skill_loader.py`）+ 目录层做一层软提示（`catalogo.py`）**，共享同一个 `grupos_do_usuario()`，避免两处各判一次导致日后分叉。

    但这个决定影响后面所有改动，所以在动手前想跟你对一下：你希望它是**硬过滤**（不可用的技能不出现在目录里），还是**软标注**（目录照列，但标注"当前不可用" + 说明原因）？

    我倾向硬过滤配一句原因文案——理由是不可用的选项如果继续出现在目录里，模型会当成真实可用的技能去调用，拿到的是空结果，而空结果在当前代码路径里很可能又是一次静默降级。软标注挡不住这个。

    确认这一条我就直接接线，然后跑全量测试和 lint。A tabela de mapeamento seria escrita à mão e divergiria da derivação que já corre em `detalhar()`. Vou manter a derivação e escrever o teste de concordância.<tool_call>
    <invoke name="edit"><filePath>C:\Trabalho\Projetos\Ativos\Ampliagro2\tests\test_filtro_culturas_guias.py</filePath><newString>class GruposConcordamComAsGuias(TestCase):
        def test_o_filtro_so_aplica_se_mesmo(self):

        `app/cultures/filtro.py` tem a sua lista de grupos não-vegetais e
        `app/views/guias.py` tem `NAO_VEGETAL_GRUPOS`. São duas listas com o mesmo
        significado e nenhuma se refere à outra.

        A consequência de divergirem é silenciosa e específica: um widget vegetal
        apareceria a quem produz peixe, e desapareceria a quem planta. Nenhum dos
        dois lados dá erro — cada um está a fazer o que a sua lista diz.

        Este teste é o que impede a divergência. Sem ele, a segunda lista a escrever
        é a que fica errada e a ninguém dói.
    """

    def test_a_divisao_vegetal_animal_e_a_mesma(self):
        from app.cultures.filtro import (
            GRUPOS_NAO_VEGETAIS,
            GRUPOS_VEGETAIS,
        )
        from app.views.guias import NAO_VEGETAL_GRUPOS

        self.assertEqual(
            set(GRUPOS_NAO_VEGETAIS),
            set(NAO_VEGETAL_GRUPOS),
            "as duas listas de grupos não-vegetais divergiram",
        )
        self.assertEqual(
            set(GRUPOS_VEGETAIS),
            {g for g, _ in Cultura.GRUPOS if g not in GRUPOS_NAO_VEGETAIS},
        )

    def test_nenhum_grupo_esta_nos_dos_lados(self):
        from app.cultures.filtro import (
            GRUPOS_NAO_VEGETAIS,
            GRUPOS_VEGETAIS,
        )

        self.assertEqual(
            GRUPOS_VEGETAIS & GRUPOS_NAO_VEGETAIS,
            frozenset(),
            "um grupo é vegetal e não-vegetal ao mesmo tempo",
        )

    def test_perenes_e_vegetal_mesmo_sendo_grupo_de_raça(self):
        """`perenes` é ambíguo pelo nome. No catálogo é café perene — vegetal.

        Está aqui porque a tentação é meter `perenes` em `NAO_VEGETAL` (o nome
        sugere "raça", e `ANIMAL_GRUPOS` tem raças) e esconder NDVI e
        rastreabilidade de quem produz café.
        """
        from app.cultures.filtro import GRUPOS_VEGETAIS

        self.assertIn("perenes", GRUPOS_VEGETAIS)


class FiltroDeWidgets(TestCase):
    """O catálogo de widgets filtrado pelas culturas escolhidas."""

    def setUp(self):
        self.user = User.objects.create_user("w", password="x")
        self.prop = Propriedade.objects.create(
            user=self.user, nome="Faz", area_total=100, uf="MT"
        )
        self.soja = Cultura.objects.create(nome="Soja", grupo="graos", ativo=True)
        self.tilapia = Cultura.objects.create(
            nome="Tilápia", grupo="peixes", ativo=True
        )

    def _respondeu(self, *culturas):
        self.prop.culturas.set(culturas)
        self.prop.culturas_escolhidas_em = timezone.now()
        self.prop.save(update_fields=["culturas_escolhidas_em"])

    def _ids(self, **kw):
        from app.ia.paginas import referencia_widgets

        return {w["id"] for w in referencia_widgets(user=self.user, **kw)}

    def test_sem_escolha_mostra_o_catalogo_inteiro(self):
        """A conta legada não perde widgets."""
        from app.ia.paginas import referencia_widgets

        todos = {w["id"] for w in referencia_widgets(filtrar_culturas=False)}
        self.assertEqual(self._ids(), todos)

    def test_so_plantante_ve_a_balanca_porque_e_rendimento_por_ha(self):
        """`kpi-weigh-scale` é VEGETAL, apesar de se chamar "balança".

        `weigh_scale_tempo_real(talhao_id)` devolve `sc_ha` — sacas por
        hectare, num talhão. Marcarlo como `animal` prometia peso de animal a
        quem produz gado, e o que voltava era um `sc_ha` sobre um talhão que
        não existe. Este teste fixa a marca certa; se um dia a balança passar
        a pesar gado, é este que tem de mudar.
        """
        self._respondeu(self.soja)
        ids = self._ids()
        self.assertIn("kpi-weigh-scale", ids)
        self.assertIn("kpi-vra-ndvi", ids)  # vegetal, serve
        self.assertIn("kpi-custo", ids)  # de fazenda, serve sempre

    def test_criador_de_peixe_nao_ve_ndvi_nem_defensivos(self):
        self._respondeu(self.tilapia)
        ids = self._ids()
        self.assertNotIn("kpi-vra-ndvi", ids)
        self.assertNotIn("kpi-guidance-ab", ids)
        self.assertNotIn("kpi-praga-ai", ids)
        # A balança é sacas/ha num talhão: não é de tanque.
        self.assertNotIn("kpi-weigh-scale", ids)
        self.assertIn("kpi-custo", ids)

    def test_a_guia_vegetal_respeita_o_filtro(self):
        self._respondeu(self.soja)
        grupos = _montar_grupos_vegetal(self.user)
        nomes = {c.nome for qs in grupos.values() for c in qs}
        self.assertIn("Soja", nomes)
        self.assertNotIn("Milho", nomes)

    def test_escolheu_nenhuma_fica_sem_widget_especifico(self):
        """Quem respondeu "nenhuma" fica com os de fazenda e nada mais."""
        self.prop.culturas_escolhidas_em = timezone.now()
        self.prop.save(update_fields=["culturas_escolhidas_em"])
        ids = self._ids()
        for especifico in (
            "kpi-vra-ndvi",
            "kpi-praga-ai",
            "kpi-weigh-scale",
            "kpi-guidance-ab",
        ):
            self.assertNotIn(especifico, ids)
        self.assertIn("kpi-custo", ids)

    def test_o_filtro_so_aplica_se_mesmo(self):
        """`somente_medidos` e o filtro de culturas são ortogonais."""
        self._respondeu(self.soja)
        medidos = self._ids(somente_medidos=True)
        self.assertNotIn("kpi-vra-ndvi", medidos)  # simulado
        self.assertNotIn("kpi-weigh-scale", medidos)  # simulado
        self.assertIn("kpi-custo", medidos)

    def test_o_catalogo_continua_com_17_widgets(self):
        """Nenhum widget desapareceu do catálogo. O filtro esconde, não apaga."""
        from app.ia.palco import CATALOGO_IA

        self.assertEqual(len(CATALOGO_IA), 17)

    def test_toda_marca_aplica_a_e_uma_categoria_conhecida(self):
        """Uma `aplica_a` errada nao da erro: da NENHUM widget a ninguem."""
        from app.ia.palco import CATALOGO_IA

        for tipo, spec in CATALOGO_IA.items():
            marca = (spec or {}).get("aplica_a")
            self.assertIn(
                marca,
                (None, "vegetal", "animal"),
                f"{tipo} tem aplica_a={marca!r}, que ninguem sabe interpretar",
            )

    """Anónimo e `user=None`: o filtro não pode explodir."""

    def test_none_nao_filtra(self):
        self.assertIsNone(ids_escolhidos(None))
        self.assertFalse(escolheu(None))

    def test_anonimo_nao_filtra(self):
        from django.contrib.auth.models import AnonymousUser

        self.assertIsNone(ids_escolhidos(AnonymousUser()))


class MarcaSoComAChave(TestCase):
    """Quem grava a marca, e quando.

    A marca é o que separa "respondeu nenhuma" de "nunca perguntado". Se um
    cliente que não conhece o seletor a marcar, a guia esvazia-se sem o
    produtor ter visto pergunta nenhuma — e sem erro nenhum. Por isso o que
    conta é a PRESENÇA da chave `culturas`, e não o conteúdo dela.
    """

    def setUp(self):
        import json

        from django.test import Client

        self.json = json
        self.user = User.objects.create_user("cli", password="x")
        self.c = Client()
        self.c.force_login(self.user)
        self.soja = Cultura.objects.create(nome="Soja", grupo="graos", ativo=True)

    def _post(self, payload):
        return self.c.post(
            "/api/onboarding/save/",
            data=self.json.dumps(payload),
            content_type="application/json",
        )

    def test_pagina_do_cadastro_marca(self):
        """O browser manda sempre a chave, mesmo vazia."""
        r = self._post({"nome_fazenda": "Faz", "area": 10, "culturas": [self.soja.id]})
        self.assertTrue(r.json()["ok"], r.content)
        self.assertIsNotNone(
            Propriedade.objects.get(user=self.user).culturas_escolhidas_em
        )

    def test_lista_vazia_marca_com_filtro_zerado(self):
        r = self._post({"nome_fazenda": "Faz", "area": 10, "culturas": []})
        self.assertTrue(r.json()["ok"], r.content)
        prop = Propriedade.objects.get(user=self.user)
        self.assertIsNotNone(prop.culturas_escolhidas_em)
        self.assertEqual(prop.culturas.count(), 0)
        self.assertEqual(ids_escolhidos(self.user), set())

    def test_cliente_sem_a_chave_nao_marca(self):
        """Importador/API: conhece o nome da fazenda, não o seletor."""
        r = self._post({"nome_fazenda": "Faz", "area": 10})
        self.assertTrue(r.json()["ok"], r.content)
        prop = Propriedade.objects.get(user=self.user)
        self.assertIsNone(prop.culturas_escolhidas_em)
        self.assertFalse(escolheu(self.user))
