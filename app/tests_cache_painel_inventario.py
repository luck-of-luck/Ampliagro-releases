"""A lista `MODELOS_DO_PAINEL` e uma lista manual — e listas manuais esquecem-se.

O BUG-4 foi exactamente isto: existia uma segunda porta com cache
(`widget_data:<uid>:<0|1>`) ao lado de `dash:<uid>`, e a invalidação apagava
so a primeira. Nao foi erro de logica: foi inventario incompleto.

Este ficheiro trata a MESMA classe de falha no eixo dos MODELOS. A lista
`MODELOS_DO_PAINEL` diz quais modelos, ao guardar, mandam o painel recalcular.
Se um modelo novo entrar no payload de `dashboard_data` e ninguem o acrescentar
a essa lista, o produtor volta a ver o numero velho — e desta vez em silêncio
total, sem nenhum teste falhar.

Nao da para cross-checar "modelos lidos por `dashboard_data`" de forma
totalmente automatica sem analise de AST que envelhece mal. O que este teste
faz e o seguinte, e ja impede o caso silencioso:

1. todo modelo da lista resolve um dono (`_user_de`) — se nao resolver, a
   invalidacao e um no-op silencioso, que e o modo de falha real;
2. um modelo acrescentado a lista sem capacidade de resolver dono e detectado
   no momento da escrita, nao em producao.

Escrever o modelo na lista e um acto deliberado. O que este teste garante e
que esse acto produz efeito.
"""

from __future__ import annotations

from datetime import date

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from app.cache_painel import (
    MODELOS_DO_PAINEL,
    PREFIXOS_DO_PAINEL,
    _chaves_do_usuario,
    _user_de,
)
from app.models import (
    Animal,
    Cultura,
    Funcionario,
    LancamentoFinanceiro,
    Maquinario,
    Propriedade,
    Safra,
    Talhao,
)


class DonoResolvivelTest(TestCase):
    """`_user_de` e o coracao da invalidacao: sem dono, nao apaga nada."""

    def setUp(self):
        self.user = User.objects.create_user("produtor", password="x")
        self.prop = Propriedade.objects.create(
            user=self.user, nome="Fazenda Boa", area_total=100
        )
        self.cultura = Cultura.objects.create(nome="Soja", ativo=True)

    def test_propriedade_resolve_o_proprio_dono(self):
        self.assertEqual(_user_de(self.prop), self.user.id)

    def test_todo_modelo_da_lista_tem_caminho_ate_o_dono(self):
        """Cada modelo da lista tem de ter um owner resolvivel.

        Um modelo acrescentado a lista sem caminho ate `Propriedade.user`
        invalida silenciosamente: `_ligar` liga o sinal, o sinal corre, e
        `cache.delete` nunca e chamado porque `uid` veio `None`. O painel mente
        e nada acusa.

        INSTANCIAS REAIS, nao `model()`: um objecto por construir tem
        `user_id=None` e `propriedade_id=None`, e `_user_de` — que devolve
        `None` de proposito quando nao ha caminho — acusaria os sete modelos de
        "sem dono" sem que nada estivesse errado. O que se quer verificar e o
        caminho de atributos com as relacoes preenchidas, que e o caso real de
        um `post_save`.
        """
        from django.apps import apps

        do_date = date(2026, 1, 15)
        fabrica = {
            "app.Propriedade": lambda: Propriedade.objects.create(
                user=self.user, nome="Fazenda 2", area_total=10
            ),
            "app.LancamentoFinanceiro": lambda: LancamentoFinanceiro.objects.create(
                propriedade=self.prop,
                descricao="X",
                valor=1,
                tipo="DESPESA",
                data=do_date,
            ),
            "app.Safra": lambda: Safra.objects.create(
                propriedade=self.prop,
                ano=2026,
                area_plantada=10,
                cultura=self.cultura,
            ),
            "app.Talhao": lambda: Talhao.objects.create(
                propriedade=self.prop, nome="Talhao A", area_hectare=1
            ),
            "app.Maquinario": lambda: Maquinario.objects.create(
                propriedade=self.prop, nome="Trator", tipo="TRATOR"
            ),
            "app.Funcionario": lambda: Funcionario.objects.create(
                propriedade=self.prop,
                nome="Joao",
                cargo="OPERADOR",
                salario=1000,
                data_admissao=date(2026, 1, 1),
            ),
            "app.Animal": lambda: Animal.objects.create(
                propriedade=self.prop, especie="BOVINOS", quantidade=10
            ),
        }

        for label in MODELOS_DO_PAINEL:
            with self.subTest(modelo=label):
                constroi = fabrica.get(label)
                if constroi is None:
                    # Um modelo novo na lista sem fabrica aqui: o teste nao
                    # valida o caminho, mas nao inventa um resultado. Falha
                    # para o proximo que acrescentar um modelo ter de
                    # acrescentar a fabrica, e nao descobrir a lacuna em
                    # producao.
                    self.fail(
                        f"{label} esta em MODELOS_DO_PAINEL mas nao tem fabrica "
                        "neste teste. Acrescenta a fabrica em `fabrica` para "
                        "que o caminho ate o dono continue verificado."
                    )

                inst = constroi()
                dono = _user_de(inst)
                self.assertIsNotNone(
                    dono,
                    f"{label} nao tem caminho resolvivel ate Propriedade.user: "
                    "a invalidacao vai ser no-op silencioso para este modelo",
                )
                self.assertEqual(
                    dono,
                    self.user.id,
                    f"{label} resolveu para o dono errado",
                )
                self.assertTrue(
                    apps.get_model(label).objects.filter(pk=inst.pk).exists(),
                    f"a fabrica de {label} nao gravou o registo",
                )

    def test_escrita_com_dono_apaga_todas_as_portas(self):
        """O contrato observavel: guardar um dado do painel limpa o cache."""
        chaves = list(_chaves_do_usuario(self.user.id))
        self.assertTrue(chaves)
        for c in chaves:
            cache.set(c, {"velho": True}, 30)

        # `post_save` dispara via sinal; o signal handler esta ligado em
        # AppConfig.ready().
        self.prop.nome = "Fazenda Renomeada"
        self.prop.save()

        vivos = [c for c in chaves if cache.get(c) is not None]
        self.assertEqual(vivos, [], f"cache sobreviveu a post_save: {vivos}")


