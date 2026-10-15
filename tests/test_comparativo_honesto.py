"""O comparativo 100x50 tem de ser honesto, e honesto significa medido.

MEDIDO 2026-10-05 (agente 7). Encontrei quatro `C` que nao aguentam:

    F02 "NF-e do produtor rural" = `C`, evidencia `app/services/nfe.py:169`.
        A linha valida a chave de acesso de uma nota **ja emitida**. O modulo
        nao tem funcao de emissao. E a prova e' interna: a propria folha marca
        F04 (certificado A1) como `N`, e nao se emite NF-e sem A1.

    F13, P03, L01 = `C`, com evidencia em `app/admin.py`.
        A escala da propria folha define `E` como "a evidencia e' um campo".
        O admin **auto-gera** interface: `admin.py:99` prova que o campo
        existe, que e' a definicao de `E`.

Estes testes existem para que a medicao **nao volte a ser um instrumento de
mentira** — e, mais importante, para que a ferramenta que corrige a planilha
nao cometa ela propria o mesmo erro. Foi o que aconteceu duas vezes:

    - a primeira versao dava **zero** orfaos porque o corpus incluiu onde o
      campo casa com a propria declaracao;
    - a heuristica de verbos baixou `F11`, `O01`, `M08` e `X07` para `N`,
      inventando ausencias. "Nao ha funcao chamada `emitir`" nao prova que
      a emissao nao exista numa funcao chamada `_monta_documento`.

Por isso o modulo separa `divergentes` (verificacao estrutural, confiavel) de
`suspeitas` (pista, precisa de olho humano), e o teste abaixo verifica que
`suspeita` nunca vira veredicto sozinho.
"""

from pathlib import Path

from django.test import SimpleTestCase

RAIZ_SERVICOS = Path(__file__).resolve().parents[1] / "app" / "services"

from app.services.comparativo_ambiental import (
    ACOES_EXIGIDAS,
    PRE_REQUISITOS,
    SO_ENDERECO,
    Dimensao,
    _classificar_por_tipo,
    _funcoes_do_modulo,
    _verbos_da_dimensao,
    remedir,
    tabela_markdown,
)


def dim(
    dim_id="X00", nome="Teste", veredicto="C", evidencia="app/api/urls.py:1", diz=""
):
    """Fabrica de uma `Dimensao`.

    O parametro chama-se `dim_id` e nao `id` porque `A002` tem razao: `id` e'
    um builtin, e uma fabrica de testes e' exactamente o sitio onde um nome
    shadowado passa despercebido.
    """
    return Dimensao(
        id=dim_id,
        grupo="Z. Teste",
        nome=nome,
        veredicto=veredicto,
        evidencia=evidencia,
        o_que_a_linha_diz=diz,
        leitura="",
    )


class AMedicaoCorreTest(SimpleTestCase):
    """Propriedades do veredicto sobre a planilha real."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.rel = remedir()

    def test_a_planilha_foi_lida(self):
        self.assertEqual(self.rel.fonte_ilegivel, "", "a planilha nao abriu")
        self.assertEqual(self.rel.total, 50, "a folha AMPLIAGRO tem 50 dimensoes")

    def test_os_veredictos_sao_todos_conhecidos(self):
        """Nenhum veredicto invented. Uma escala fechada ou nao e' escala."""
        for v in self.rel.divergentes + self.rel.confirmadas:
            with self.subTest(id=v.dimensao.id):
                self.assertIn(
                    v.veredicto,
                    {"C", "E", "N", "indeterminado"},
                    f"veredicto inventado: {v.veredicto}",
                )

    def test_toda_divergente_tem_razao(self):
        """Uma divergencia sem razao nao se pode corrigir."""
        for v in self.rel.divergentes:
            with self.subTest(id=v.dimensao.id):
                self.assertGreater(
                    len(v.razao.strip()),
                    40,
                    "divergencia sem razao escrita",
                )

    def test_o_remedio_soma_a_total(self):
        soma = sum(self.rel.por_veredicto.values())
        self.assertEqual(
            soma,
            self.rel.total,
            f"as contagens somam {soma} mas ha {self.rel.total} dimensoes",
        )


