"""Testes do Chamado Amplia — o catálogo de blocos e a trava de escrita.

O QUE ESTES TESTES PROVAM
=========================
Duas coisas, e as duas são garantias que o produto promete ao produtor:

1. **A IA só escreve no Chamado Amplia.** Nos outros presets, só lê.
2. **Um número que a IA escreve tem de estar num bloco de dado.** Texto que
   afirma números que nada sustenta desce a `sem_dado` — que é o estado que o
   painel já sabe mostrar.

A segunda é a que tem os testes mais específicos, e é a que parece enfeite.
Não é: um painel que mostra "a margem caiu para 18%" sem nenhum bloco que
mostre 18% é um painel que afirma, e é de afirmações que um produtor decide uma
safra. O custo de um falso positivo — um texto que fala de "safra 2024" ser
apanhado como número — é um aviso a mais. O custo de um falso negativo é a
decisão errada. O equilíbrio é avisar, nunca recusar.
"""

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase

from app.ia import chamado


class NumerosNoTextoTest(TestCase):
    """A leitura de números. É aqui que a maior parte do código mora."""

    def test_ignora_ponto_final(self):
        """REGRESSÃO. O número no fim da frase tem de ser lido.

        Este teste existe porque o bug que fecha é dos que não dão falha: com o
        ponto final na lista de separadores de data, `numeros_no_texto` devolvia
        `[]` para "A semente custou 77,77." — e a rastreabilidade respondia
        `medido`, que é o carimbo de "isto está certo". Um validador que passa
        sempre é pior do que nenhum, porque dá a confiança de que o número foi
        conferido.

        E o número no fim da frase é o mais comum que existe. Perder este caso
        era perder quase toda a norma.
        """
        self.assertEqual(chamado.numeros_no_texto("A semente custou 77,77."), ["77,77"])
        self.assertEqual(
            chamado.numeros_no_texto("O adubo custou 1.234,56."), ["1.234,56"]
        )
        # E a data continua a ser ignorada, que é o que o ponto protegia.
        self.assertEqual(chamado.numeros_no_texto("Lançado em 12/03/2026."), [])
        self.assertEqual(chamado.numeros_no_texto("Safra 2024/2025."), [])

    def test_ignora_ano(self):
        self.assertEqual(chamado.numeros_no_texto("A safra 2024 fechou."), [])

    def test_ignora_data(self):
        # A data de um lançamento é o próprio dado. Rastreá-la faria o alerta
        # disparar em "12/03/2026" e perder o que interessa.
        self.assertEqual(chamado.numeros_no_texto("Lançado em 12/03/2026."), [])

    def test_apanha_percentagem(self):
        self.assertEqual(chamado.numeros_no_texto("caiu para 18%"), ["18"])

    def test_apanha_valor_brasileiro_com_uma_vez(self):
        # O formato brasileiro tem de casar INTEIRO. Com a ordem das alternativas
        # invertida, "1.234,56" produzia ["1.234", "56"] — dois avisos para o
        # mesmo número, que treina o produtor a ignorar o aviso.
        self.assertEqual(chamado.numeros_no_texto("custou 1.234,56"), ["1.234,56"])

    def test_apanha_valor_brasileiro_com_duas_vezes(self):
        self.assertEqual(
            chamado.numeros_no_texto("total 1.234.567,89"), ["1.234.567,89"]
        )

    def test_numero_no_inicio_do_texto_nao_e_data(self):
        # `"" in "/-."` é True em Python: a string vazia está em qualquer
        # string. Sem a guarda, o PRIMEIRO número de um texto era tomado por
        # uma data — e o número grande é quase sempre o primeiro.
        self.assertEqual(chamado.numeros_no_texto("420.000 de despesa"), ["420.000"])

    def test_nao_comi_letra_de_palavra_como_unidade(self):
        # "89 total" produzia "89t" — a letra de "total" lida como a unidade
        # "t" (tonelada). É o que acontece quando o `\s*` antes da unidade
        # aceita zero espaços.
        self.assertEqual(chamado.numeros_no_texto("foram 89 no total"), ["89"])

    def test_palavra_com_a_letra_da_unidade_nao_e_numero(self):
        self.assertEqual(chamado.numeros_no_texto("o produtor cultiva ha"), [])

    def test_decimal_com_virgula(self):
        self.assertEqual(chamado.numeros_no_texto("foram 45,5 ha"), ["45,5"])


