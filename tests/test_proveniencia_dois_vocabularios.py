"""Os DOIS vocabulários de proveniência não podem divergir outra vez.

O que aconteceu
---------------
O `MERGED.md` (síntese de 8 análises, 2026-10-04) registou o erro mais
instructivo de toda a operação. Três agentes — 1, 9 e 7 — mediram o estado da
proveniência e publicaram, com a confiança de quem mediu:

    "a proveniência tem TRÊS estados, e `declarado` não existe"

**Estavam errados os três.** O agente 2 tinha razão, e a razão é que existem
DOIS ficheiros:

    app/validators.py:11-17      ESTADOS_FONTE = {medido, medida_com_ressalva,
                                                  suspect, sem_dado, declarado}
    app/ia/proveniencia.py:68    TODOS = (MEDIDO, SEM_DADO, SIMULADO)   <- sem 'declarado'

Os três olharam o segundo. Ninguém foi ler o primeiro. E o pior não é o
erro: é que **convergência entre agentes amplificou o erro em vez de o travar**
— três medições independentes do mesmo ficheiro concordaram, e as três
concordavam porque as três mediram a mesma coisa.

Este ficheiro é o que faz o que os três agentes não fizeram: **lê os dois
sítios e compara.**

A DIVULGÊNCIA REAL, e o que ela custava
=======================================
`app/ia/proveniencia.py` é o módulo que o **PAINEL** usa. `app/validators.py`
é o que **valida a escrita**. Enquanto o painel não soubesse dizer
"isto foi uma pessoa que afirmou", o produtor que digitasse uma produtividade
que se lembrava via ver o painel mostrar `fonte_dado: "medido"` — e um
comprador que pagasse mais por esse lote pagaria por uma **declaração
tratada como medição**, que é exactamente o que `validators.py:26-37` chama
"a pior mentira possível nesta camada".

Isto é pior que inventar um zero. Um zero inventado é visível e alguém
pergunta. Um `declarado` marcado como `medido` é **plausível**, entra na
cadeia de custódia, e ninguém o questiona durante meses.

O QUE ESTE TESTE TRAVA
======================
1. `proveniencia.Estado` tem `declarado` — o estado que o validador exige e o
   painel não tinha.
2. Todo o estado do painel está no conjunto do validador. Se alguém acrescentar
   um quarto estado só ao painel, este teste falha: um `fonte_dado` que o
   validador não conhece é um `fonte_dado` que ninguém sabe validar.
3. Todo o estado do validador é serializável pelo painel. O inverso: um estado
   que a escrita aceita e o painel não sabe desenhar é um estado que o
   produtor perde.
4. `declarado` sobrevive à serialização — não pode ser engolido pelo `else`
   final de `serializar()`, que é o caminho dos rótulos e das séries.

A nota sobre `simulado`
=======================
`simulado` NÃO está em `ESTADOS_FONTE`. Isto é propositado e não é um
buraco: um valor simulado não é uma afirmação sobre o mundo, é uma pergunta
"como ficaria o ecrã com o dado". Deixá-lo fora do conjunto do validador é
correcto — o validador valida o que se **afirma**, e um simulado não afirma.
Este teste conhece a diferença e não a trata como divergência.
"""

from django.test import SimpleTestCase

from app import validators
from app.ia import proveniencia as P


class OsDoisVocabulariosNaoDivergemTest(SimpleTestCase):
    def test_o_painel_conhece_declarado(self):
        """O estado que faltava, e que é o mais importante dos cinco.

        `validators.py:9` chama-lhe "o mais importante dos cinco" desde
        2026-10-03. O painel, que é o que o produtor vê, não o conhecia.
        """
        self.assertTrue(
            hasattr(P.Estado, "DECLARADO"),
            "proveniencia.Estado nao tem DECLARADO. O produtor que afirma um "
            "valor via ver o painel mostrar 'medido' — e o validador "
            "(validators.py:40-41) diz que isso e' a mentira que esta camada "
            "existe para impedir.",
        )
        self.assertEqual(P.Estado.DECLARADO, "declarado")
        self.assertIn(
            P.Estado.DECLARADO,
            P.TODOS,
            "DECLARADO existe mas nao esta em TODOS: serializar() nunca o "
            "alcanca e o valor cai no `else` final, que nao escreve "
            "fonte_dado.",
        )

    def test_o_validador_nao_perde_estados_para_o_painel(self):
        """Todo o estado que a escrita aceita tem de ser desenhável.

        Um estado que o validador aceita e o painel nao sabe escrever e' um
        estado que o produtor perde: a gravacao fica correcta e a leitura
        mostra outra coisa.
        """
        em_ambos = set(validators.ESTADOS_FONTE) & set(P.TODOS)
        perdidos = set(validators.ESTADOS_FONTE) - set(P.TODOS)
        self.assertEqual(
            perdidos,
            set(),
            f"o validador aceita {sorted(perdidos)} e o painel nao sabe "
            f"escrever. A gravacao fica correcta e o painel mostra outra "
            f"coisa. Estados em comum: {sorted(em_ambos)}.",
        )

    def test_o_painel_nao_inventa_estados_que_o_validador_nao_conhece(self):
        """O inverso do anterior, e mais perigoso.

        Um `fonte_dado` que o validador nunca viu não é validado por nada.
        Escrever `fonte_dado: "estimado"` num widget parece conservador
        ("se não é medido nem simulado, será estimado") e não é: é um estado
        sem regra, sem validação e sem significado para o validador.
        """
        # `simulado` é a excepção deliberada, ver a nota do docstring.
        desconhecidos = (
            set(P.TODOS) - set(validators.ESTADOS_FONTE) - {P.Estado.SIMULADO}
        )
        self.assertEqual(
            desconhecidos,
            set(),
            f"o painel escreve {sorted(desconhecidos)} e o validador não "
            "conhece esse estado. Não há regra que o valide.",
        )