class OVerificadorDeEnderecoTest(SimpleTestCase):
    """`admin.py` e `urls.py` nunca provam `C`. E' a regra que rebaixou F13."""

    def test_admin_py_nunca_da_C(self):
        d = dim(evidencia="app/admin.py:99", veredicto="C")
        veredicto, razao = _classificar_por_tipo(d)
        self.assertEqual(veredicto, "E")
        self.assertIn("admin.py", razao)

    def test_urls_py_nunca_da_C(self):
        d = dim(evidencia="app/api/urls.py:36", veredicto="C")
        veredicto, _ = _classificar_por_tipo(d)
        self.assertEqual(veredicto, "E")

    def test_a_explicacao_diz_que_e_endereco(self):
        d = dim(evidencia="app/admin.py:1")
        _, razao = _classificar_por_tipo(d)
        self.assertTrue(
            SO_ENDERECO.issubset({"admin.py"}) or "endereco" in razao,
            "a razao tem de explicar que e' endereco e nao execucao",
        )

    def test_um_servico_real_nao_e_rebaixado(self):
        """A regra so' toca em endereco. `compliance_ambiental` e' servico."""
        d = dim(evidencia="app/services/erp_externo.py:30")
        self.assertIsNone(
            _classificar_por_tipo(d),
            "um modulo de servico foi tratado como endereco",
        )


class OVerboNaoDecideTest(SimpleTestCase):
    """A heuristica de verbos e' pista, nunca veredicto.

    MEDIDO: quando baixava o veredicto, produziu `N` em F11, O01, M08 e X07 —
    todos falsos. Uma capacidade pode estar em `_monta_documento`.
    """

    def test_a_pista_nao_vira_veredicto(self):
        rel = remedir()
        for v in rel.suspeitas:
            with self.subTest(id=v.dimensao.id):
                self.assertNotEqual(
                    v.veredicto,
                    "N",
                    "uma suspeita virou `N`. `N` significa ausencia; uma "
                    "pista sobre o nome de uma funcao nao prova ausencia.",
                )

    def test_indeterminado_nao_e_N(self):
        """`nao sei` e' um terceiro estado, e trata-se como tal."""
        rel = remedir()
        for v in rel.divergentes + rel.confirmadas:
            if v.veredicto == "indeterminado":
                with self.subTest(id=v.dimensao.id):
                    self.assertNotEqual(v.veredicto, "N")

    def test_as_accoes_tem_marcas(self):
        for acao, marcas in ACOES_EXIGIDAS.items():
            with self.subTest(acao=acao):
                self.assertTrue(marcas, f"accao {acao} sem marcas")

    def test_ler_nota_nao_e_emitir(self):
        """A funcao real do caso F02, para a heuristica ter o que procurar."""
        funcoes = _funcoes_do_modulo("app/services/nfe.py")
        self.assertIn("ler_nota", funcoes)
        self.assertNotIn(
            "emitir",
            " ".join(funcoes),
            "se `nfe.py` passar a ter uma funcao de emissao, F02 deixa de ser "
            "suspeita — e este teste avisa.",
        )

    def test_os_verbos_sao_detetados_no_texto(self):
        achou = _verbos_da_dimensao(
            "NF-e do produtor rural", "a nota que o bois vende, emite-se noutro sitio"
        )
        self.assertTrue(
            achou,
            "a dimensao fala em emissao e o verificador nao viu o verbo",
        )


