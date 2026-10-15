"""As FONTES — o servidor escreve os números, e o tenancy não se negocia.

O BURACO QUE ESTES TESTES FECHAM
================================
A primeira versão do Chamado deixava a IA escrever as *linhas* dos blocos de
dado, e marcava o bloco `medido` por ter linhas. As linhas vinham de um modelo
de 1,7B: não havia consulta nenhuma por trás delas, e o número aparecia com o
carimbo que o produtor usa para decidir uma safra.

`test_numeros_da_ia_sao_descartados` é o teste desse buraco. Os outros existem
porque uma fonte que devolve o número do vizinho é um vazamento entre contas —
e o sinal seria o produtor A ver uma despesa que não é dele, sem erro nenhum.
"""

import json

from django.contrib.auth.models import User
from django.test import TestCase

from app.ia import sandbox
from app.models import ChamadoAmplia, LancamentoFinanceiro, Propriedade

DIA = "2026-03-12"


def _rotulo(valores, inicio):
    """O valor da linha cujo rotulo COMEÇA por `inicio`, com ou sem acento.

    Comparar "saídas" e "saidas" é uma AssertError que não tem nada a ver com o
    que o teste quer provar — e um teste que falha por um acento é um teste que
    a proxima pessoa apaga em vez de corrigir.
    """
    for rotulo, valor in valores.items():
        if rotulo.lower().startswith(inicio.lower()):
            return valor
    raise AssertionError(
        f"nenhuma linha começa por {inicio!r}; existem: {sorted(valores)}"
    )