class FormatoDasChavesTest(TestCase):
    """As chaves tem de bater certo com as que as views escrevem.

    `dashboard_data` grava `dash:<uid>`; `widget_data` grava
    `widget_data:<uid>:<0|1>`. Se uma view mudar o formato e a invalidacao
    nao for actualizada, volta o BUG-4.
    """

    def test_prefixos_correspondem_a_portas_reais(self):
        self.assertIn("dash", PREFIXOS_DO_PAINEL)
        self.assertIn("widget_data", PREFIXOS_DO_PAINEL)

    def test_formato_dash(self):
        chaves = list(_chaves_do_usuario(42))
        self.assertIn("dash:42", chaves)

    def test_formato_widget_data_com_variante(self):
        chaves = list(_chaves_do_usuario(42))
        self.assertIn("widget_data:42:0", chaves)
        self.assertIn("widget_data:42:1", chaves)

    def test_toda_chave_tem_o_uid_dentro(self):
        """Uma chave sem o uid apaga o cache de ninguem ou de toda a gente."""
        for c in _chaves_do_usuario(42):
            self.assertIn("42", c)

    def test_view_usa_o_formato_que_a_invalidacao_apaga(self):
        """Ligar o formato real da view ao formato gerado aqui.

        Nao e analise de AST: e uma substring sobre o fonte da view, que
        apanha a view a mudar o prefixo e o `PREFIXOS_DO_PAINEL` a ficar para
        tras — que e o BUG-4 repetido noutra forma.
        """
        import inspect

        from app.api.views import user as user_views

        fonte = inspect.getsource(user_views)
        for prefixo in PREFIXOS_DO_PAINEL:
            with self.subTest(prefixo=prefixo):
                self.assertIn(
                    prefixo,
                    fonte,
                    f"a view nao usa mais o prefixo {prefixo!r}: ou a porta "
                    "morreu (tire de PREFIXOS_DO_PAINEL) ou a invalidacao "
                    "precisa de a incluir",
                )
