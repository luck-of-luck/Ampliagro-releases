"""O diagnóstico de dados tem de VER, e nunca de MEXER.

O QUE ESTE COMANDO É
====================
`checar_drift` aponta uma safra impossível e pára. Este faz as perguntas que
ficam de fora: soma dos talhões contra a área declarada, safras sem
contra-o-que-conferir, datas ao contrário, lançamentos cujo tipo não bate com
a categoria.

A REGRA QUE NÃO SE NEGOCIA
==========================
Só lê. Um comando que apaga uma safra para "resolver" um alerta é o pior
defeito possível aqui: ninguém sabe o valor certo do cadastro, e um número
inventado para tapar outro é uma segunda mentira — desta vez escondida, e sem
aviso para ninguém desconfiar.

Por isso estes testes verificam DUAS coisas, e as duas importam:
1. o comando acha o que está errado;
2. o comando não altera absolutamente nada.

O QUE ESTE TESTE TRAVA
======================
1. A safra de 45.000 ha num talhão de 15 ha é apontada.
2. A soma dos talhões contra a área declarada é apontada.
3. A despesa de folha registada como receita é apontada.
4. Uma data de colheita antes do plantio é apontada.
5. A SAFRA SOBREVIVE ao comando — e o talhão, e o lançamento. Se o comando
   "limpasse" algo, este teste falhava.
6. Nenhum registo muda de valor.
"""

from datetime import date
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from app.models import (
    Cultura,
    LancamentoFinanceiro,
    Propriedade,
    Safra,
    Talhao,
)

User = get_user_model()