class FonteBase(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user("ana", password="x")
        self.bruno = User.objects.create_user("bruno", password="x")

        self.pa = Propriedade.objects.create(
            user=self.ana, nome="Sitio da Ana", area_total="100.00"
        )
        self.pb = Propriedade.objects.create(
            user=self.bruno, nome="Sitio do Bruno", area_total="50.00"
        )

        # A despesa da Ana. `1234.56` e `900.00` sao os numeros que os testes vao
        # procurar — e vao procurar a string INTEIRA, para nao passarem por um
        # `1` ou um `9` que apareca numa data.
        self._lancamento(self.pa, "DESPESA", "Adubo", "1234.56")
        self._lancamento(self.pa, "DESPESA", "Semente", "900.00")
        self._lancamento(self.pa, "RECEITA", "Venda", "5000.00")

        # A do Bruno. NUNCA pode aparecer para a Ana.
        self._lancamento(self.pb, "DESPESA", "Adubo", "999999.00")

    def _lancamento(self, prop, tipo, categoria, valor):
        return LancamentoFinanceiro.objects.create(
            propriedade=prop,
            tipo=tipo,
            categoria=categoria,
            valor=valor,
            data=DIA,
        )

    def peca(self, user, blocos, **extra):
        r = sandbox.executar(
            user, "chamado_criar", {"blocos": blocos, "confirm": True, **extra}
        )
        self.assertTrue(r.get("ok"), r)
        return r["dados"]

    def bloco(self, dados, tipo):
        achado = [b for b in dados["blocos"] if b["tipo"] == tipo]
        self.assertTrue(achado, f"sem bloco {tipo}")
        return achado[0]


class DescartaNumerosDaIaTest(FonteBase):
    """O buraco. Sem fonte, o número da IA não entra no ecrã nem na base."""

    def test_numeros_da_ia_sao_descartados(self):
        d = self.peca(
            self.ana,
            [
                {
                    "tipo": "tabela",
                    "titulo": "Despesas",
                    "colunas": ["categoria", "valor"],
                    "linhas": [["Adubo", "1234.56"]],
                }
            ],
        )
        b = self.bloco(d, "tabela")
        self.assertEqual(b["fonte_dado"], "sem_dado")
        # DESCARTADAS, e não mostradas-com-carimbo. Um número inventado à vista
        # do produtor, mesmo marcado, é um número que ele vai ler.
        self.assertEqual(b["config"]["linhas"], [])
        # E o motivo diz o que fazer, não só o que está mal.
        self.assertIn("fonte", b["config"]["motivo"].lower())

    def test_o_produtor_e_informado_na_resposta(self):
        r = sandbox.executar(
            self.ana,
            "chamado_criar",
            {
                "blocos": [{"tipo": "tabela", "linhas": [["a", "1234.56"]]}],
                "confirm": True,
            },
        )
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(r["dados"]["numeros_descartados"], 1)
        self.assertIn("descartados", r["resposta"])

    def test_a_base_nao_guarda_linhas(self):
        # O que fica gravado e a RECEITA. Se um dia ficar a linha, o numero
        # inventado entra na base como se fosse medido — e nada mais avisa,
        # porque o bloco continua a desenhar bem.
        self.peca(self.ana, [{"tipo": "tabela", "linhas": [["a", "1234.56"]]}])
        peca = ChamadoAmplia.objects.do_produtore(self.ana).get()
        for b in peca.corpo:
            self.assertNotIn("linhas", b.get("config", {}))


class FonteCalculadaTest(FonteBase):
    """Com fonte, o numero vem do banco — e tem de bater certo."""

    def test_a_fonte_traz_as_despesas_do_banco(self):
        d = self.peca(
            self.ana,
            [
                {
                    "tipo": "tabela",
                    "titulo": "Despesas",
                    "fonte": "despesas-por-categoria",
                }
            ],
        )
        b = self.bloco(d, "tabela")
        self.assertEqual(b["fonte_dado"], "medido")
        self.assertEqual(b["config"]["fonte"], "despesas-por-categoria")
        linhas = b["config"]["linhas"]
        self.assertEqual(len(linhas), 2, linhas)
        celulas = {c for l in linhas for c in l}
        self.assertIn("1,234.56", celulas)
        self.assertIn("900.00", celulas)

    def test_a_ordena_e_da_maior_para_a_menor(self):
        d = self.peca(self.ana, [{"tipo": "tabela", "fonte": "despesas-por-categoria"}])
        linhas = self.bloco(d, "tabela")["config"]["linhas"]
        self.assertEqual(linhas[0][0], "Adubo")

    def test_o_saldo_soma_receitas_e_despesas(self):
        d = self.peca(self.ana, [{"tipo": "kpi", "fonte": "saldo"}])
        b = self.bloco(d, "kpi")
        self.assertEqual(b["fonte_dado"], "medido")
        valores = {l[0]: l[1] for l in b["config"]["linhas"]}
        self.assertEqual(_rotulo(valores, "entrada"), "5,000.00")
        self.assertEqual(_rotulo(valores, "sa"), "2,134.56")
        self.assertEqual(_rotulo(valores, "saldo"), "2,865.44")

    def test_receitas_despesas_por_mes(self):
        d = self.peca(self.ana, [{"tipo": "tabela", "fonte": "receitas-despesas"}])
        b = self.bloco(d, "tabela")
        self.assertEqual(b["fonte_dado"], "medido")
        linhas = b["config"]["linhas"]
        self.assertEqual(len(linhas), 1)
        self.assertEqual(linhas[0][0], "2026-03")

    def test_uma_fonte_desconhecida_desce_com_motivo(self):
        d = self.peca(self.ana, [{"tipo": "tabela", "fonte": "inventada-por-mim"}])
        b = self.bloco(d, "tabela")
        self.assertEqual(b["fonte_dado"], "sem_dado")
        self.assertEqual(b["config"]["linhas"], [])
        self.assertIn("desconhecida", b["config"]["motivo"])

    def test_uma_fonte_sem_registo_e_sem_dado_e_nao_zero(self):
        vazio = User.objects.create_user("vazio", password="x")
        d = self.peca(vazio, [{"tipo": "tabela", "fonte": "despesas-por-categoria"}])
        b = self.bloco(d, "tabela")
        self.assertEqual(b["fonte_dado"], "sem_dado")
        # "consultada e não há registo" e "a despesa foi zero" são coisas
        # diferentes, e é a diferença entre uma tela que ajuda e uma que mente.
        self.assertEqual(b["config"]["linhas"], [])
        self.assertIn("registo", b["config"]["motivo"])


class TenancyDasFontesTest(FonteBase):
    """Um número de outra conta é o pior bug que este sistema pode ter."""

    def test_a_ana_nao_ve_a_despesa_do_bruno(self):
        d = self.peca(self.ana, [{"tipo": "tabela", "fonte": "despesas-por-categoria"}])
        self.assertNotIn("999,999.00", json.dumps(d, ensure_ascii=False))

    def test_o_bruno_so_ve_a_dele(self):
        d = self.peca(
            self.bruno, [{"tipo": "tabela", "fonte": "despesas-por-categoria"}]
        )
        bruto = json.dumps(d, ensure_ascii=False)
        # O valor chega FORMATADO ("999,999.00"). Procurar o numero cru num
        # valor formatado e um teste que passa ou falha por razoes que nao tem
        # nada a ver com o tenancy.
        self.assertIn("999,999.00", bruto)
        self.assertNotIn("1,234.56", bruto)
        self.assertNotIn("5,000.00", bruto)

    def test_o_saldo_nao_mistura_as_contas(self):
        d = self.peca(self.bruno, [{"tipo": "kpi", "fonte": "saldo"}])
        valores = {l[0]: l[1] for l in self.bloco(d, "kpi")["config"]["linhas"]}
        # O Bruno so tem uma despesa e nenhuma receita.
        self.assertEqual(_rotulo(valores, "entrada"), "0.00")
        self.assertEqual(_rotulo(valores, "sa"), "999,999.00")


class ContagemDeDescartesTest(FonteBase):
    """Quantos numeros a IA escreveu e foram descartados — e a historia disso.

    Este numero vivia num sitio onde nao podia sobreviver. A peca guarda so a
    RECEITA: `_guarda` tira `linhas` antes de gravar, para a base nao ter
    numeros de um modelo. Mas a leitura conta os descartes por `len(linhas)` —
    e a essa altura `linhas` ja nao existe. O contador dava sempre zero, em
    qualquer peca, para sempre.

    Zero aqui nao e "nada foi descartado": e "ninguem contou". E o produtor lia
    isso como se fosse a primeira coisa, que e o pior dos dois casos: um
    contador que mente para zero e mais facil de acreditar do que um que esta
    em branco.
    """

    def test_a_contagem_sobrevive_a_reabertura_da_peca(self):
        d = self.peca(
            self.ana,
            [
                {
                    "tipo": "tabela",
                    "titulo": "Despesas escritas pela IA",
                    "colunas": ["categoria", "valor"],
                    "linhas": [["Adubo", "1.234,56"], ["Calcario", "99,00"]],
                }
            ],
        )
        self.assertEqual(
            d["numeros_descartados"],
            2,
            "duas linhas escritas pela IA, nenhuma com fonte: duas descartadas",
        )

    def test_a_leitura_nao_apaga_a_contagem(self):
        """A leitura e onde a contagem morria.

        `aplicar_fontes` e chamado com o corpo JA guardado, em que `linhas` nao
        existe. Se ele escrever `numeros_descartados = len(linhas)`, apaga o
        registo que a escrita deixou. Por isso so escreve quando contou mesmo.
        """
        peca = self.peca(
            self.ana,
            [{"tipo": "tabela", "linhas": [["Adubo", "1.234,56"]]}],
        )
        # Reaplicar e o mesmo que abrir a peca outra vez.
        from app.ia import chamado

        segunda = chamado.aplicar_fontes(self.ana, [dict(b) for b in peca["blocos"]])
        self.assertEqual(
            segunda[0].get("numeros_descartados"),
            1,
            "a segunda leitura nao pode perder a contagem da primeira",
        )
        self.assertIsNotNone(chamado.aplicar_fonte_dado(segunda))

    def test_uma_fonte_real_nao_conta_como_descarte(self):
        d = self.peca(
            self.ana,
            [{"tipo": "tabela", "fonte": "despesas-por-categoria"}],
        )
        self.assertEqual(
            d["numeros_descartados"],
            0,
            "com fonte do servidor, nada foi descartado",
        )

    def test_o_bloco_diz_o_motivo_do_descarte(self):
        d = self.peca(
            self.ana,
            [{"tipo": "tabela", "linhas": [["Adubo", "1.234,56"]]}],
        )
        bloco = d["blocos"][0]
        self.assertEqual(bloco["fonte_dado"], "sem_dado")
        self.assertIn("fonte", bloco["config"]["motivo"].lower())
        # `_config_sem_linhas` deixa a chave com lista VAZIA, e nao a remove. Nao e a
        # mesma coisa, e a distincao importa: uma chave `linhas: []` diz "aqui
        # havia um desenho sem numeros"; uma chave `linhas` com
        # [['Adubo', '1.234,56']] seria o numero do modelo a chegar ao
        # produtor. O que tem de ser verificado e que nao sobrou nada.
        self.assertEqual(bloco["config"].get("linhas"), [])


class TextoApoiadoTest(FonteBase):
    """O carimbo do texto tem de se apoiar nos numeros que FICARAM."""

    def test_um_texto_apoiado_numa_fonte_real_e_medido(self):
        d = self.peca(
            self.ana,
            [
                {"tipo": "tabela", "fonte": "despesas-por-categoria"},
                {"tipo": "texto", "texto": "O adubo custou 1.234,56."},
            ],
        )
        self.assertEqual(self.bloco(d, "texto")["fonte_dado"], "medido")

    def test_um_texto_que_cita_um_numero_que_nao_existe_nao_e_medido(self):
        # A tabela traz 1.234,56 e 900,00 do banco. O TEXTO inventou 77,77.
        # O validador tem de o apanhar: é a diferença entre "a peça está certa"
        # e "a peça parece certa".
        d = self.peca(
            self.ana,
            [
                {"tipo": "tabela", "fonte": "despesas-por-categoria"},
                {"tipo": "texto", "texto": "A semente custou 77,77."},
            ],
        )
        self.assertEqual(self.bloco(d, "texto")["fonte_dado"], "sem_dado")
        numeros = {a["numero"] for a in d["numeros_sem_apoio"]}
        self.assertIn("77,77", numeros)


class RegistoDasFontesTest(TestCase):
    """O catálogo é derivado, e uma fonte que a IA não conhece é inventada."""

    def test_toda_fonte_declara_as_colunas(self):
        from app.ia import chamado_fontes

        for nome, spec in chamado_fontes.FONTES.items():
            with self.subTest(fonte=nome):
                self.assertTrue(spec.get("descricao"), "sem descrição")
                self.assertTrue(spec.get("colunas"), "sem colunas")
                self.assertIn("calcular", spec)

    def test_calcular_nunca_levanta(self):
        from app.ia import chamado_fontes

        # Uma fonte que rebenta tem de devolver `ok: False` com o motivo, não
        # traceback — quem chama é um handler a meio de uma requisição.
        r = chamado_fontes.calcular(None, "saldo")
        self.assertTrue(r["ok"])

    def test_fonte_desconhecida_diz_que_existem_outras(self):
        from app.ia import chamado_fontes

        r = chamado_fontes.calcular(None, "nao-existe")
        self.assertFalse(r["ok"])
        # O motivo com a lista é o que faz um LLM de 1,7B parar e corrigir, em
        # vez de insistir com o mesmo nome.
        self.assertIn("fontes_conhecidas", r)
        self.assertTrue(r["fontes_conhecidas"])

    def test_a_referencia_tem_o_essencial(self):
        from app.ia import chamado_fontes

        ref = {f["id"]: f for f in chamado_fontes.referencia_fontes()}
        self.assertEqual(set(ref), set(chamado_fontes.FONTES))
        for f in ref.values():
            self.assertIn("descricao", f)
            self.assertIn("filtros", f)

    def test_toda_fonte_responde(self):
        """**Toda** a fonte, contra dados reais.

        Este é o teste que apanha um import em falta. A primeira versão tinha
        seis fontes e nenhuma testada em conjunto: `f_receitas_despesas`
        usava `Sum` sem o importar, o `except` de `calcular` engolia o
        `NameError`, e o bloco descia a `sem_dado` — que o painel lê como "não
        há registo". O produtor vê "não há lançamentos" e conclui que não
        lançou nada, quando o problema era um import.

        Com este teste, uma fonte que rebenta com dados na mesa é um teste
        VERMELHO no momento em que se escreve, e não um bloco vazio dias
        depois.
        """
        from app.ia import chamado_fontes
        from app.models import Cultura, LancamentoFinanceiro, Propriedade, Safra

        u = User.objects.create_user("todas", password="x")
        p = Propriedade.objects.create(user=u, nome="Sitio", area_total="10.00")
        # `Safra.cultura` e NOT NULL. Uma safra sem cultura e uma safra que
        # ninguém vai conseguir comparar com nenhuma outra.
        c = Cultura.objects.create(nome="Soja", grupo="graos")
        LancamentoFinanceiro.objects.create(
            propriedade=p, tipo="DESPESA", categoria="Adubo", valor="10.00", data=DIA
        )
        LancamentoFinanceiro.objects.create(
            propriedade=p, tipo="RECEITA", categoria="Venda", valor="99.00", data=DIA
        )
        Safra.objects.create(
            propriedade=p,
            cultura=c,
            ano=2026,
            producao_total="500",
            area_colhida="10",
            area_plantada="12",  # NOT NULL
        )

        for nome in sorted(chamado_fontes.FONTES):
            # EXTERNA (ex.: `chuva-semana`) responde de fetch, não de registo:
            # sem rede não há linhas, e linhas vazias aqui seriam o teste a
            # exigir internet — não a apanhar um import em falta, que é o que
            # este teste existe para fazer. A cobertura da externa com fetch
            # mockado vive em `tests/test_chuva_serie_preset.py`.
            if chamado_fontes.FONTES[nome].get("externa"):
                continue
            with self.subTest(fonte=nome):
                r = chamado_fontes.calcular(u, nome)
                # `falhou` distingue "partiu" de "não há registo". Uma fonte que
                # responde com `falhou` e linhas vazias é um bug com a
                # roupa de um dado ausente.
                self.assertNotEqual(
                    r.get("falhou"),
                    True,
                    f"a fonte {nome} rebentou: {r.get('erro')}",
                )
                self.assertTrue(r["ok"], f"{nome}: {r.get('erro')}")
                self.assertTrue(
                    r["linhas"],
                    f"a fonte {nome} respondeu sem linhas, e ha registo na base",
                )
                self.assertTrue(r["colunas"], f"{nome} sem colunas")

    def test_o_mcp_publica_as_fontes(self):
        from app.amplia_mcp import catalogo_completo

        User.objects.create_user("cat", password="x")
        c = catalogo_completo()
        self.assertIn("fontes", c)
        # Sem as fontes publicadas, a IA só tem duas escolhas: não fazer tabela
        # nenhuma, ou escrever os números — que é o buraco.
        self.assertTrue(c["fontes"])
