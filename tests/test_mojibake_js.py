"""Nenhum ficheiro JS pode ter mojibake. Este teste trava isso.

PORQUE ISTO EXISTE
==================
`app/static/js/pagina-index.js` (692 KB) tinha a codificacao TRIPLA em
690 linhas. MEDIDO no DOM antes da correccao:

    .amp-kpi__label.textContent = "ÃƒÂ<U+0081>rea Total"

O productor via `ÃÂrea` no cartao "Area Total" do dashboard. Nao era o
HTML, nao era a base, nao era a API — era o proprio ficheiro JS, gravado
assim e committado assim.

O QUE ESTE TESTE DETECTA, E PORQUE ASSIM
========================================
O detector anterior que escrevi acusava **4069 ocorrencias** em
`pagina-index.js`. Quase todas as 4069 eram FALSAS: o padrao
`[ÃÂ][algo][algo]` apanha portugues legitimo — `avô`, `irmã`, `João`,
`mãe`, `cabeça`. `Ã` e `Â` sao letras portuguesas.

O sinal que nao falha e' o **controlo C1** (U+0080-U+009F): um
caractere que nao existe em nenhuma lingua escrita, e que so aparece
quando um byte e' lido como latin-1. E o par `Ãƒ` (`A-tilde` + `f-hook`),
que so sai de UTF-8 lido como cp1252.

Por isso o detector aqui e' C1 + `Ãƒ`, e NAO `Ã`/`Â` isolados. Testei os
dois: o detector de `ÃÂ` dava 4069; este da zero num ficheiro limpo.

A TOLERANCIA: PORQUE NAO FALHA COM `Ãª` E SIMPLES
================================================
Este ficheiro tem acentos DUPLICADOS de proposito (nomes deTile em
portugues como `Timor-Leste`, que o browser duplica para gerar os
`stat_tiles`). Entao um acento isolado no ficheiro e' normal e nao e'
mojibake. Por isso o detector exige o par completo `Ãƒ` — e nao a letra
so. Um teste que acusasse `Ã` Isolado obrigaria a Choose entre o bug e a
funcionalidade.
"""

import pathlib
import re
import unittest

RAIZ = pathlib.Path(__file__).resolve().parents[1]
JS = RAIZ / "app" / "static" / "js"

# controlo C1: nao existe em texto nenhum
C1 = re.compile("[\u0080-\u009f]")
# 'A-tilde' seguido de 'f-hook': so sai de UTF-8 lido 2x como cp1252
AE_F = re.compile("\u00c3\u0192")

IGNORAR = {"node_modules", ".git", ".venv", "staticfiles", "__pycache__"}


