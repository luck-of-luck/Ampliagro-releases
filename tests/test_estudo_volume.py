"""A6 — o estudo de volume nao cresce. Nao e' um documento, e' uma catraca.

O QUE ESTE TESTE TRAVA
----------------------
`docs/super-estudo-globo-rural/` tem uma meta escrita de **1.000.000 de linhas**.
MEDIDO em 2026-10-03:

    ficheiros    2.400 (aprox)  ->  1.403
    bytes        2,4 MB        ->  237.137.320   (237 MB)
    do pipeline v2                            1.312 ficheiros

E o **`ANALISE-1001-2400-PROXIMO.md`** — o exemplar do problema — dava:

    linhas totais   26.606
    linhas unicas    3.037
    TAXA DE UNICIDADE  11,4%      (89% e' repeticao)

O proprio `SISTEMA-TOP1-INTEGRACAO.md` admite: *"vs repeticao atual para bater 1M"*.

PORQUE ISTO E' UM TESTE E NAO UM ACORDO
-----------------------------------------
A A6 da carta diz *"congelar, nenhuma linha nova"*. E um acordo nao se mede: foi
exatamente o que aconteceu, e a directoria tripled em massa. Um acordo respeitado
por 4 sessoes seguidos e' um teste que faz barulho.

Este teste e' a mesma tecnica que a catraca de aparencia (`test_aparencia_invariante`),
e pelos mesmos motivos:

1. **Nao e' "tem de ser zero".** Seria mentira: o conteudo ja la esta, e apagar
   237 MB de trabalho alheio e' o incidente da §13 da carta. O objectivo e' que
   **pare de crescer**, nao que desapareca.
2. **Falha no delTA.** Quem cria um ficheiro novo ve-o barrado.
3. **Baixar a baseline e' explicito e e' decisao de quem tem o direito** — e vem
   com um `--mostra` que diz exactamente quanto entrou, para nao ser um acto de
   fe.

O QUE NAO ESTE TESTE FAZ
-------------------------
Nao decide o que fazer com os 237 MB que ja la estao. Apagar, arquivar num
bucket, ou reduzir ao que tem sinal — sao tres decisoes com custos diferentes, e
sao do dono. Este teste so garante que **nao entra mais**, que e' a parte
automatizavel.

E medido: um `v2/` com 1.312 ficheiros brutos de transcricao e' contexto que
ninguem le. Nao e' conhecimento, e' ocupacao de disco.
"""

from __future__ import annotations

import json
import pathlib

from django.test import SimpleTestCase

RAIZ = pathlib.Path(__file__).resolve().parents[1]
ESTUDO = RAIZ / "docs" / "super-estudo-globo-rural"
BASE = pathlib.Path(__file__).parent / "estudo_baseline.json"

#: Sub-pastas que nao contam. O `v2/pipeline/bruto/` e' saida de transcricao
#: automatica — cada ficheiro e' um video inteiro. E' precisamente o que nao
#: deve crescer sem decisao, por isso conta. O que fica de fora e' o
#: `.gitignore` e o cache, que nao sao conhecimento nem ocupacao.
IGNORAR = {".git", "__pycache__", "node_modules"}


def medir() -> dict:
    if not ESTUDO.exists():
        return {"ficheiros": 0, "bytes": 0, "por_subpasta": {}}
    ficheiros = 0
    total = 0
    por_subpasta: dict[str, int] = {}
    for p in ESTUDO.rglob("*"):
        if not p.is_file():
            continue
        if any(parte in IGNORAR for parte in p.parts):
            continue
        ficheiros += 1
        total += p.stat().st_size
        rel = p.relative_to(ESTUDO)
        chave = rel.parts[0] if len(rel.parts) > 1 else "(raiz)"
        por_subpasta[chave] = por_subpasta.get(chave, 0) + 1
    return {"ficheiros": ficheiros, "bytes": total, "por_subpasta": por_subpasta}


