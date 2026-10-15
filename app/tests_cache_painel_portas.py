"""O cache do `widget_data` tambem tem de ser invalidado quando o produtor escreve.

`cache_painel.py` nasceu para matar uma mentira concreta: o produtor lançava
uma despesa e voltava ao painel via 30 segundos com o número antigo. A correção
foi um sinal de `post_save`/`post_delete` que apaga `dash:<user_id>`.

Mas existe um SEGUNDO endpoint com cache: `widget_data`
(`app/api/views/user.py:503`), gravado em `widget_data:<user_id>:<0|1>`.

O sinal apagava `dash:<uid>`. Chave diferente — o payload do `widget_data`
continuava a ser servido do cache depois de uma escrita, exatamente o mesmo
sintoma que o módulo existe para impedir. E `widget_data` é o endpoint que
alimenta os widgets do dashboard, ou seja, é exatamente onde o produtor
repara no número velho.

O invariant deste ficheiro: toda chave `dash*` de um utilizador tem de
desaparecer quando um registo do painel é escrito. Um teste por chave, para
que uma terceira porta com cache não repita o mesmo erro.
"""

from __future__ import annotations

from datetime import date

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from app.models import LancamentoFinanceiro, Propriedade


def _despesa(prop, descricao="Adubo", valor=100):
    return LancamentoFinanceiro.objects.create(
        propriedade=prop,
        descricao=descricao,
        valor=valor,
        tipo="DESPESA",
        data=date(2026, 1, 15),
    )


class InvalidaTodasAsPortasDoCacheTest(TestCase):
    """Cada porta com cache tem de morrer na mesma escrita."""

    def setUp(self):
        self.user = User.objects.create_user("produtor", password="x")
        self.prop = Propriedade.objects.create(
            user=self.user, nome="Fazenda Boa", area_total=100
        )
        # As duas portas que `dashboard_data`/`widget_data` abrem.
        self.chaves = [
            f"dash:{self.user.id}",
            f"widget_data:{self.user.id}:0",
            f"widget_data:{self.user.id}:1",
        ]

    def _cachear_tudo(self):
        for c in self.chaves:
            cache.set(c, {"ok": True, "numero": 1}, 30)

    def test_escrita_apaga_TODAS_as_chaves_do_usuario(self):
        """Uma despesas nao pode deixar nenhum `dash*` vivo."""
        self._cachear_tudo()

        _despesa(self.prop)

        vivos = [c for c in self.chaves if cache.get(c) is not None]
        self.assertEqual(
            vivos,
            [],
            f"cache sobreviveu a uma escrita do painel: {vivos}",
        )

    def test_outro_usuario_nao_sofre_com_a_escrita(self):
        """Invalidar o dono do registo não pode limpar o cache alheio.

        O `dash:<uid>` é por utilizador: apagar o cache do vizinho seria
        só um desperdício, mas errar o `uid` e apagar o errado é o mesmo
        bug do dashboard mentiroso, ao contrário.
        """
        outro = User.objects.create_user("vizinho", password="x")
        vizinho_prop = Propriedade.objects.create(
            user=outro, nome="Fazenda do Vizinho", area_total=50
        )
        cache.set(f"dash:{outro.id}", {"ok": True}, 30)

        _despesa(self.prop, descricao="X", valor=1)

        self.assertIsNotNone(
            cache.get(f"dash:{outro.id}"),
            "a escrita de um produtor limpou o cache de outro",
        )
        self.assertTrue(Propriedade.objects.filter(pk=vizinho_prop.pk).exists())

    def test_propriedade_criada_depois_tambem_invalida(self):
        """Criar a propriedade invalida um `dash:` que já existia (ex.: de
        um payload `{sem_propriedade: true}`)."""
        cache.set(f"dash:{self.user.id}", {"sem_propriedade": True}, 30)

        Propriedade.objects.create(
            user=self.user, nome="Segunda Fazenda", area_total=10
        )

        self.assertIsNone(
            cache.get(f"dash:{self.user.id}"),
            "criar propriedade nao limpou o painel que dizia 'sem_propriedade'",
        )