class TravaDeEscritaTest(TestCase):
    """A garantia central. Se estes testes falharem, a promessa é falsa."""

    def setUp(self):
        self.user = User.objects.create_user("produtor", password="x")

    def test_permite_o_chamado(self):
        pode, motivo = chamado.pode_escrever(self.user, chamado.SLUG_CHAMADO)
        self.assertTrue(pode)
        self.assertEqual(motivo, "")

    def test_permite_como_o_produtor_escreve(self):
        # Maiúsculas, acentos e espaços não podem ser a razão de um "não": uma
        # trava que falha por um acento não é uma trava, é uma fonte de erro sem
        # aviso.
        for variante in ("Chamado Amplia", "CHAMADO-AMPLIA", "chamado  amplia"):
            with self.subTest(variante=variante):
                pode, _ = chamado.pode_escrever(self.user, variante)
                self.assertTrue(pode)

    def test_recusa_qualquer_outro_preset(self):
        for slug in ("custom-custo", "amplia", "cafe", "financeiro", ""):
            with self.subTest(slug=slug):
                pode, motivo = chamado.pode_escrever(self.user, slug)
                self.assertFalse(pode)
                self.assertTrue(motivo, "um 'não' sem motivo parece uma IA avariada")

    def test_motivo_diz_que_e_leitura_e_oferece_o_chamado(self):
        _, motivo = chamado.pode_escrever(self.user, "custom-custo")
        self.assertIn("só lê", motivo)
        # O motivo que oferece o caminho é o que evita que o produtor conclua
        # que a IA não consegue.
        self.assertIn(chamado.NOME_CHAMADO, motivo)