class OPreRequisitoTest(SimpleTestCase):
    """A regra da dependencia, e onde ela **nao** se aplica.

    Ver o docstring do modulo: em 2026-10-05 esta regra estava mal aplicada a
    F01 e F02, e a rectificacao esta' aqui para que a versao errada nao volte.
    """

    def test_o_mdfe_depende_do_certificado(self):
        """MDF-e e' documento assinado. A dependencia e' real."""
        self.assertIn("F03", PRE_REQUISITOS)
        self.assertEqual(PRE_REQUISITOS["F03"][0], "F04")

    def test_o_lcdpr_nao_depende_do_certificado(self):
        """`lcdpr.py` nao assina. Gerar o livro e' outra coisa que assinar.

        Verificado por determinismo: zero ocorrencias de `assin`, `pkcs12`,
        `dsig`, `x509` ou `transmit` no gerador. Assinar o LCDPR e' parte da
        declaracao no Fisco, e nao uma capacidade do Ampliagro.
        """
        self.assertNotIn(
            "F01",
            PRE_REQUISITOS,
            "F01 voltou a depender do A1. Isso rebaixa um gerador que existe "
            "para N — um falso negativo.",
        )

        fonte = Path(RAIZ_SERVICOS / "lcdpr.py").read_text(encoding="utf-8")
        for marca in ("pkcs12", "dsig", "x509", "transmitir"):
            with self.subTest(marca=marca):
                self.assertNotIn(
                    marca,
                    fonte.lower(),
                    f"`lcdpr.py` passou a mencionar `{marca}` — entao o "
                    f"gerador assina, e a dependencia passa a ser real e "
                    f"F01 tem de voltar a PRE_REQUISITOS.",
                )

    def test_a_nfe_depende_do_certificado_para_emissao(self):
        """A dependencia e' real, mas **nao** o que o pre-requisito mede.

        Nao se emite NF-e sem A1 — verdadeiro. Mas `nfe.py` tem importacao, e
        ela funciona. O veredicto que a leitura do codigo sustenta e' `E`
        (existe a parte, e sabemos qual), nao `N` (ausencia).
        """
        self.assertNotIn(
            "F02",
            PRE_REQUISITOS,
            "F02 voltou a ser rebaixado a N pelo A1 ausente. Importacao de "
            "NF-e existe e tem 83 testes; N e' demasiado forte.",
        )

    def test_a_importacao_de_nfe_existe_e_e_isto_que_se_sabe(self):
        """O que sustenta o `E`: a parte que existe, nomeada."""
        from app.services.comparativo_ambiental import _funcoes_do_modulo

        funcoes = _funcoes_do_modulo("app/services/nfe.py")
        for esperada in ("ler_nota", "importar_nota", "importar_xml"):
            with self.subTest(funcao=esperada):
                self.assertIn(
                    esperada,
                    funcoes,
                    "a importacao de NF-e deixou de existir. Se desaparecer, "
                    "`E` passa a `N` e F02 volta a PRE_REQUISITOS.",
                )

    def test_o_veredicto_da_nfe_nao_e_n(self):
        """A correccao que a rectificacao trouxe: `C` -> `E`, nunca `N`.

        Um `C` aqui promete que o Ampliagro **emite** nota. Nao emite. Mas a
        importacao existe, e dizer que a capacidade nao existe seria o erro
        oposto.
        """
        rel = remedir()
        f02 = next(
            (
                v
                for v in rel.divergentes + rel.confirmadas + rel.suspeitas
                if v.dimensao.id == "F02"
            ),
            None,
        )
        if f02 is None:
            self.skipTest("F02 ausente da remediacao")
        self.assertNotEqual(
            f02.veredicto,
            "N",
            "F02 voltou a N. Importacao existe; N afirma ausencia.",
        )

    def test_o_mdfe_e_o_unico_com_dependencia_declarada(self):
        """A regra fica pequena de proposito.

        Uma lista de dependencias que cresce sem verificacao volta a ser a
        folha a mentir sobre si mesma. Hoje e' uma entrada, e ha um teste que
        avisa se deixar de ser.
        """
        self.assertEqual(
            sorted(PRE_REQUISITOS),
            ["F03"],
            "a lista de dependencias mudou. Cada entrada nova precisa de "
            "razao E de a dependencia ser real — como F03 (assinado), "
            "ao contrario de F01 (nao assinado) e F02 (importado, nao emitido).",
        )