class SensorDuvidosoTest(SimpleTestCase):
    """`medido_com_ressalva` e `suspect` — o sensor a falar com ressalva.

    Estes dois estados eram o que faltava **depois** de `declarado`, e são os
    que protegem a física: um `NaN` que chega a um KPI envenena o primeiro
    `Math.min()` que o tocar, e não há nada no ecrã que diga porquê.
    """

    def test_ressalva_sai_com_o_numero_e_a_ressalva(self):
        saida = P.serializar(
            P.MedidoComRessalva(
                23.5, "Estacao MG-01", "3 de 40 leituras fora de 2 desvios"
            ),
            chave="temp_media",
        )
        self.assertEqual(saida["temp_media"], 23.5)
        self.assertEqual(saida["fonte_dado"], "medido_com_ressalva")
        self.assertIn("desvios", saida["ressalva"])

    def test_ressalva_sem_ressalva_e_rejeitado(self):
        """Prometer a ressalva e não a entregar é pior que `medido`.

        O produtor lê `fonte_dado: "medido"` e nunca soube que o sensor
        duvidava. Se não há nada a dizer, o estado certo é `Medido`.
        """
        with self.assertRaises(ValueError):
            P.MedidoComRessalva(23.5, "Estacao MG-01", "")

    def test_suspect_nao_devolve_o_numero(self):
        """`None`, nunca o NaN.

        Guardar o valor e marcá-lo suspect seria continuar a transportar um
        número que ninguém pode usar, e algum `float()` mais tarde deixa de
        o olhar.
        """
        saida = P.serializar(P.Suspect("Precipitacao negativa: -3 mm"), chave="chuva")
        self.assertIsNone(saida["chuva"])
        self.assertEqual(saida["fonte_dado"], "suspect")
        self.assertIn("negativa", saida["motivo"])

    def test_um_nan_nao_passa_como_medido(self):
        """A propriedade que o estado existe para garantir.

        `Medido` só exige uma fonte — e um NaN tem uma fonte tan válida como
        o 23.5. Sem `Suspect`, ele entrava no KPI.
        """
        nan = float("nan")
        # Medido aceita: tem fonte. E' precisamente esse o problema.
        self.assertEqual(P.Medido(nan, "Estacao MG-01").estado, P.Estado.MEDIDO)
        # Logo tem de existir uma via que o trave.
        suspeito = P.Suspect("NaN do sensor")
        self.assertIsNone(P.serializar(suspeito, chave="chuva")["chuva"])

    def test_suspect_sem_motivo_e_rejeitado(self):
        with self.assertRaises(ValueError):
            P.Suspect("  ")

class DeclaradoOBrasaTest(SimpleTestCase):
    """O estado novo tem de se comportar como os outros."""

    def test_serializa_com_fonte_dado_declarado(self):
        saida = P.serializar(P.declarar(65, "produtor"), chave="sc_ha")
        self.assertEqual(saida["sc_ha"], 65)
        self.assertEqual(saida["fonte_dado"], "declarado")
        # `fonte` e o que o palco ja le; o `fonte_dado` diz qual dos dois e.
        self.assertEqual(saida["fonte"], "produtor")

    def test_declared_sem_autor_e_rejeitado(self):
        """`declarado` sem `por` e' 'alguem afirmou'.

        E' o mesmo buraco que `Medido` sem `fonte` ja fecha: um numero sem
        responsavel nao e' auditavel.
        """
        with self.assertRaises(ValueError):
            P.Declarado(65, "   ")

    def test_declarar_none_da_sem_dado_e_nao_declarado(self):
        """Afirmar nada nao e' afirmar. E' ausencia.

        E o mesmo ramo que `medir(None)` toma, e pela mesma razao: sem isto,
        "o produtor nao afirmou" e "o produtor afirmou zero" liam-se igual.
        """
        v = P.declarar(None, "produtor")
        self.assertIsInstance(v, P.SemDado)

    def test_declared_nao_promove_a_medido(self):
        """A regra de `validators.py:40-41`, execitada.

        Nao ha conversao implicita de `Declarado` para `Medido`. Se um dia
        existir, este teste falha — e essa e' a razao de existir.
        """
        v = P.declarar(65, "produtor")
        self.assertNotEqual(v.estado, P.Estado.MEDIDO)
        self.assertEqual(v.estado, P.Estado.DECLARADO)