class PedidoExplicitoTest(TravaDeEscritaTest):
    """Fase 2: o preset do produtor, quando ELE pede.

    Herda de `TravaDeEscritaTest` de propósito: os testes da porta fechada têm de
    continuar a correr contra o código novo. Se esta classe não herdasse deles,
    o `test_refusa_qualquer_outro_preset` continuaria a passar por estar a testar
    o que sempre testou — e ninguém notaria que deixou de cobrir o caminho que
    a Fase 2 mudou.

    `test_refusa_qualquer_outro_preset` continua verdade e continua a passar: sem
    `pedido_explicito`, um `custom-*` é recusado. Isto não afrouxou a regra — fez-a
    ter uma segunda porta, e esta classe vigia a porta.

    O que muda com `pedido_explicito=True` é o AUTOR da autorização: o produtor,
    respondendo ao `confirm`. Não é um campo dos `params`, e é por isso que
    nenhum handler pode ligá-lo a um nome que o modelo escolheu.
    """

    def setUp(self):
        self.user = User.objects.create_user("produtor", password="x")

    def test_o_preset_do_produtor_abre_com_pedido(self):
        pode, motivo = chamado.pode_escrever(
            self.user, "custom-custo", pedido_explicito=True
        )
        self.assertTrue(pode)
        self.assertEqual(motivo, "")

    def test_sem_pedido_continua_fechado(self):
        """A primeira porta não arceu. Este é o teste que a garante."""
        pode, _ = chamado.pode_escrever(self.user, "custom-custo")
        self.assertFalse(pode)

    def test_o_painel_do_amplia_nao_abre_nem_com_pedido(self):
        """`amplia` e `base-ia` são do PRODUTO. O produtor pedir não os torna
        dele — e um dashboard guardado num painel de sistema é uma tela que
        desaparece quando a instalação muda de versão."""
        for slug in ("amplia", "base-ia", "chamado-amplia"):
            with self.subTest(slug=slug):
                pode, motivo = chamado.pode_escrever(
                    self.user, slug, pedido_explicito=True
                )
                if slug == "chamado-amplia":
                    self.assertTrue(pode)  # é a zona, por omissão
                else:
                    self.assertFalse(pode)
                    self.assertTrue(motivo, "um 'não' sem motivo")

    def test_o_motivo_diz_que_e_o_painel_do_amplia(self):
        """Um "não" que não diz PORQUÉM produz o sintoma que este produto já
        teve: o produtor olha para ecrã nenhum e conclui que a IA está avariada."""
        _, motivo = chamado.pode_escrever(self.user, "amplia", pedido_explicito=True)
        self.assertIn(chamado.NOME_CHAMADO, motivo)

    def test_preset_bloqueado_abre_nem_com_pedido(self):
        """`visao-geral` é um `PRESET_BLOCK`: a limpeza de fantasmas apaga-o. Abrir
        aqui seria guardar uma tela num preset que não fica."""
        pode, motivo = chamado.pode_escrever(
            self.user, "visao-geral", pedido_explicito=True
        )
        self.assertFalse(pode)
        self.assertIn("custom-", motivo, "o motivo não diz o prefixo dos teus")

    def test_sem_produtor_abrange_o_pedido(self):
        from django.contrib.auth.models import AnonymousUser

        pode, _ = chamado.pode_escrever(
            AnonymousUser(), "custom-custo", pedido_explicito=True
        )
        self.assertFalse(pode, "o pedido do produtor não o torna identificado")

    def test_a_excepcao_esta_no_codigo_e_nao_nos_params(self):
        """A garantia estrutural: `pode_escrever` não aceita um nome de preset
        como autorização. Quem autoriza é o parâmetro, e o parâmetro vem da
        resposta do produtor.

        Um handler que fizesse `pode_escrever(user, params['preset'],
        pedido_explicito=True)` sem criterio seria a mesma coisa que a versão
        anterior da Fase 2: um preset reescrevível que depende de estar no sitio
        certo. Por isso o teste diz o que a assinatura NÃO aceita.
        """
        import inspect

        params = inspect.signature(chamado.pode_escrever).parameters
        self.assertIn("pedido_explicito", params)
        self.assertIs(params["pedido_explicito"].default, False)

    def test_recusa_sem_produtor(self):
        from django.contrib.auth.models import AnonymousUser

        pode, motivo = chamado.pode_escrever(AnonymousUser(), chamado.SLUG_CHAMADO)
        self.assertFalse(pode)
        self.assertTrue(motivo)

    def test_recusa_preset_ausente(self):
        pode, motivo = chamado.pode_escrever(self.user, None)
        self.assertFalse(pode)
        self.assertIn(chamado.NOME_CHAMADO, motivo)


class ZonaNoBancoTest(TestCase):
    """A trava também está no schema, e não só em Python.

    Um handler com um bug que passe o slug errado tem de falhar NA BASE DE
    DADOS. Se falhar só no Python, basta alguém escrever `objects.create()` sem
    a validação e a garantia desaparece — que é como a garantia de um
    `PresetPalco` reescrevível desapareceria.
    """

    def setUp(self):
        self.user = User.objects.create_user("produtor", password="x")

    def test_slug_fixo_e_a_unica_zona(self):
        from app.models import ChamadoAmplia

        ChamadoAmplia.objects.create(user=self.user, nome="A", corpo=[])
        with self.assertRaises(IntegrityError), transaction.atomic():
            ChamadoAmplia.objects.create(
                user=self.user, slug="custom-custo", nome="B", corpo=[]
            )

    def test_so_um_chamado_por_produtor(self):
        from app.models import ChamadoAmplia

        ChamadoAmplia.objects.create(user=self.user, corpo=[])
        with self.assertRaises(IntegrityError), transaction.atomic():
            ChamadoAmplia.objects.create(user=self.user, corpo=[])

    def test_dois_produtores_tem_a_sua_zona(self):
        from app.models import ChamadoAmplia

        outro = User.objects.create_user("vizinho", password="x")
        a = ChamadoAmplia.objects.create(user=self.user, corpo=[])
        b = ChamadoAmplia.objects.create(user=outro, corpo=[])
        self.assertNotEqual(a.pk, b.pk)
        self.assertEqual(ChamadoAmplia.objects.count(), 2)

    def test_arquivado_e_somente_leitura_para_a_ia(self):
        from app.models import ChamadoAmplia

        c = ChamadoAmplia.objects.create(user=self.user, corpo=[])
        self.assertFalse(c.somente_leitura_para_ia)
        c.estado = "arquivado"
        c.save(update_fields=["estado"])
        c.refresh_from_db()
        self.assertTrue(c.somente_leitura_para_ia)