class DiagnosticoDeDados(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("diag_t", "diag_t@t.com", "x")
        self.prop = Propriedade.objects.create(
            user=self.user,
            nome="Fazenda do Diagnóstico",
            cidade="Muzambinho",
            uf="MG",
            area_total=Decimal("1000.00"),
        )
        self.soja = Cultura.objects.create(nome="Soja")
        self.milho = Cultura.objects.create(nome="Milho")

    def _rodar(self):
        out = StringIO()
        call_command("diagnostico_dados", stdout=out)
        return out.getvalue()

    def _folha_como_receita_legado(self, **extra):
        """Grava folha-como-receita do jeito que o dado ANTIGO chegou ao banco.

        `LancamentoFinanceiro.clean()` recusa `tipo=RECEITA` com
        `categoria=FOLHA` — folha e' despesa, e a gravacao nova nao passa. E
        exatamente por isso que o `diagnostico_dados` ainda tem trabalho: o
        dado invalido nao nasce mais, mas ja esta em bases antigas e em
        importacoes feitas antes da regra.

        Para os testes do diagnostico, entao, o dado invalido tem de entrar por
        um caminho que NAO passa pela trava de escrita — `QuerySet.update()`,
        que nao dispara sinal nem `save()`. E' o que reproduz fielmente a
        situacao que o comando existe para encontrar.
        """
        lanc = LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            data=date(2026, 9, 12),
            tipo="DESPESA",
            categoria="FOLHA",
            valor=Decimal("100.00"),
            descricao="pagamento dos funcionarios",
            **extra,
        )
        LancamentoFinanceiro.objects.filter(pk=lanc.pk).update(
            tipo="RECEITA", categoria="FOLHA"
        )
        lanc.refresh_from_db()
        self.assertEqual(lanc.tipo, "RECEITA", msg="o dado legado nao entrou")
        return lanc

    # ───────────────────────────────────────────────────────────────────
    # 1. Achar o que está errado
    # ───────────────────────────────────────────────────────────────────
    def test_aponta_a_safra_maior_que_o_talhao(self):
        """O caso real: 45.000 ha num talhão de 15 ha."""
        talhao = Talhao.objects.create(
            propriedade=self.prop, nome="Pequeno", area_hectare=Decimal("15.00")
        )
        Safra.objects.create(
            propriedade=self.prop,
            cultura=self.soja,
            ano=2026,
            area_plantada=Decimal("45000.00"),
            talhao=talhao,
        )

        saida = self._rodar()

        self.assertIn("SAFRA MAIOR QUE O TALHÃO", saida)
        self.assertIn("45,000.00", saida)
        self.assertIn("3,000x", saida, "a razão não foi dita — quem lê não vê a escala")

    def test_aponta_a_soma_dos_talhoes_acima_da_propriedade(self):
        """18 talhões a somar 3.047 ha numa propriedade declarada com 1.240."""
        for i in range(6):
            Talhao.objects.create(
                propriedade=self.prop,
                nome=f"T{i}",
                area_hectare=Decimal("200.00"),  # 1.200 no total
            )

        saida = self._rodar()
        self.assertIn("TALHÕES SOMAM MAIS QUE A PROPRIEDADE", saida)
        self.assertIn("1,000.00", saida)  # a área declarada
        self.assertIn("1,200.00", saida)  # a soma dos talhões

    def test_aponta_folha_registada_como_receita(self):
        """Folha é despesa. Registada como receita, o lucro é falso."""
        self._folha_como_receita_legado()

        saida = self._rodar()
        self.assertIn("LANÇAMENTO FINANCEIRO IMPOSSÍVEL", saida)
        self.assertIn("RECEITA mas categoria=FOLHA", saida)

    def test_aponta_colheita_antes_do_plantio(self):
        Safra.objects.create(
            propriedade=self.prop,
            cultura=self.soja,
            ano=2026,
            area_plantada=Decimal("100.00"),
            data_plantio=date(2026, 3, 1),
            data_colheita=date(2026, 2, 1),
        )

        saida = self._rodar()
        self.assertIn("DATAS QUE NÃO FAZEM SENTIDO", saida)
        self.assertIn("ANTES do plantio", saida)

    def test_aponta_safra_com_ano_no_futuro(self):
        Safra.objects.create(
            propriedade=self.prop,
            cultura=self.soja,
            ano=date.today().year + 3,
            area_plantada=Decimal("100.00"),
        )

        saida = self._rodar()
        self.assertIn("ANO NO FUTURO", saida)

    def test_um_banco_limpo_diz_que_nao_ha_achado(self):
        """Um diagnóstico que acusa sempre treina o olho a não o ler.

        Este é o teste que impede o comando de virar alarme de rotina. Com
        dados coerentes, ele tem de dizer que não achou nada.

        "Coerente" aqui quer dizer TUDO ligado: a safra tem o seu talhão, a
        área cabe na propriedade, a soma dos talhões cabe na área declarada,
        as datas fazem sentido, o lançamento é de despesa de insumo. Uma
        safra sem talhão é um achado legítimo (§4) — o diagnóstico tem razão
        em apontá-la, e um teste que montasse o "caso limpo" com uma dessas
        sem querer estaria a exigir que o comando calasse a boca.
        """
        talhao = Talhao.objects.create(
            propriedade=self.prop, nome="Certo", area_hectare=Decimal("200.00")
        )
        Safra.objects.create(
            propriedade=self.prop,
            cultura=self.soja,
            ano=2026,
            area_plantada=Decimal("100.00"),
            talhao=talhao,
            data_plantio=date(2026, 3, 1),
            data_colheita=date(2026, 6, 1),
        )
        LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            data=date(2026, 3, 1),
            tipo="DESPESA",
            categoria="INSUMO",
            valor=Decimal("1000.00"),
        )

        saida = self._rodar()

        self.assertIn("Nenhum achado", saida)
        for categoria in ("[ÁREA]", "[FINANCEIRO]", "[DATA]", "[ANO]", "[CONFERÊNCIA]"):
            self.assertNotIn(
                categoria, saida, f"houve um {categoria} num banco coerente"
            )

    def test_a_conta_no_rodape_diz_que_nada_e_corrigido(self):
        """O rodapé tem de dizer que é um relatório, não uma correcção.

        Sem esta frase, alguém lê "3 achados" e vai à assume que o comando
        já os resolveu. Em dado de cadastro, quem sabe o valor certo é quem
        conhece a fazenda.

        A frase aparece no caso em que HÁ achados. Num banco limpo o rodapé
        diz "Nenhum achado", e a mesma promessa — de que nada foi tocado —
        está no cabeçalho, que diz "(leitura, não altera nada)".
        """
        talhao = Talhao.objects.create(
            propriedade=self.prop, nome="Pequeno", area_hectare=Decimal("15.00")
        )
        Safra.objects.create(
            propriedade=self.prop,
            cultura=self.soja,
            ano=2026,
            area_plantada=Decimal("45000.00"),
            talhao=talhao,
        )

        saida = self._rodar()

        self.assertIn("Nenhum é corrigido aqui", saida)
        # E a promessa de leitura está no cabeçalho, para quem lê só o topo.
        self.assertIn("leitura, não altera nada", saida)

    # ───────────────────────────────────────────────────────────────────
    # 2. NÃO MEXER — a parte que importa
    # ───────────────────────────────────────────────────────────────────
    def test_o_comando_nao_apaga_nem_altera_nada(self):
        """A propriedade mais importante deste ficheiro.

        O comando produz um relatório. Se um dia alguém lhe acrescentar
        "e já agora corrige o que dá para corrigir", o número pode estar
        certo e o DADO errado: ninguém sabe a área verdadeira de uma safra,
        e um valor inventado para tapar outro é uma segunda mentira — sem
        nenhum sinal de que foi substituído.

        Por isso o teste conta ANTES e DEPOIS, e compara.
        """
        talhao = Talhao.objects.create(
            propriedade=self.prop, nome="Pequeno", area_hectare=Decimal("15.00")
        )
        safra = Safra.objects.create(
            propriedade=self.prop,
            cultura=self.soja,
            ano=2026,
            area_plantada=Decimal("45000.00"),
            talhao=talhao,
        )
        lancamento = self._folha_como_receita_legado()
        # Um talhao grande, para que a propriedade tambem apanhe no
        # "talhoes somam mais que a propriedade" e o teste tenha mais do que
        # um tipo de achado para comparar.
        Talhao.objects.create(
            propriedade=self.prop, nome="Outro", area_hectare=Decimal("500.00")
        )

        antes = {
            "safras": Safra.objects.count(),
            "talhoes": Talhao.objects.count(),
            "lancamentos": LancamentoFinanceiro.objects.count(),
            "area_safra": float(Safra.objects.get(id=safra.id).area_plantada),
            "area_talhao": float(Talhao.objects.get(id=talhao.id).area_hectare),
            "area_total_prop": float(
                Propriedade.objects.get(id=self.prop.id).area_total
            ),
            "valor_lanc": float(
                LancamentoFinanceiro.objects.get(id=lancamento.id).valor
            ),
        }

        self._rodar()

        depois = {
            "safras": Safra.objects.count(),
            "talhoes": Talhao.objects.count(),
            "lancamentos": LancamentoFinanceiro.objects.count(),
            "area_safra": float(Safra.objects.get(id=safra.id).area_plantada),
            "area_talhao": float(Talhao.objects.get(id=talhao.id).area_hectare),
            "area_total_prop": float(
                Propriedade.objects.get(id=self.prop.id).area_total
            ),
            "valor_lanc": float(
                LancamentoFinanceiro.objects.get(id=lancamento.id).valor
            ),
        }

        self.assertEqual(
            antes,
            depois,
            "o diagnóstico alterou dados. Este comando SÓ LÊ: corrigir um "
            "cadastro sem saber o valor certo é fabricar um segundo erro.",
        )

    def test_o_comando_nao_falha_com_banco_vazio(self):
        """Um diagnóstico que rebenta em dados limpos não é um diagnóstico."""
        for model in (Safra, Talhao, LancamentoFinanceiro):
            self.assertEqual(model.objects.count(), 0)

        saida = self._rodar()

        self.assertIn("DIAGNÓSTICO DE DADOS", saida)
        self.assertIn("Nenhum achado", saida)

    def test_o_comando_lida_com_o_ano_futuro_sem_quebrar(self):
        """O `exclude(ano__gt=...)` de um filtro por data tem de ser seguro."""
        for ano in (date.today().year - 5, date.today().year, date.today().year + 5):
            Safra.objects.create(
                propriedade=self.prop,
                cultura=self.soja,
                ano=ano,
                area_plantada=Decimal("10.00"),
            )

        saida = self._rodar()
        self.assertIn("ANO NO FUTURO", saida)