class VolumeDoEstudoNaoCresce(SimpleTestCase):
    """A A6 como catraca."""

    def setUp(self):
        self.base = json.loads(BASE.read_text(encoding="utf-8-sig"))

    def test_nem_ficheiros_nem_bytes_crescem(self):
        atual = medir()
        for chave in ("ficheiros", "bytes"):
            self.assertLessEqual(
                atual[chave],
                self.base[chave],
                f"O estudo cresceu em {chave}: "
                f"{self.base[chave]:,} -> {atual[chave]:,} "
                f"(+{atual[chave] - self.base[chave]:,}).\n"
                "A A6 diz: nenhuma linha nova de volume. Uma linha de estudo "
                "que nao acrescenta conhecimento e' contexto gasto por ninguem.\n"
                "Se a entridade e' real e nao gerada, mede a taxa de unicidade "
                "PRIMEIRO e mostra o numero. Depois:\n"
                "    python tests/estudo_volume.py --aceitar\n"
                f"Sub-pastas: {json.dumps(atual['por_subpasta'], ensure_ascii=False)}",
            )

    def test_nenhuma_sub_pasta_nova(self):
        """Um `v3/` aparece com um nome novo e nao mexe nos totais de uma vez.

        Este teste e' o que impede o padrão de "outro ciclo, outro directorio":
        cada ciclo novo contornava uma contagem por pasta.
        """
        atual = medir()
        novas = sorted(set(atual["por_subpasta"]) - set(self.base["por_subpasta"]))
        self.assertEqual(
            novas,
            [],
            f"Sub-pastas novas no estudo: {novas}. "
            "Um ciclo novo com nome novo nao e' a mesma coisa que continuar o "
            "anterior — e' por isso que se conta por sub-pasta.",
        )

    # ─────────────────────────────────────────────────────────────────────
    # A DIREÇÃO QUE FALTAVA: ELIMINAÇÃO
    # ─────────────────────────────────────────────────────────────────────
    #
    # MEDIDO 2026-10-04. Ate aqui a catraca barrava em UMA direcção: crescer.
    # `assertLessEqual` nos totais e `assertEqual` nas sub-pastas novas. E um
    # volume que so cresce nao pode ser violado por uma eliminacao — que e' o
    # modo de falha mais perigoso dos dois, porque:
    #
    #   * apagar 91 ficheiros de analise NAO dispara nenhuma das tres
    #     verificacoes existentes;
    #   * a pasta e' untracked, logo o git tambem nao regista a remocao;
    #   * o commits que a mexeu (`9c8eb1a`, "mover documentacao e artefactos
    #     para o galho de arquivo") nao diz nada sobre o que foi.
    #
    # MEDIDO: `analises-profundas` 67 -> 0, `(raiz)` 24 -> 0. together
    # 91 ficheiros de analise que desapareceram em silencio.
    #
    # Isto NAO e' um pedido para os restaurar. E' o registo de que a
    # eliminacao nao tinha alarme, e de que agora tem. A decisao do que fazer
    # com os 91 e' de quem e' dono do conteudo — e o caminho para a tombar e'
    # `python tests/estudo_volume.py --aceitar --porque "..."`, que exige
    # escrita e guarda a razao dentro da baseline.

    def test_nenhuma_sub_pasta_desaparece(self):
        """Uma sub-pasta da baseline nao pode desaparecer sem registo."""
        atual = medir()
        base = self.base["por_subpasta"]

        desaparecidas = {
            chave: base[chave]
            for chave, n in base.items()
            if n > 0 and atual["por_subpasta"].get(chave, 0) == 0
        }

        self.assertEqual(
            desaparecidas,
            {},
            "Sub-pastas que desapareceram: "
            + json.dumps(desaparecidas, ensure_ascii=False, sort_keys=True)
            + ".\n"
            "Apagar conteudo do estudo nao dispara nenhuma outra verificacao "
            "deste ficheiro, e a pasta e' untracked — logo o git tambem nao "
            "fica a saber. Se a remocao foi de proposito, aceita com razao "
            "escrita:\n"
            "    python tests/estudo_volume.py --aceitar "
            '--porque "mover para o galho de arquivo"\n'
            "Se nao foi, o ultimo commit que mexeu no estudo foi: "
            + _ultimo_commit_do_estudo(),
        )

    def test_nenhuma_sub_pasta_encolhe(self):
        """Nenhuma sub-pasta pode ter MENOS ficheiros do que a baseline.

        Mais picky do que `desaparece`, e e' justificado: uma sub-pasta que
        perde 3 de 40 ficheiros nao desaparece, e por isso passava. Perder
        ficheiros e' uma decisao; perder *alguns* ficheiros sem querer e' um
        acidente, e o acidente e' o que ninguem nota.
        """
        atual = medir()
        base = self.base["por_subpasta"]

        encolheu = {}
        for chave, antes in base.items():
            agora = atual["por_subpasta"].get(chave, 0)
            if agora < antes:
                encolheu[chave] = (antes, agora)

        self.assertEqual(
            encolheu,
            {},
            "Sub-pastas que encolheram (antes -> agora): "
            + json.dumps(encolheu, ensure_ascii=False, sort_keys=True)
            + ".\n"
            "Nenhuma sub-pasta pode perder ficheiros sem que a baseline seja "
            "reescrita com razao:\n"
            '    python tests/estudo_volume.py --aceitar --porque "..."',
        )


def _ultimo_commit_do_estudo() -> str:
    """O commit que mexeu no estudo. Va para a mensagem: 'ninguem sabe' e' a
    pior coisa que se pode dizer a quem tenta reconstruir o que aconteceu."""
    import subprocess

    try:
        r = subprocess.run(
            [
                "git",
                "log",
                "-1",
                "--format=%h %s",
                "--",
                "docs/super-estudo-globo-rural",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(RAIZ),
        )
        return (r.stdout or "").strip() or "(nenhum commit)"
    except Exception:
        return "(git indisponivel)"


class RelatorioDeUnicidade(SimpleTestCase):
    """Nao mede nada. LEMBRA o que se deve medir antes de aceitar volume.

    Este teste passa sempre, de proposito. A sua funcao e' estar la quando alguem
    correr `--aceitar` e perguntar "mas este conteudo e' bom?" — e a resposta
    honesta e': nao foi verificado'.
    """

    def test_a_pergunta_que_tem_de_acompanhar_o_volume(self):
        self.assertTrue(
            (BASE.exists()),
            "falta o estudo_baseline.json; correr tests/estudo_volume.py",
        )
        base = json.loads(BASE.read_text(encoding="utf-8-sig"))
        self.assertIn("unicidade_exemplo", base)
        self.assertIsNotNone(
            base.get("unicidade_exemplo"),
            "a baseline devia lembrar o exemplo medido: o "
            "ANALISE-1001-2400-PROXIMO.md dava 11,4% de unicidade.",
        )