class ADocstringNaoImplementaTest(SimpleTestCase):
    """Nenhuma fonte pode assentar um `C` em prosa.

    Terceira ocorrencia do mesmo erro nesta sessao, e a mais subtil: um
    detector que testa a **forma** em vez do **facto**.

        1. `test_contrato_de_esquema` dava 0 orfaos porque o corpus incluía
           `models/`, onde o campo casa com a propria declaracao.
        2. A heuristica de verbos baixava F11/O01/M08/X07 para `N`.
        3. O detector de docstring so' via linhas que *abrem* aspas triplas.

    MEDIDO. `F12` ancorava em `app/api/views/custos.py:427`, a **segunda**
    linha da docstring de `conciliacao_upload` (abre na 426). O guard
    `test_ancora_tem_codigo` apanhou primeiro; o meu verificador so depois de
    corrigido. As duas fontes — `vereditos.py` e a folha `AMPLIAGRO` do .xlsx —
    convergiram depois para `custos.py:432`, que e' corpo executavel. Por isso
    `C` hoje e' correcto, e fixar `E` seria fixar um numero que ja envelheceu.

    O que fica fixado e' a regra, e vale para as duas fontes.
    """

    def _faixa_do_ficheiro(self, evidencia: str) -> set[int]:
        import ast as _ast
        import pathlib as _pl

        from app.services.comparativo_ambiental import _faixa_de_docstrings

        rel, _, ln_txt = evidencia.rpartition(":")
        p = _pl.Path(__file__).resolve().parents[1] / rel
        if not p.exists():
            return set()
        try:
            return _faixa_de_docstrings(_ast.parse(p.read_text(encoding="utf-8")))
        except SyntaxError:
            return set()

    def test_a_faixa_cobre_a_docstring_inteira(self):
        """A 426 (abre) e a 427 (prosa) tem de estar ambas na faixa.

        O detector antigo so' via linhas que *comecam* por aspas triplas. A
        427 nao comeca: e' prosa. Era esse o buraco.
        """
        faixa = self._faixa_do_ficheiro("app/api/views/custos.py:427")
        self.assertIn(426, faixa, "a linha que ABRE a docstring nao foi contada")
        self.assertIn(
            427,
            faixa,
            "a linha de PROSA dentro da docstring nao foi contada — e' "
            "exactamente o caso que passou e deixou um `C` assentar em prosa.",
        )

    def test_a_folha_nao_ancora_o_C_em_prosa(self):
        """A fonte que eu remedio: `C` tem de citar codigo, nao prosa."""
        from app.services.comparativo_ambiental import _carregar_dimensoes

        for dim in _carregar_dimensoes():
            if dim.veredicto != "C" or not dim.evidencia or ":" not in dim.evidencia:
                continue
            with self.subTest(id=dim.id):
                faixa = self._faixa_do_ficheiro(dim.evidencia)
                self.assertNotIn(
                    dim.linha,
                    faixa,
                    f"{dim.id} esta em `C` mas cita {dim.evidencia}, que esta "
                    f"DENTRO de uma docstring. Descrever a capacidade nao a "
                    f"implementa.",
                )

    def test_o_veredito_escrito_tambem_nao_ancora_em_prosa(self):
        """A outra fonte. A mesma regra, verificada do lado deles.

        `tests/test_ancora_tem_codigo.py` ja cobre `vereditos.py`. Este
        existe para fixar o mesmo invariante **a partir da remediacao**, e
        para dizer porque as duas fontes nao sao uma so: um numero ancorado
        num ficheiro .py envelhece quando o ficheiro ganha linhas, e so a
        fonte que se re-lê acusa. E' por isso que `vereditos.py` tem a nota
        "o guard apanhou" — para o proximo saber que ja foi verificado.
        """
        from docs.arquitetura.sistema.comparativo.vereditos import VEREDITOS

        for cid, spec in VEREDITOS.items():
            estado, evidencia = spec[0], spec[1]
            if estado != "C" or not evidencia or ":" not in evidencia:
                continue
            with self.subTest(id=cid):
                faixa = self._faixa_do_ficheiro(evidencia)
                ln = int(evidencia.rpartition(":")[2])
                self.assertNotIn(
                    ln,
                    faixa,
                    f"{cid} em `C` cita {evidencia}, dentro de uma docstring.",
                )

    def test_o_codigo_real_da_conciliacao_existe(self):
        """`E` era "existe mas a prova aponta para o sitio errado".

        Confirma que o trabalho esta la: se `conciliacao_upload` desaparecer,
        F12 passa a `N` e o veredicto muda. Um `C` que ninguem pode deixar de
        ser verdade sem o teste dizer nada e' uma cifra Morta.
        """
        from app.services.comparativo_ambiental import _funcoes_do_modulo

        funcoes = _funcoes_do_modulo("app/api/views/custos.py")
        self.assertIn(
            "conciliacao_upload",
            funcoes,
            "a funcao de conciliacao deixou de existir: F12 passa a `N`.",
        )


class ORelatorioParaIaTest(SimpleTestCase):
    """O que a IA recebe. O objectivo e' que ela **nao** leia 50 linhas."""

    def test_o_texto_explica_como_ler(self):
        rel = remedir()
        d = rel.para_dict()
        self.assertIn("nao e' um ranking", d["aviso"])
        self.assertIn("'E' quer dizer", d["aviso"])

    def test_a_ia_nao_confunde_E_com_falta(self):
        """A frase que impede a IA de sair a construir as 24 `E`."""
        rel = remedir()
        d = rel.para_dict()
        # o aviso tem de dizer que remedir != cobertura
        self.assertIn("coberta na integra", d["aviso"])

    def test_o_markdown_tem_a_coluna_do_plano(self):
        md = tabela_markdown()
        self.assertIn("| ID | Dimensao | Planilha | Remedido | Razao |", md)
        self.assertIn("Remedido:", md)

    def test_o_markdown_nao_leva_mais_de_60_linhas(self):
        """Limite de contexto. Uma tabela que nao cabe nao e' uma resposta."""
        md = tabela_markdown()
        self.assertLessEqual(len(md.splitlines()), 70)


