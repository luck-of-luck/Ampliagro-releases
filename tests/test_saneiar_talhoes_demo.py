"""O saneamento da demo tem de ser reversível, previewável e conservador.

O QUE ESTE COMANDO FAZ
======================
A "Fazenda Modelo" foi criada por `seed_mvp_demo.py` para uma apresentação, e
o seed define QUATRO talhões que somam 1.240 ha — exactamente o `area_total`.
Depois, o banco foi acumulando: testes com `unittest.TestCase` em vez de
`django.test.TestCase` escrevem no `db.sqlite3` de desenvolvimento sem fazer
rollback, e o mesmo acontece com experiments manuais. O resultado, verificado
nesta base, foi 18 talhões a somar 3.047 ha numa propriedade declarada com
1.240 ha.

A regra que este comando herda, e que estes testes vigiam
========================================================
1. **Dry-run por omissão.** Sem `--apagar`, não acontece nada. O relatório é
   o produto; apagar é uma decisão separada.
2. **O backup vem antes do DELETE.** Um comando que apaga e depois pensa em
   fazer backup é um comando que já perdeu.
3. **As safras sobrevivem por omissão.** `Safra.talhao` é `SET_NULL`: apagar o
   talhão deixa a safra de pé, e ela continua a contar 45.000 ha. Apagar o
   talhão sem dizer isso é o pior resultado possível — o utilizador vê o
   painel igual e conclui que o problema morreu.
4. **Só toca na propriedade do seed.** Noutra fazenda, um talhão chamado
   "Guia" pode ser real.
5. **A lista do seed é a definição.** A constante é importada do gerador, não
   reescrita — para que as duas não possam divergir.
"""

from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from app.management.commands.saneear_talhoes_demo import NOME_DA_DEMO, NOMES_DA_DEMO
from app.models import Cultura, Propriedade, Safra, Talhao