class ValidarBlocosTest(TestCase):
    """O catálogo é a fronteira. O que não é reconhecido é descartado."""

    def test_descarta_tipo_desconhecido_e_monta_o_resto(self):
        blocos, descartados = chamado.validar_blocos(
            [{"tipo": "texto", "texto": "oi"}, {"tipo": "video"}]
        )
        self.assertEqual([b["tipo"] for b in blocos], ["texto"])
        self.assertTrue(any(d.startswith("desconhecido") for d in descartados))

    def test_nunca_levanta_com_garbage(self):
        for bruto in (None, 42, "texto", [], {"sem": "chave"}, [None, 3, "x"]):
            with self.subTest(bruto=bruto):
                blocos, _ = chamado.validar_blocos(bruto)
                self.assertIsInstance(blocos, list)

    def test_ids_continuam_apos_editar(self):
        corpo, _ = chamado.validar_blocos(
            [{"tipo": "texto", "texto": "a"}, {"tipo": "texto", "texto": "b"}]
        )
        self.assertEqual([b["id"] for b in corpo], ["b1", "b2"])
        # O segundo `adicionar` tem de continuar a numeração, senão um
        # `remover {id: "b3"}` não encontra o alvo.
        corpo, avisos = chamado.aplicar_delta(
            corpo, {"op": "adicionar", "blocos": [{"tipo": "texto", "texto": "c"}]}
        )
        self.assertEqual([b["id"] for b in corpo], ["b1", "b2", "b3"])
        self.assertEqual(avisos, [])

    def test_aceita_campos_no_item_e_na_config(self):
        # A forma mais natural que um LLM produz é `{"tipo": "texto", "texto":
        # "..."}`; a que o catálogo publica é `config`. Ambas têm de funcionar.
        a, _ = chamado.validar_blocos([{"tipo": "texto", "texto": "oi"}])
        b, _ = chamado.validar_blocos([{"tipo": "texto", "config": {"texto": "oi"}}])
        self.assertEqual(a[0]["config"]["texto"], "oi")
        self.assertEqual(b[0]["config"]["texto"], "oi")

    def test_teto_de_blocos(self):
        blocos, descartados = chamado.validar_blocos(
            [{"tipo": "texto", "texto": "x"} for _ in range(chamado.MAX_BLOCOS + 10)]
        )
        self.assertEqual(len(blocos), chamado.MAX_BLOCOS)
        self.assertTrue(any(d.startswith("acima_do_teto") for d in descartados))

    def test_texto_e_limitado(self):
        blocos, _ = chamado.validar_blocos(
            [{"tipo": "texto", "texto": "x" * (chamado.MAX_TEXTO + 500)}]
        )
        self.assertEqual(len(blocos[0]["config"]["texto"]), chamado.MAX_TEXTO)

    def test_colunas_inferidas_quando_faltam(self):
        # O campo é declarado obrigatório no catálogo e mesmo assim chega
        # vazio. Inferir da largura da linha é o que evita uma planilha de 4
        # campos sem nome nenhum, que é inutilizável.
        blocos, _ = chamado.validar_blocos(
            [{"tipo": "tabela", "linhas": [["a", "b", "c"]]}]
        )
        self.assertEqual(
            blocos[0]["config"]["colunas"], ["coluna_1", "coluna_2", "coluna_3"]
        )


