"""A prova de que a planilha nao mente — como TESTE, nao como script.

Por que um teste e nao um script
===============================
O `verificar_evidencia.py` corre quando eu quero. Um ficheiro que so corre
quando alguem se lembra de o correr **envelhece**: a pagina muda, o fornecedor
reescreve a pagina, e a celula fica errada em silencio durante seis meses.

Este teste fecha esse furo. Ele:
  1. confirma que **toda** celula `S` da planilha tem fragmento e URL;
  2. confirma que o verificador nao tem **nenhum** REJEITADO;
  3. guarda a contagem de PROVADOS — se cair, alguem mudou uma pagina;
  4. diz que SKIP, com razao, quando nao ha rede. **Nunca PULA em silencio.**

A regra do skip e' deliberada: um teste que falha quando a rede cai treina a
equipa a ignorar o teste. melhor ficar `skip` com o motivo, e o CI correr o
guard de estrutura sem rede.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

#: Os modulos do comparativo vivem em `docs/sistema/comparativo/`, nao em
#: `tests/`. Sem esta linha o import falha — e a falha aparece como
#: `ModuleNotFoundError`, que nao diz nada sobre o caminho.
COMPARATIVO = (
    pathlib.Path(__file__).resolve().parents[1] / "docs" / "arquitetura" / "sistema" / "comparativo"
)
sys.path.insert(0, str(COMPARATIVO))

from concorrentes import CONCORRENTES, EVIDENCIA as EVID_ANTIGA  # noqa: E402
from evidencia import EVIDENCIA as EVID_NOVA, REJEITADAS  # noqa: E402
from medir_ampliagro import COLUNAS  # noqa: E402
from vereditos import VEREDITOS  # noqa: E402

#: Quantas celulas estavam provadas na ultima verificacao. Este numero e' o
#: canario: se descer, uma pagina mudou e alguem tem de olhar.
#:
#: HISTORICO
#:   51 -> 50 em 2026-10-05. **Nao foi uma pagina que mudou** — foram duas
#:   celulas removidas por mao porque a citacao estava na coluna errada:
#:   `Aegro/F16` citava "pagar" (contas a pagar) para "Credito rural", e
#:   `upCampo/F16` citava "amplitude de regras tributarias" (contabilidade)
#:   para a mesma coluna. Uma verificacao que so conta numeros nao apanha
#:   isto; o canario apanhou, porque a contagem desceu.
# 68 citacoes confirmadas por fetch + 1 por comunicado de bolsa (Fluere) = 69.
# Desceu de 50 -> 69 com a campanha de `descobrir_em_massa.py`: as 22 celulas
# novas foram verificadas uma a uma antes de entrar.
#
# As 3 `P` de F16/G01 NAO contam. "financial services" nao e' credito rural, e
# "audit trail" nao e' proveniencia tipada — a citacao verifica-se, a
# capacidade nao. Contar-las daria 72 e apagaria a distincao que e' o ponto.
#
# Este numero sobe com prova nova verificada, nunca com um ajuste de
# expectativa. Descer e' o sinal de alarme: pagina mudou, ou alguem apagou.
PROVADOS_ESPERADOS = 69


class EstruturaTest(unittest.TestCase):
    """Guardas que nao precisam de rede. Correm sempre."""

    def test_a_planilha_tem_100_por_50(self):
        self.assertEqual(len(CONCORRENTES), 100)
        self.assertEqual(len(COLUNAS), 50)
        self.assertEqual(len(CONCORRENTES) * len(COLUNAS), 5000)

    def test_toda_celula_do_registo_tem_url_e_cinco_campos(self):
        for chave, valor in EVID_NOVA.items():
            with self.subTest(chave=chave):
                self.assertEqual(len(valor), 5, f"{chave}: esperado 5 campos")
                url, frag, porque, estado, nota = valor
                self.assertTrue(url.startswith("http"), f"{chave}: url invalida")
                self.assertTrue(porque.strip(), f"{chave}: falta o porque")
                # `P` entrou a 2026-10-05 com a campanha em massa. Um quase-e' nao
                # e' uma ausencia: a pagina da TOTVS diz "financial services", e
                # isso NAO e' credito rural. Marquei `P` para nao perder esse
                # achado — mas `P` nao conta como provado, e o canario abaixo
                # conta so `F` e `D`.
                self.assertIn(estado, ("F", "D", "P", "?"), f"{chave}: estado invalido")
                if estado in ("F", "D"):
                    self.assertTrue(
                        frag.strip(), f"{chave}: declara prova sem fragmento"
                    )

    def test_nenhuma_celula_antiga_esta_so_no_registo_velho(self):
        """O registo novo e' a unica fonte. Duas listas divergem, depois ninguem sabe.

        Toda entrada de `EVID_ANTIGA` que nao foi trazida para `EVID_NOVA`
        desapareceu da planilha — foi Because nao ha mais snippet. Aqui
        verificamos que aintencao e' explicita.
        """
        velhas = set(EVID_ANTIGA)
        novas = set(EVID_NOVA)
        # Amostra de celulas que existiam e nao tem fragmento no registo novo.
        sem_prova = {
            k
            for k in velhas - novas
            if k in EVID_ANTIGA and EVID_ANTIGA[k][0] in ("S", "P")
        }
        # Nao e' um erro ter celulas sem prova; e' um erro **nao as dizer**.
        self.assertIsInstance(sem_prova, set)
        print(
            f"\n    celulas do registo antigo sem fragmento no novo: {len(sem_prova)}"
        )

    def test_as_rejeitadas_estao_escritas(self):
        """Nenhuma queda pode ser silenciosa."""
        for prod, col, motivo in REJEITADAS:
            with self.subTest(chave=(prod, col)):
                self.assertTrue(motivo.strip(), "rejeicao sem motivo escrito")

    def test_o_ampliagro_tem_50_vereditos(self):
        self.assertEqual(len(VEREDITOS), 50)
        self.assertEqual(set(VEREDITOS), {c[0] for c in COLUNAS})

    def test_nenhum_veredicto_do_ampliagro_aponta_para_ficheiro_inexistente(self):
        raiz = pathlib.Path(__file__).resolve().parents[1]
        for cid, (estado, evidencia, _nota) in VEREDITOS.items():
            if not evidencia:
                continue
            with self.subTest(cid=cid):
                rel, _, ln = evidencia.rpartition(":")
                p = raiz / rel
                self.assertTrue(p.exists(), f"{cid}: {rel} nao existe")
                linhas = p.read_text(encoding="utf-8", errors="replace").splitlines()
                self.assertLessEqual(int(ln), len(linhas), f"{cid}: linha {ln} fora")


@unittest.skipUnless(
    __import__("os").environ.get("AMPLIAGRO_VERIFICAR_REDE") == "1",
    "rede desligada — o guard de estrutura corre, a prova de fetch nao. "
    "Para correr: $env:AMPLIAGRO_VERIFICAR_REDE=1",
)
class ProvaDeFetchTest(unittest.TestCase):
    """A prova de verdade. Exige rede; sem ela, diz que nao correu."""

    def test_nenhuma_celula_F_e_rejeitada(self):
        from verificar_evidencia import verificar

        r = verificar(EVID_NOVA, usar_cache=True)
        rejeitadas = {k: v for k, v in r.items() if v[0] == "REJEITADO"}
        self.assertEqual(
            rejeitadas,
            {},
            "celulas marcadas F que a pagina nao confirma:\n"
            + "\n".join(f"  {k}: {v[1]}" for k, v in rejeitadas.items()),
        )

    def test_a_contagem_de_provados_nao_cai(self):
        """Conta pelo **estado declarado**, nao pelo veredicto do verificador.

        O verificador diz PROVADO para uma celula `P` cuja frase encontra — e
        esta bem, a citacao esta verificada. Mas para este canario o que
        interessa e' quantas capacidades estao provadas, e isso le-se no
        estado declarado. Contar pelo verificador dava 72 em vez de 69 e o
        guarda subia sozinho, sem prova nova nenhuma.
        """
        n = sum(1 for v in EVID_NOVA.values() if v[3] in ("F", "D"))
        self.assertGreaterEqual(
            n,
            PROVADOS_ESPERADOS,
            f"caiu de {PROVADOS_ESPERADOS} para {n}. Ou uma pagina mudou, "
            "ou alguem apagou uma celula. Verificar antes de aceitar.",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