class SaneamentoDaDemo(TestCase):
    def setUp(self):
        # `django.contrib.auth.models.User` e não `get_user_model()`: o
        # `app.models` exporta um `User` que NÃO é o modelo de auth (é o
        # serializer, ou um alias), e `create_user` só existe no segundo.
        self.user = User.objects.create_user("saneia_t", "saneia_t@t.com", "x")
        self.prop = Propriedade.objects.create(
            user=self.user,
            nome=NOME_DA_DEMO,
            cidade="Primavera do Leste",
            uf="MT",
            area_total=Decimal("1240.00"),
        )
        self.cultura = Cultura.objects.create(nome="Soja")

        # Os quatro talhões do seed.
        for nome, area in (
            ("Talhão A - Soja", "420.00"),
            ("Talhão B - Milho Safrinha", "380.00"),
            ("Talhão C - Pastagem", "280.00"),
            ("Reserva Legal", "160.00"),
        ):
            Talhao.objects.create(
                propriedade=self.prop, nome=nome, area_hectare=Decimal(area)
            )

        # Lixo: um talhão de teste com uma safra impossível em cima.
        self.lixo = Talhao.objects.create(
            propriedade=self.prop, nome="Alpiste 001", area_hectare=Decimal("15.00")
        )
        self.safra_impossivel = Safra.objects.create(
            propriedade=self.prop,
            cultura=self.cultura,
            ano=2026,
            area_plantada=Decimal("45000.00"),
            talhao=self.lixo,
        )

    def _rodar(self, **kwargs):
        out = StringIO()
        call_command("saneear_talhoes_demo", "--sim", stdout=out, **kwargs)
        return out.getvalue()

    # ───────────────────────────────────────────────────────────────────
    # 1. Dry-run: o produto é o relatório, e nada muda
    # ───────────────────────────────────────────────────────────────────
    def test_sem_apagar_nao_muda_nada(self):
        """A propriedade mais importante: o relatório não toca em nada."""
        antes = {
            "talhoes": Talhao.objects.count(),
            "safras": Safra.objects.count(),
            "lixo_vivo": Talhao.objects.filter(id=self.lixo.id).exists(),
            "area_safra": float(
                Safra.objects.get(id=self.safra_impossivel.id).area_plantada
            ),
        }

        saida = self._rodar()

        depois = {
            "talhoes": Talhao.objects.count(),
            "safras": Safra.objects.count(),
            "lixo_vivo": Talhao.objects.filter(id=self.lixo.id).exists(),
            "area_safra": float(
                Safra.objects.get(id=self.safra_impossivel.id).area_plantada
            ),
        }
        self.assertEqual(antes, depois, "o dry-run alterou dados")
        self.assertIn("dry-run: nada foi apagado", saida)

    def test_o_relatorio_diz_o_que_esta_a_errado_com_numeros(self):
        saida = self._rodar()

        # A soma actual contra a área declarada — a conta que está errada.
        self.assertIn("1,255.00", saida)  # 1240 + 15
        self.assertIn("1,240.00", saida)  # a área do seed
        self.assertIn("15.00", saida)  # o talhão a remover
        # E a promessa de que depois bate.
        self.assertIn("bate com a área declarada", saida)

    def test_o_relatorio_aponta_a_safra_impossivel(self):
        """A safra de 45.000 ha é a razão do comando existir.

        Se o relatório não a nomear, quem lê apaga o talhão, vê o painel
        igual, e conclui que o problema morreu. Ele não morreu.
        """
        saida = self._rodar()

        self.assertIn("45,000.00", saida)
        self.assertIn("SET_NULL", saida)
        # O aviso está partido em linhas (é `self.style.WARNING` com
        # quebras para caber no terminal), por isso a comparação junta os
        # espaços: o que interessa é que a frase exista, não como está
        # quebrada.
        sem_espacos = " ".join(saida.split())
        self.assertIn(
            "continuam a contar área",
            sem_espacos,
            "o relatório não avisa que as safras sobrevivem. Apagar o talhão "
            "sem isto é tirar a contraprova e chamar-lhe limpeza.",
        )

    def test_o_relatorio_nao_promete_mais_do_que_que_entra_no_ano(self):
        """O relatório tem de dizer o que o `--apagar` faria, não o que resolve.

        O ponto é este: apagar os talhões tira a contraprova, não a safra. A
        diferença é entre "limpo" e "não consigo mais verificar", e só a
        segunda é verdade.
        """
        saida = self._rodar()
        self.assertIn("só tira a contraprova", saida)

    # ───────────────────────────────────────────────────────────────────
    # 2. Com --apagar, e só com --apagar
    # ───────────────────────────────────────────────────────────────────
    def test_com_apagar_sai_a_area_pela_metade(self):
        """O talhão vai; a safra fica; a área dos talhões bate com a declarada."""
        self._rodar(apagar=True)

        self.assertFalse(
            Talhao.objects.filter(id=self.lixo.id).exists(),
            "o talhão de teste não foi removido com --apagar",
        )
        # A area agora: só os quatro do seed.
        self.assertEqual(Talhao.objects.filter(propriedade=self.prop).count(), 4)

    def test_apagar_sem_tambem_safras_deixa_a_safra_de_pe(self):
        """O aviso do dry-run tem de ser verdade no momento do apagar.

        `Safra.talhao` é `SET_NULL`, e é isso que acontece: a safra sobrevive
        sem talhão e continua a contar 45.000 ha. Se este teste falhar, o
        relatório estava a mentir — e o relatório é o que autoriza a apagar.
        """
        self._rodar(apagar=True)

        s = Safra.objects.get(id=self.safra_impossivel.id)
        self.assertIsNone(
            s.talhao_id,
            "a safra não ficou órfã: ou o talhão não foi apagado, ou o "
            "SET_NULL não se aplica aqui. A previsão do relatório está errada.",
        )
        self.assertEqual(
            float(s.area_plantada), 45000.0, "a área da safra mudou sem ninguém pedir"
        )

    def test_apagar_com_tambem_safras_apaga_as_duas(self):
        self._rodar(apagar=True, tambem_safras=True)

        self.assertFalse(Talhao.objects.filter(id=self.lixo.id).exists())
        self.assertFalse(
            Safra.objects.filter(id=self.safra_impossivel.id).exists(),
            "--tambem-safras não apagou a safra.",
        )

    def test_as_safras_do_seed_nunca_sao_apagadas(self):
        """A safra de 2024 está no Talhão A, que é do seed.

        É a safra que a demonstração mostra — a que o painel de
        apresentação precisa de ver. Uma regra de "apagar safras" que a
        apanhasse seria um comando a destruir a própria demo.
        """
        talhao_a = Talhao.objects.get(propriedade=self.prop, nome="Talhão A - Soja")
        safra_do_seed = Safra.objects.create(
            propriedade=self.prop,
            cultura=self.cultura,
            ano=2024,
            area_plantada=Decimal("420.00"),
            talhao=talhao_a,
        )

        self._rodar(apagar=True, tambem_safras=True)

        self.assertTrue(
            Safra.objects.filter(id=safra_do_seed.id).exists(),
            "a safra do talhão do seed foi apagada. A demo perdeu o que mostrava.",
        )

    # ───────────────────────────────────────────────────────────────────
    # 3. Escopo: só a propriedade do seed
    # ───────────────────────────────────────────────────────────────────
    def test_nao_toca_numa_fazenda_que_nao_e_a_demo(self):
        """Noutra propriedade, um talhão chamado 'Guia' pode ser real.

        Este é o teste que impede o comando de ser um destrói-génio: a
        regra tem de estar presa ao nome da propriedade do seed, não a um
        padrão de nome de talhão.
        """
        outra = Propriedade.objects.create(
            user=self.user,
            nome="Fazenda da Ana",
            cidade="Muzambinho",
            uf="MG",
            area_total=Decimal("500.00"),
        )
        talhao_real = Talhao.objects.create(
            propriedade=outra, nome="Talhão Arroz Guia", area_hectare=Decimal("120.00")
        )

        saida = self._rodar()

        # A demo desta base tem lixo, o relatório tem de aparecer. O que
        # interesta é que a fazenda da Ana NÃO entrou nele.
        self.assertIn("1 talhão(ões) que NÃO são do seed", saida)
        self.assertNotIn(
            "Fazenda da Ana",
            saida,
            "o relatório falou da propriedade errada. O alvo tem de ser a "
            "propriedade do seed, não um talhão cujo nome pareça de teste.",
        )
        self.assertTrue(
            Talhao.objects.filter(id=talhao_real.id).exists(),
            "o comando apagou um talhão de outra fazenda. O nome 'Guia' não "
            "é o que define a demo — a propriedade é.",
        )

    def test_avisa_quando_a_demo_nao_existe(self):
        Propriedade.objects.all().delete()
        saida = self._rodar()
        self.assertIn("só age sobre a demonstração", saida)

    def test_avisa_quando_a_area_do_seed_nao_bate_com_a_declarada(self):
        """O comando não pode prometer o que não pode cumprir.

        Se os talhões do seed não somarem a área declarada, apagar o lixo
        não resolve a divergência — e dizer "depois bate" seria mentir. O
        comando tem de dizer que a área declarada também precisa de revisão.
        """
        self.prop.area_total = Decimal("999.00")
        self.prop.save(update_fields=["area_total"])

        saida = self._rodar()

        self.assertNotIn("bate com a área declarada", saida)
        self.assertIn("a área declarada", saida)
        self.assertIn("999.00", saida)

    def test_demo_limpa_diz_que_esta_limpa(self):
        Talhao.objects.filter(id=self.lixo.id).delete()
        Safra.objects.filter(id=self.safra_impossivel.id).delete()
        saida = self._rodar()
        self.assertIn("está limpa", saida)

    # ───────────────────────────────────────────────────────────────────
    # 4. A constante é a do gerador
    # ───────────────────────────────────────────────────────────────────
    def test_a_lista_de_talhoes_vem_do_seed_e_nao_e_reescrita(self):
        """A lista é importada do gerador, não duplicada aqui.

        Se alguém acrescentar um talhão ao `seed_mvp_demo.py` e não a esta
        lista, o comando passa a considerar legítimo o talhão novo — ou, ao
        contrário, a apagar o que o seed criou. As duas são silenciosas.
        """
        from app.management.commands.seed_mvp_demo import TALHOES_MODELO

        self.assertEqual(
            NOMES_DA_DEMO,
            {t["nome"] for t in TALHOES_MODELO},
            "a lista de talhões da demo divergiu do gerador. Uma divergência "
            "aqui significa apagar o que a demo cria, ou proteger lixo.",
        )