class DeltaTest(TestCase):
    """Editar sem substituir tudo.

    Substituir a peça inteira obriga a IA a reenviar o que já está feito — e um
    modelo de 1,7B a reenviar 12 blocos perde dois e muda um sem querer. O
    produtor vê uma peça que perdeu conteúdo e conclui que a IA desistiu.
    """

    def corpo(self):
        corpo, _ = chamado.validar_blocos(
            [
                {"tipo": "texto", "texto": "primeiro"},
                {"tipo": "tabela", "colunas": ["a"], "linhas": [["1"]]},
                {"tipo": "texto", "texto": "terceiro"},
            ]
        )
        return corpo

    def test_remover_por_id(self):
        novo, avisos = chamado.aplicar_delta(
            self.corpo(), {"op": "remover", "id": "b2"}
        )
        self.assertEqual([b["id"] for b in novo], ["b1", "b3"])
        self.assertEqual(avisos, [])

    def test_remover_id_inexistente_avisa_e_nao_perde_nada(self):
        antes = self.corpo()
        novo, avisos = chamado.aplicar_delta(antes, {"op": "remover", "id": "b99"})
        self.assertEqual(len(novo), len(antes))
        self.assertTrue(any("id_inexistente" in a for a in avisos))

    def test_reecrever_texto_so_toca_no_texto(self):
        antes = self.corpo()
        novo, avisos = chamado.aplicar_delta(
            antes, {"op": "reescrever_texto", "id": "b1", "texto": "outra coisa"}
        )
        self.assertEqual(novo[0]["config"]["texto"], "outra coisa")
        # Os outros blocos não podem ser mexidos: é a razão de o delta existir.
        self.assertEqual(novo[1], antes[1])
        self.assertEqual(novo[2], antes[2])

    def test_reecrever_texto_em_bloco_que_nao_e_texto_avisa(self):
        novo, avisos = chamado.aplicar_delta(
            self.corpo(), {"op": "reescrever_texto", "id": "b2", "texto": "x"}
        )
        self.assertTrue(any("nao_e_texto" in a for a in avisos))
        self.assertEqual(len(novo), 3)

    def test_reordenar_nao_perde_bocos(self):
        # Um `ordem` incompleto não pode descartar o que não foi listado: perder
        # um bloco por o produtor não listar um id é perda de trabalho.
        novo, avisos = chamado.aplicar_delta(
            self.corpo(), {"op": "reordenar", "ordem": ["b3", "b1"]}
        )
        self.assertEqual([b["id"] for b in novo], ["b3", "b1", "b2"])
        self.assertEqual(avisos, [])

    def test_operacao_desconhecida_avisa(self):
        novo, avisos = chamado.aplicar_delta(self.corpo(), {"op": "explodir"})
        self.assertTrue(any("operacao_desconhecida" in a for a in avisos))
        self.assertEqual(len(novo), 3)

    def test_delta_nao_muta_o_corpo_original(self):
        antes = self.corpo()
        import copy

        copia = copy.deepcopy(antes)
        chamado.aplicar_delta(antes, {"op": "remover", "id": "b1"})
        self.assertEqual(antes, copia)


