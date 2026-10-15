"""Uma só fonte de verdade para os estados de proveniencia.

`proveniencia.Estado` e `palco.FONTE_*` designavam o mesmo conceito com dois
vocabularios independentes — tres strings num lado, tres strings iguais no
outro. Funcionava enquanto ninguem mexesse. Divergia no primeiro estado novo
acrescentado a um lado e nao ao outro: `paginas.py` e `palco_dados.py`
comparavam contra `Estado`, `intents.py` comparava contra `palco.FONTE_SEM_DADO`,
e o painel passava a distinguir valores que a governanca diz serem o mesmo.

Agora `palco.FONTE_*` sao alias de `Estado`. Estes testes fixam isso: se um
quarto estado aparecer num lado, o outro tem de ter o alias, ou o ficheiro
explica o que fazer.

Nao e um teste sobre valores: e um teste sobre a **forma** do codigo. Os
valores podem mudar sem quebrar aqui; o que nao pode mudar e um lado ganhar um
estado sem o outro.
"""

from __future__ import annotations

from django.test import SimpleTestCase

from app.ia import palco
from app.ia.proveniencia import TODOS, Estado, SemDado, Simulado


class FonteUnicaDeProvenienciaTest(SimpleTestCase):
    """Nao toca a base de dados: e um teste sobre a forma do codigo."""

    def test_aliases_apontam_para_o_enum(self):
        """`palco.FONTE_*` E `Estado` — identidade, nao igualdade.

        `assertIs` e nao `assertEqual`: uma copia com o mesmo valor passaria
        num `assertEqual` e continuaria a ser a segunda fonte de verdade que
        este ficheiro veio apagar.
        """
        self.assertIs(palco.FONTE_MEDIDO, Estado.MEDIDO)
        self.assertIs(palco.FONTE_SEM_DADO, Estado.SEM_DADO)
        self.assertIs(palco.FONTE_SIMULADO, Estado.SIMULADO)

    def test_o_vocabulario_do_palco_nao_tem_estado_a_mais_ou_a_menos(self):
        """A lista de alias tem de ser exactamente a lista de estados.

        Um alias novo sem `Estado` correspondente (ou vice-versa) e drift — e e
        exactamente a classe do bug do `widget_data`: uma porta que ninguem
        inventariou. O nome do estado novo tem de aparecer dos dois lados.
        """
        apelidos = {
            palco.FONTE_MEDIDO,
            palco.FONTE_SEM_DADO,
            palco.FONTE_SIMULADO,
        }
        # Nenhum alias pode apontar para fora do enum.
        for alias in apelidos:
            with self.subTest(alias=alias):
                self.assertIn(
                    alias,
                    TODOS,
                    f"palco.FONTE_* = {alias!r} nao esta em proveniencia.TODOS",
                )

    def test_estados_novos_levam_alias(self):
        """Se `Estado` ganhar um estado, este teste lembra de o propagar.

        Nao falha sozinho — falha no dia em que se escreve o quarto estado,
        que e quando o drift ja aconteceu. A mensagem diz o que fazer.
        """
        faltam = set(TODOS) - {
            palco.FONTE_MEDIDO,
            palco.FONTE_SEM_DADO,
            palco.FONTE_SIMULADO,
        }
        self.assertEqual(
            faltam,
            set(),
            f"Estado tem {faltam} sem alias em palco.FONTE_*: "
            "acrescenta o alias em app/ia/palco.py para nao haver "
            "dois vocabularios para o mesmo conceito",
        )

    def test_sem_dado_nao_e_zero_mascarado(self):
        """`SemDado` recusa-se a ter valor: e por isso que nao pode virar 0.

        A doutrina axiomatica proibe o `or 0` que transforma ausencia em
        medicao. O enum separa os estados pelo TIPO do portador, e o portador
        de ausencia nao tem campo `valor` para o `or` encontrar. Este teste
        verifica essa propriedade estrutural, e nao um numero.
        """
        ausente = SemDado(motivo="sem medicao")
        self.assertFalse(
            hasattr(ausente, "valor"),
            "SemDado passou a ter `valor`: um `x or 0` sobre ele volta a "
            "inventar medicao a partir de ausencia",
        )
        self.assertEqual(ausente.estado, Estado.SEM_DADO)

        # E `Simulado` anuncia-se: um numero gerado nunca e indistinguivel
        # de um medido (proveniencia.py:123-149).
        gerado = Simulado(valor=42.0, gerador="teste")
        self.assertEqual(gerado.estado, Estado.SIMULADO)
        self.assertNotEqual(gerado.estado, Estado.MEDIDO)

    def test_sem_dado_sem_motivo_e_rejeitado(self):
        """'Sem dado' sem motivo obriga o produtor a adivinhar o que falta.

        Este e o unico teste do ficheiro que toca em regra de negocio: o
        motivo e accional — a diferenca entre "nao ha lancamentos" e "a
        consulta falhou" e a diferenca entre ir ao cadastro e mudar de rede
        (proveniencia.py:99-105).
        """
        with self.assertRaises(ValueError):
            SemDado(motivo="   ")