class MojibakeNoJsTest(unittest.TestCase):
    def _ficheiros(self):
        for p in sorted(JS.rglob("*.js")):
            if any(x in p.as_posix() for x in IGNORAR):
                continue
            yield p

    def test_nenhum_js_tem_mojibake(self):
        """Nenhum `Ãƒ` e nenhum controlo C1 em qualquer .js do frontend."""
        maus = []
        for p in self._ficheiros():
            t = p.read_text(encoding="utf-8", errors="replace")
            c1 = C1.findall(t)
            af = AE_F.findall(t)
            if c1 or af:
                maus.append((p, len(c1), len(af)))

        if maus:
            detalhe = "\n".join(
                "    %-34s %d controlo(s) C1, %d par(es) Ãƒ"
                % (p.relative_to(RAIZ).as_posix(), n_c1, n_af)
                for p, n_c1, n_af in maus
            )
            self.fail(
                "%d ficheiro(s) com mojibake:\n%s\n\n"
                "MEDIDO: em `pagina-index.js` o rotulo do KPI chegou a tela "
                "como `ÃƒÂrea Total` — codepoints U+00C3 U+0192 U+00C2 "
                "U+0081, ou seja UTF-8 lido como cp1252 DUAS vezes.\n\n"
                "O U+0081 nao existe em nenhuma lingua escrita: e' a "
                "assinatura de um byte lido como latin-1. O par `Ãƒ` so "
                "sai de UTF-8 lido como cp1252.\n\n"
                "Como reparar (iterativo, porque a codificacao aqui e' "
                "TRIPLA — `disponÃƒÂ­vel` precisa de DOIS passos para dar "
                "`disponível`):\n\n"
                "    A t = s.encode('cp1252'); t = t.decode('utf-8')\n"
                "    repete ate estabilizar\n\n"
                "OU, para a faixa C1, por cp1252 E LINHA-A-LINHA (que e' o "
                "que o script usou): os controles C1 entram pelo valor do "
                "proprio codepoint e o resto vai por cp1252 — nenhum dos "
                "dois codecs sozinho serve, porque cp1252 nao tem U+0081 e "
                "latin-1 nao tem 'ƒ' (U+0192).\n\n"
                "CONFIRMA QUE NAO E' FALSO POSITIVO: `Ã` e `Â` sao letras "
                "PORTUGUESAS. Um detector que os acuse acusa `avô` e "
                "`irmã`. Por isso este teste exige o par completo `Ãƒ`."
                % (len(maus), detalhe)
            )

    def test_o_detector_nao_acusa_portugues_legitimo(self):
        """O detector tem de passar em portugues bom.

        Um teste de mojibake que acusa `avô` nao e' um teste de mojibake,
        e' um detector de acentos. Este fixa essa fronteira, para a
        proxima pessoa nao "corrigir" o detector e ficar com 4069 falsos
        positivos.
        """
        LEGITIMOS = [
            "avô",
            "avó",
            "irmã",
            "irmão",
            "João",
            "mãe",
            "pão",
            "água",
            "cabeça",
            "coração",
            "órgão",
            "manhã",
            "Timor-Leste",
            "João Pessoa",
            "Belém",
        ]
        for s in LEGITIMOS:
            self.assertIsNone(
                C1.search(s),
                "'%s' tem um controlo C1? isso nao e' portugues." % s,
            )
            self.assertIsNone(
                AE_F.search(s),
                "'%s' tem o par Ãƒ? isso e' mojibake, nao portugues." % s,
            )

    def test_um_mojibake_real_e_detectado(self):
        """O detector tem de apanhar o caso real, nao so passar nele.

        Um detector que nunca falha tambem nao serve. Estes sao os casos
        MEDIDOS no DOM antes da correccao.
        """
        REAIS = [
            "ÃƒÂrea Total",
            "ÃƒÂ\x81rea Total",  # com o controlo C1
            "disponÃƒÂ­vel",
            "duplicaÃƒÂ§ÃƒÂ£o",
            "preferÃƒÂªncias",
        ]
        for s in REAIS:
            self.assertTrue(
                C1.search(s) or AE_F.search(s),
                "o detector NAO apanhou %r. Se passou, nao detecta "
                "mojibake nenhum." % s,
            )

    def test_pagina_index_nao_tem_mojibake(self):
        """O ficheiro onde isto foi encontrado, nomeado.

        O teste acima e' geral. Este diz explicitamente que
        `pagina-index.js` esta limpo, porque e' o ficheiro que mostrou o
        bug na tela. Se um dia voltar, o nome do ficheiro esta no erro.
        """
        p = JS / "pagina-index.js"
        self.assertTrue(p.exists(), "pagina-index.js nao existe onde se espera")
        t = p.read_text(encoding="utf-8", errors="replace")
        self.assertEqual(
            C1.findall(t),
            [],
            "pagina-index.js tem %d controlo(s) C1 — mojibake voltou"
            % len(C1.findall(t)),
        )
        self.assertEqual(
            AE_F.findall(t),
            [],
            "pagina-index.js tem %d par(es) Ãƒ — mojibake voltou"
            % len(AE_F.findall(t)),
        )


if __name__ == "__main__":
    unittest.main()