class RastreabilidadeTest(TestCase):
    """A norma: um número escrito tem de estar num bloco de dado."""

    def test_texto_sem_numero_e_medido(self):
        corpo, _ = chamado.validar_blocos(
            [{"tipo": "texto", "texto": "Está tranquilo."}]
        )
        chamado.aplicar_fonte_dado(corpo)
        self.assertEqual(corpo[0]["fonte_dado"], "medido")

    def test_texto_com_numero_sem_bloco_de_dado_desce_a_sem_dado(self):
        corpo, _ = chamado.validar_blocos(
            [{"tipo": "texto", "texto": "A margem caiu para 18%."}]
        )
        achados = chamado.rastrear_numeros(corpo)
        chamado.aplicar_fonte_dado(corpo)
        self.assertEqual(len(achados), 1)
        self.assertEqual(achados[0]["numero"], "18")
        self.assertEqual(corpo[0]["fonte_dado"], "sem_dado")

    def test_texto_que_cita_um_numero_que_existe_no_bloco_fica_medido(self):
        corpo, _ = chamado.validar_blocos(
            [
                {"tipo": "tabela", "colunas": ["margem"], "linhas": [["18%"]]},
                {"tipo": "texto", "texto": "A margem caiu para 18%."},
            ]
        )
        achados = chamado.rastrear_numeros(corpo)
        chamado.aplicar_fonte_dado(corpo)
        self.assertEqual(achados, [])
        self.assertEqual(corpo[1]["fonte_dado"], "medido")

    def test_aplicar_fonte_dado_e_auto_suficiente(self):
        """Chamada isolada, sem `aplicar_fontes` antes.

        Ler um carimbo que outra função pôs obriga a que as duas sejam sempre
        chamadas em conjunto — e o dia em que alguém chama só uma, o texto
        certainko vira `sem_dado` sem que nada tenha mudado. Já aconteceu nesta
        mesma peça: um leitor que dependia de estado que outro mantinha.
        """
        corpo, _ = chamado.validar_blocos(
            [{"tipo": "texto", "texto": "Está tranquilo."}]
        )
        chamado.aplicar_fonte_dado(corpo)
        self.assertEqual(corpo[0]["fonte_dado"], "medido")

    def test_bloco_de_dado_sem_fonte_desce_a_sem_dado(self):
        # ESTE TESTE AFIRMAVA O BUG ANTES.
        #
        # A versão anterior dizia: "uma tabela com linhas é `medido`". E as
        # linhas vinham de um modelo de 1,7B. Um número inventado com o carimbo
        # que o produtor usa para decidir uma safra é a pior coisa que este
        # sistema pode mostrar, porque não dá erro.
        #
        # O contrato agora é: um bloco de dado só é `medido` se o SERVIDOR o
        # consultou. Com linhas escritas à mão e sem fonte, é `sem_dado` — e as
        # linhas são descartadas antes de irem para a base (ver
        # `tests_chamado_fontes.DescartaNumerosDaIaTest`).
        corpo, _ = chamado.validar_blocos(
            [{"tipo": "tabela", "colunas": ["a"], "linhas": [["1"]]}]
        )
        chamado.aplicar_fonte_dado(corpo)
        self.assertEqual(corpo[0]["fonte_dado"], "sem_dado")
        # E diz porquê — um `sem_dado` sem motivo obriga o produtor a adivinhar.
        self.assertIn("fonte", corpo[0]["config"]["motivo"].lower())

    def test_um_bloco_calculado_pelo_servidor_e_medido(self):
        corpo = [
            {
                "id": "b1",
                "tipo": "tabela",
                "titulo": "Despesas",
                "config": {
                    "fonte": "despesas-por-categoria",
                    "linhas": [["Adubo", "10,00"]],
                },
                # O carimbo que `aplicar_fontes` põe. E é o ÚNICO caminho para
                # `medido` num bloco de dado.
                "fonte_dado": "medido",
            }
        ]
        chamado.aplicar_fonte_dado(corpo)
        self.assertEqual(corpo[0]["fonte_dado"], "medido")


class RegistoDoBlocoTest(TestCase):
    """O MCP publica o dicionário, e o dicionário não pode estar vazio."""

    def test_todo_tem_campos_declarados(self):
        # A razão de `palco.campos_conhecidos` estar morta: lia uma chave que
        # nenhuma entrada escrevia. Aqui há teste a falhar se isso voltar.
        for tipo, spec in chamado.CATALOGO_BLOCOS.items():
            with self.subTest(tipo=tipo):
                self.assertTrue(spec.get("campos"), f"{tipo} sem campos publicados")

    def test_todo_obligatorio_esta_nos_campos(self):
        for tipo, spec in chamado.CATALOGO_BLOCOS.items():
            for campo in spec.get("obrigatorios", ()):
                with self.subTest(tipo=tipo, campo=campo):
                    self.assertIn(campo, spec["campos"])

    def test_campos_conhecidos_le_o_catalogo(self):
        self.assertEqual(
            chamado.campos_conhecidos("tabela"), ("titulo", "colunas", "linhas")
        )

    def test_referencia_tem_o_essencial(self):
        ref = {b["id"]: b for b in chamado.referencia_blocos()}
        self.assertIn("texto", ref)
        self.assertIn("origem", ref["texto"])
        self.assertEqual(ref["texto"]["origem"], "prosa")
        self.assertEqual(ref["kpi"]["origem"], "dado")

    def test_resumo_menca_a_regra_dos_numeros(self):
        # Esconder a regra não a elimina — só faz o modelo descobri-la quando a
        # tela já está errada.
        self.assertIn("sem_dado", chamado.summarise_blocos())