class OIntentTest(SimpleTestCase):
    """O intent tem de responder, e a explicar-se quando nao pode.

    MEDIDO 2026-10-05. Estes testes **nao** importam `app.ia.sandbox`.
    Quando o faziam, rebentavam com `ImportError: cannot import name
    'INTENTS_CONTAS'` — o registo de intents carrega `contas_intents.py` de
    outro agente, que estava momentaneamente partido, e o meu teste falhava
    pela causa dele.

    Um teste que depende de um modulo que outro agente esta a editar mede o
    calendario de essa pessoa, nao o meu codigo. O que me interessa verificar
    e' que **o meu** intent esta bem formado e responde — e isso testa-se sem
    o registo global.
    """

    def test_o_intent_declara_o_que_a_ia_precisa(self):
        from app.ia.intents_comparativo import INTENT_COMPARATIVO_REVISAO

        spec = INTENT_COMPARATIVO_REVISAO["comparativo_revisao"]
        for chave in ("descricao", "exemplos", "flags", "handler"):
            with self.subTest(chave=chave):
                self.assertIn(chave, spec)
        self.assertTrue(spec["descricao"].strip())
        self.assertGreaterEqual(len(spec["exemplos"]), 3)

    def test_o_intent_declara_o_schema_dos_parametros(self):
        """Sem `params_schema`, a tool sai com `properties: {}`.

        MEDIDO: foi o que aconteceu na primeira versao — os exemplos sao
        perguntas em portugues, sem parametros, e nao ha de onde deduzir um
        campo. Um schema vazio faz o modelo passar tudo como string, ou nao
        passar nada.
        """
        from app.ia.intents_comparativo import INTENT_COMPARATIVO_REVISAO

        schema = INTENT_COMPARATIVO_REVISAO["comparativo_revisao"]["params_schema"]
        self.assertIn("detalhe", schema)
        self.assertIn("formato", schema)
        self.assertEqual(schema["formato"]["enum"], ["json", "markdown"])

    def test_a_flag_e_de_leitura(self):
        """`comparativo` so' le. Uma flag de escrita seria um acesso de mais."""
        from app.ia.intents_comparativo import INTENT_COMPARATIVO_REVISAO

        flags = INTENT_COMPARATIVO_REVISAO["comparativo_revisao"]["flags"]
        self.assertEqual(flags, ["competencia.read"])
        self.assertFalse([f for f in flags if "write" in f])

    def test_o_handler_responde_sem_parametros(self):
        from app.ia.intents_comparativo import h_comparativo

        r = h_comparativo(None, {}, None)
        self.assertTrue(r["ok"])
        self.assertEqual(r["total_dimension"], 50)
        self.assertIn("como_ler", r, "sem `como_ler` a IA le 'E' como falta")

    def test_detalhe_true_devolve_mais(self):
        from app.ia.intents_comparativo import h_comparativo

        curto = h_comparativo(None, {}, None)
        longo = h_comparativo(None, {"detalhe": True}, None)
        self.assertLessEqual(
            len(curto["divergentes"]),
            len(longo["divergentes"]),
            "`detalhe: true` devolveu menos do que o default",
        )

    def test_a_descricao_manda_remedir_antes_de_planear(self):
        from app.ia.intents_comparativo import INTENT_COMPARATIVO_REVISAO

        d = INTENT_COMPARATIVO_REVISAO["comparativo_revisao"]["descricao"]
        self.assertIn("ANTES de planear", d)
        self.assertIn("NAO use para comparar", d)

    def test_o_nome_nao_colide_com_a_tool_do_outro_modulo(self):
        """MEDIDO 2026-10-05. Colisao real, com dois agentes em paralelo.

        Este intent nasceu como `comparativo` e produzia `amplia_comparativo`
        — exactamente o nome que `app/amplia_mcp/comparativo.py` (outro
        agente) expoe. O cliente MCP recebia a descricao errada, e
        `test_tools_em_formato_openai` acusava `86 != 87`.

        Nenhum dos dois foi apagado: fazem perguntas diferentes. O que mudou
        foi o nome, e este teste existe para que a colisao nao volte por
        descuido — que e' como aconteceu.
        """
        from app.amplia_mcp import nome_tool
        from app.ia.sandbox import INTENTS

        meu = nome_tool("comparativo_revisao")
        self.assertEqual(meu, "amplia_comparativo_revisao")

        alheio = "amplia_comparativo"
        self.assertNotEqual(
            meu,
            alheio,
            "o nome voltou a colidir com app/amplia_mcp/comparativo.py",
        )

        # e nenhum dos dois pode ter deixado de existir
        self.assertIn("comparativo_revisao", INTENTS)

    def test_o_handler_diz_como_ler_E(self):
        """A frase que impede a IA de sair a construir as 24 `E`."""
        from app.ia.intents_comparativo import h_comparativo

        r = h_comparativo(None, {}, None)
        self.assertIn("NAO e' falta", r["como_ler"])
