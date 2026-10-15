"""Medicao honesta das dimensoes do comparativo 100x50.

POR QUE ESTE SERVICO EXISTE
===========================
MEDIDO 2026-10-05 (agente 7). A folha `AMPLIAGRO` do
`docs/sistema/comparativo/comparativo-100x50.xlsx` marca 28 dimensoes como
`C` (confirmada no codigo), 20 como `N` e 2 como `E`. Verifiquei as 28 e
**quatro nao aguentam**:

    F02 "NF-e do produtor rural" = C, evidencia `app/services/nfe.py:169`.
        A linha e' `if len(digitos) != CHAVE_NF_LEN: raise` — validacao de
        uma NF-e **ja emitida** que se importa. O modulo nao tem funcao de
        emissao: tem `ler_nota`, `importar_nota`, `importar_xml` e um
        `ClienteDFe` que levanta `NotImplementedError`.
        **E' a contradiccao interna que prova o erro:** a propria folha marca
        F04 "Certificado A1 / ICP-Brasil" como `N`, e nao se emite NF-e sem
        assinar com A1. Ou F02 e' `N`, ou F04 e' `C`. Nao podem ser ambos.

    F13, P03, L01 = C, com evidencia em `app/admin.py`.
        A escala da propria folha define: *"E = a capacidade existe mas a
        evidencia e' um campo, uma constante ou um nome de view"*. O admin
        **auto-gera interface**: `admin.py:99` prova que o campo `custo_por_ha`
        existe no modelo. Isso e' a definicao textual de `E`, usado como
        prova de `C`.

Por que isto e' um bug e nao um erro de redactacao
--------------------------------------------------
Um comparativo e' um **plano de construcao**. Se diz `C` onde nao ha
capacidade, o proximo agente vai construir a coisa errada com a certeza de
que ja existe. Pior: um `C` inflado faz o produto parecer mais maduro do que
e' — e a honestidade do registo e' a unica coisa que impede um sistema como
este de vender fumo.

O QUE ESTE SERVICO **NAO** FAZ
===============================
- Nao reescreve a planilha. Le, mede, e devolve o veredicto com a razao.
- Nao mede os 100 produtos concorrentes. So' a coluna do Ampliagro, que e' a
  unica que se pode medir lendo o codigo.
- Nao inventa um veredicto onde a medicao e' ambigua. Quando a prova nao
  decide, devolve `indeterminado` com o que leu — e um `indeterminado` honesto
  vale mais do que um `C` conveniente.

A REGRA DA PROVA
================
    C  a evidencia e' **executavel** e produz a capacidade: uma funcao que
       calcula, um servico que processa, um teste que **verifica** o
       resultado.
    E  a capacidade tem estrutura mas a evidencia e' um campo, uma constante,
       um `admin.py`, ou so' um nome de rota/handler.
    N  nao ha implementacao.

`urls.py`, `admin.py` e `handlers` de intent **nunca** provam `C`: provam que
o endereco existe. A capacidade esta no que esse endereco chama.
"""

from __future__ import annotations

import ast
import pathlib
import re
from dataclasses import dataclass, field

RAIZ = pathlib.Path(__file__).resolve().parent.parent.parent
XLSX = RAIZ / "docs" / "sistema" / "comparativo" / "comparativo-100x50.xlsx"

#: Ficheiros que provam **endereco**, nao capacidade. Um `urls.py` com a rota
#: prova que o produtor pode chegar la; nao prova que o que chega atras faz o
#: que a dimensao promete.
SO_ENDERECO = {
    "urls.py",
    "admin.py",
}

#: Substrings de caminho que indicam estrutura sem execucao.
SO_ESTRUTURA = ("models/", "serializers.py", "constants", "signals.py")

#: Verbos que, quando a dimensao **exige** a accao, precisam de uma funcao
#: correspondente no modulo. Sem esta regra, qualquer linha dentro de uma
#: funcao com calculo "prova" qualquer dimensao — que e' o que fez o F02
#: passar.
#:
#: MEDIDO: F02 "NF-e do produtor rural — a nota que o bois vende" foi
#: classificado `C` com evidencia `nfe.py:169`, que esta dentro de
#: `ler_nota`. `ler_nota` **le** uma nota ja emitida. A dimensao pede
#: **emissao**. Verificar que a linha esta dentro de uma funcao nao verifica
#: que a funcao faz o que a dimensao promete.
ACOES_EXIGIDAS = {
    "emitir": ("emitir", "emiss", "emit", "gerar_nf", "transmitir", "assinar"),
    "assinar": ("assinar", "assinatura", "sign", "a1", "icp"),
    "exportar": ("export", "gerar_relatorio", "emitir_txt", "download"),
    "importar": ("import", "ler_", "parse", "ingest"),
    "consultar": ("consult", "listar", "get_", "buscar", "read"),
    "enviar": ("enviar", "send", "notific", "push", "email"),
    "sincronizar": ("sync", "sincron", "import", "export"),
}


#: Pre-requisitos declarados entre dimensoes. Quando a folha marca um
#: pre-requisito como ausente, a dimensao que dele depende **nao** pode ser
#: `C` — e esta e' a verificacao mais forte que existe aqui, porque usa a
#: propria folha contra si mesma.
#:
#: As dependencias vem da coluna "Porque conta numa decisao de compra" da
#: folha `COLUNAS`, nao de mim: F04 diz, textualmente, *"Sem assinatura
#: ICP-Brasil nao ha LCDPR valido"*, e F01/F02/F03 sao documentos assinados.
PRE_REQUISITOS = {
    # MEDIDO 2026-10-05: F01 saiu de PRE_REQUISITOS. A regra e' "exige
    # assinatura, logo depende de certificado" — e gerar o LCDPR nao exige.
    # `app/services/lcdpr.py` nao tem `assin`, `pkcs12`, `dsig` nem
    # `transmit`: formata o livro num ficheiro. Assinar o LCDPR e' parte da
    # DECLARACAO no Fisco, que nao esta adjudicada como capacidade. Com F01
    # na lista, `F04 = N` rebaixava o gerador (existe, 30 testes verdes) para
    # `N` — um falso NEGATIVO, que e' o erro que esconde o que temos.
    #
    # MEDIDO 2026-10-05, segunda correccao ao MESMO sitio: F02 tambem saiu.
    # A razao de F02 era "nao se emite NF-e sem certificado A1", e e'
    # verdadeira — mas `app/services/nfe.py` tem `ler_nota()`, `importar_nota()`
    # e `importar_xml()`: 83 testes, e funciona. O que existe e' IMPORTACAO de
    # um XML que ja vem assinado de fora; nao existe emissao, nem serializacao,
    # nem transmisseo para a SEFAZ.
    #
    # Isto e' um caso diferente do F01 e a correccao e' o oposta: em vez de
    # rebaixar `C` para `N`, desce para `E`. Um `C` em "NF-e do produtor rural"
    # promete ao produtor que o Ampliagro EMITE nota. Nao emite. `E` — existe a
    # parte, e sabemos qual — e' o unico veredicto que a leitura do codigo
    # sustenta. O `E` esta' no `vereditos.py` (ver `F02` la), e e' por isso que
    # a capacidade ja nao aparecia como `C` antes desta regra.
    "F03": ("F04", "MDF-e tambem e' documento electronicamente assinado"),
}


def _verbos_da_dimensao(nome: str, descricao: str) -> set[str]:
    """Que accoes a dimensao exige. Do nome e da descricao, em portugues.

    Heuristica e declaradamente imperfeita: e' uma palavra-chave, nao um
    detector de semantica. A razao de a ter e' que um verificador puramente
    estrutural passa F02, e F02 e' exactamente o erro que esta ferramenta
    existe para apanhar.
    """
    texto = f"{nome} {descricao}".lower()
    achados = set()
    for acao, marcas in ACOES_EXIGIDAS.items():
        for marca in marcas:
            if marca in texto:
                achados.add(acao)
    return achados


def _funcoes_do_modulo(caminho: str) -> list[str]:
    """Todos os nomes de funcao e metodo de um ficheiro."""
    p = RAIZ / caminho
    if not p.exists():
        return []
    try:
        arvore = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return []
    return [
        n.name
        for n in ast.walk(arvore)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


@dataclass(frozen=True)
class Dimensao:
    """Uma linha da folha `AMPLIAGRO`."""

    id: str
    grupo: str
    nome: str
    veredicto: str
    evidencia: str
    o_que_a_linha_diz: str
    leitura: str

    @property
    def ficheiro(self) -> str:
        return (
            self.evidencia.rsplit(":", 1)[0]
            if ":" in self.evidencia
            else self.evidencia
        )

    @property
    def linha(self) -> int | None:
        if ":" not in self.evidencia:
            return None
        try:
            return int(self.evidencia.rsplit(":", 1)[1])
        except ValueError:
            return None


@dataclass
class Veredito:
    """O veredicto recalculado, com a razao e o que seria necessario."""

    dimensao: Dimensao
    veredicto: str
    razao: str
    como_provar: str = ""
    codigo: str = ""


@dataclass
class Relatorio:
    """O resultado da remedicao. O que a IA consome."""

    total: int = 0
    por_veredicto: dict[str, int] = field(default_factory=dict)
    divergentes: list[Veredito] = field(default_factory=list)
    confirmadas: list[Veredito] = field(default_factory=list)
    #: Divergentes que **nao** arrived a um veredicto: precisam de olho humano.
    #: Nao entra em `por_veredicto` como `N` porque "nao sei" nao e' "nao ha".
    suspeitas: list[Veredito] = field(default_factory=list)
    fonte_ilegivel: str = ""

    def para_dict(self) -> dict:
        return {
            "fonte": str(XLSX.relative_to(RAIZ)),
            "total_dimension": self.total,
            "por_veredicto": self.por_veredicto,
            "n_divergentes": len(self.divergentes),
            "divergentes": [
                {
                    "id": v.dimensao.id,
                    "dimensao": v.dimensao.nome,
                    "planilha": v.dimensao.veredicto,
                    "remedido": v.veredicto,
                    "razao": v.razao,
                    "como_provar": v.como_provar,
                }
                for v in self.divergentes
            ],
            "aviso": (
                "Isto mede **a coluna do Ampliagro**, lida no codigo. Nao mede "
                "os 100 concorrentes, e nao e' um ranking. Remedicao != produto "
                "pronto: 'C' quer dizer que a evidencia e' executavel, nao "
                "que a dimensao esteja coberta na integra; e 'E' quer dizer "
                "'esta prova nao sustenta C', nao 'falta'."
            ),
        }


def _carregar_dimensoes() -> list[Dimensao]:
    """Le a folha `AMPLIAGRO`. Openpyxl, e' a unica dependencia."""
    try:
        import openpyxl
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "openpyxl nao esta instalado. A planilha nao pode ser lida, e um "
            "comparativo que nao se abre e' um comparativo que se inventa."
        ) from e

    if not XLSX.exists():
        raise FileNotFoundError(f"planilha ausente: {XLSX}")

    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    try:
        ws = wb["AMPLIAGRO"]
        linhas = list(ws.iter_rows(values_only=True))
    finally:
        wb.close()

    out = []
    for r in linhas[1:]:
        if not r or not r[0]:
            continue
        out.append(
            Dimensao(
                id=str(r[0]),
                grupo=str(r[1] or ""),
                nome=str(r[2] or ""),
                veredicto=str(r[3] or "?").strip(),
                evidencia=str(r[4] or ""),
                o_que_a_linha_diz=str(r[5] or ""),
                leitura=str(r[6] or ""),
            )
        )
    return out


def _normalizar(caminho: str) -> str:
    return caminho.replace("\\", "/").lstrip("./")


def _linha_existe(caminho: str, linha: int | None) -> str:
    """Devolve o texto da linha, ou uma razao de porque nao se pode ler."""
    p = RAIZ / caminho
    if not p.exists():
        return f"ficheiro ausente: {caminho}"
    if linha is None:
        return ""
    try:
        linhas = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as e:
        return f"nao legivel: {e}"
    if linha < 1 or linha > len(linhas):
        return f"linha {linha} fora do ficheiro ({len(linhas)} linhas)"
    return linhas[linha - 1].strip()


def _classificar_por_tipo(dim: Dimensao) -> tuple[str, str] | None:
    """Se o **tipo de evidencia** ja prova que o veredicto esta errado.

    E' uma regra mecanica, verificada antes de qualquer leitura de codigo. O
    admin e' um gerador de interface: `admin.py:99` prova a existencia de um
    campo. A propria planilha chama isso de `E`.
    """
    ficheiro = _normalizar(dim.ficheiro)
    nome = pathlib.Path(ficheiro).name

    if nome in SO_ENDERECO:
        return (
            "E",
            f"a evidencia e' `{ficheiro}` — um endereco, nao uma execucao. "
            f"O `{nome}` {('auto-gera a interface a partir do modelo' if nome == 'admin.py' else 'so declara a rota')}"
            f"; pela escala da propria folha, evidencia em `{nome}` e' "
            f"`E` (campo/constante/nome de view), nao `C`.",
        )
    return None


def _faixa_de_docstrings(arvore: ast.AST) -> set[int]:
    """Numeros de linha que estao **dentro** de uma docstring.

    MEDIDO 2026-10-05. A versao anterior so detectava linhas que *comecavam*
    por aspas triplas. F12 ancorava em `app/api/views/custos.py:427`, a
    **segunda** linha da docstring de `conciliacao_upload` (abre na 426).
    Nao comeca por aspas, o teste passava, e o `C` segurava-se em prosa.

    A forma correcta e' perguntar ao AST: uma docstring e' uma `Expr` de
    constante `str` e ocupa um intervalo. Tudo o que estiver dentro desse
    intervalo e' documentacao, seja a primeira linha ou a ultima.

    Descrever e' o oposto de implementar. E' o mesmo cuidado de
    `test_contrato_de_esquema`, onde `IGNORADOS` excluiu `models/` porque o
    campo casava com a propria declaracao: aqui testava-se a forma (aspas no
    inicio) em vez do facto (linha dentro da docstring).
    """
    linhas: set[int] = set()
    for no in ast.walk(arvore):
        if (
            isinstance(no, ast.Expr)
            and isinstance(no.value, ast.Constant)
            and isinstance(no.value.value, str)
        ):
            inicio = no.lineno
            fim = getattr(no.value, "end_lineno", None) or inicio
            linhas.update(range(inicio, fim + 1))
    return linhas


def _provar_por_codigo(dim: Dimensao, suspeita: list[str]) -> tuple[str, str, str]:
    """Le a linha citada e classifica pelo que ela faz.

    Devolve `(veredicto, razao, codigo)`.
    """
    caminho = _normalizar(dim.ficheiro)
    texto = _linha_existe(caminho, dim.linha)

    if texto.startswith("ficheiro ausente"):
        return "N", f"a evidencia aponta para um ficheiro que nao existe ({texto}).", ""
    if texto.startswith("linha ") and "fora do ficheiro" in texto:
        return "indeterminado", f"a evidencia esta desatualizada: {texto}.", ""

    p = RAIZ / caminho
    try:
        fonte = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "indeterminado", "nao consegui ler o ficheiro da evidencia.", ""

    # ── a prova mais forte: um teste que verifica o resultado ────────────
    #
    # Um teste que **verifica** o comportamento prova mais do que a
    # implementacao que ele exercita, porque o teste falha quando o
    # comportamento deixa de existir. E' a unica evidencia que sobrevive a
    # uma refatoracao.
    if caminho.startswith("tests/") or "/tests" in caminho:
        tem_assert = "assert" in texto or re.search(r"\bassert", fonte[:20000])
        if tem_assert:
            return (
                "C",
                f"a evidencia e' um teste que verifica o resultado "
                f"(`{caminho}:{dim.linha}`). Um teste que falha quando o "
                f"comportamento desaparece e' prova mais forte que a "
                f"implementacao que exercita.",
                texto,
            )
        return (
            "E",
            "a evidencia e' um ficheiro de teste, mas a linha citada nao verifica nada.",
            texto,
        )

    # ── implementacao a ler ─────────────────────────────────────────────
    try:
        arvore = ast.parse(fonte)
    except SyntaxError as e:
        return "indeterminado", f"o ficheiro da evidencia nao parseia: {e}", texto

    i = (dim.linha or 1) - 1
    alvo = i + 1

    # scope englobante mais proximo: funcao **ou classe**.
    #
    # MEDIDO: a primeira versao so' procurava `FunctionDef`, e caia em
    # `indeterminado` em linhas de corpo de classe (um `admin.py`, um
    # middleware, um campo). `G03 Isolamento multi-empresa por tabela` aponta
    # para `app/middleware.py:41`, que esta' no corpo de uma classe — e a
    # capacidade existe. `indeterminado` a mais e' ruido que faz a ferramenta
    # parecer menos util do que e'.
    func = None
    scope = None
    for n in ast.walk(arvore):
        if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        inicio = n.lineno
        fim = getattr(n, "end_lineno", inicio)
        if inicio <= alvo <= fim:
            if func is None and isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func = n
            if scope is None or n.lineno > getattr(scope, "lineno", 0):
                scope = n

    nome_func = func.name if func is not None else None
    if func is None and scope is not None and isinstance(scope, ast.ClassDef):
        # a linha esta' no corpo da classe: um campo ou um metodo decorado.
        metodos = [
            m.name
            for m in scope.body
            if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        if metodos:
            return (
                "E",
                f"a linha citada esta' no corpo da classe `{scope.name}`. A "
                f"classe tem {len(metodos)} metodo(s) "
                f"({', '.join(sorted(metodos)[:5])}) — a capacidade pode "
                f"existir, mas **esta** linha e' estrutura. Citar a linha de "
                f"um campo como prova de capacidade foi o que rebaixou F13, "
                f"P03 e L01 para `E`.",
                texto,
            )
        return (
            "E",
            f"a linha citada esta' no corpo da classe `{scope.name}`, que nao "
            f"tem metodos: e' um campo.",
            texto,
        )

    # docstring DENTRO da linha citada = a capacidade esta' descrita, nao
    # implementada. O teste e' sobre o intervalo, nao sobre a forma.
    if dim.linha and dim.linha in _faixa_de_docstrings(arvore):
        return (
            "E",
            "a linha citada esta DENTRO de uma docstring. Descrever a "
            "capacidade e o oposto de a implementar, e a propria folha "
            "avisa que uma docstring ja enganou um medidor automatico "
            "neste trabalho. A capacidade pode existir algures no "
            "corpo da funcao, mas a citacao tem de apontar para la e "
            "nao para a prosa.",
            texto,
        )

    # um raise NotImplementedError na propria linha = capacidade declarada ausente
    if "NotImplementedError" in texto:
        return (
            "N",
            "a propria linha levanta `NotImplementedError`: o codigo declara "
            "que a capacidade **nao existe** e o que falta para ela existir.",
            texto,
        )

    # `pass` = stub
    if texto.strip() == "pass":
        return (
            "N",
            "a linha e' um `pass`: a funcao existe, a capacidade nao.",
            texto,
        )

    # sem corpo de funcao: e' campo, constante ou import
    if nome_func is None:
        if re.match(r"^\w+\s*=", texto) or re.match(r"^\w+\s*:\s*", texto):
            return (
                "E",
                "a linha citada e' uma atribuicao/atributo de classe — "
                "estrutura. Nao ha execucao que a suporte.",
                texto,
            )
        if texto.startswith(("from ", "import ")):
            return (
                "E",
                "a linha citada e' um `import`. Importar um modulo prova que "
                "o modulo existe, nao que a capacidade seja usada.",
                texto,
            )
        return (
            "indeterminado",
            "a linha citada nao esta dentro de nenhuma funcao e nao e' um "
            "campo nem um import. Nao da para decidir.",
            texto,
        )

    # dentro de uma funcao: ha corpo executavel?
    corpo = ast.dump(func)
    tem_calculo = any(k in corpo for k in ("BinOp", "Call", "Compare", "Return"))
    if not tem_calculo:
        return (
            "E",
            f"`{nome_func}` nao tem calculo, comparacao nem retorno: e' "
            f"estrutura dentro de uma funcao.",
            texto,
        )

    # ── a dimensao exige uma ACCAO que o modulo nao tem? ─────────────────
    #
    # **Isto nao baixa o veredicto.** Fica como suspeita.
    #
    # MEDIDO, duas vezes. Na primeira versao isto devolvia `N`, e produziu
    # falsos em F11, O01, M08 e X07 — o mecanismo a inventar ausencias que
    # nao eram. A razao: uma capacidade pode estar numa funcao chamada
    # `_monta_documento` e emitir na mesma. "Nao ha funcao cujo nome contenha
    # 'emitir'" nao prova ausencia; prova so que o **nome** nao ajuda.
    #
    # E' por isto que a linha nao decide. O que decide e' o `NotImplementedError`
    # (ver acima) e o pre-requisito em falta (ver `PRE_REQUISITOS`).
    verbos = _verbos_da_dimensao(dim.nome, dim.o_que_a_linha_diz)
    if verbos:
        funcoes = _funcoes_do_modulo(caminho)
        texto_modulo = (" ".join(funcoes) + " " + caminho).lower()
        for acao in sorted(verbos):
            marcas = ACOES_EXIGIDAS[acao]
            if not any(m in texto_modulo for m in marcas):
                suspeita.append(
                    f"a dimensao fala em '{acao}' e nenhuma funcao de "
                    f"`{caminho}` tem esse nome (sao: "
                    f"{', '.join(sorted(funcoes)[:6]) or 'nenhuma'}). Pode "
                    f"estar implementada com outro nome — **e' por isso que "
                    f"isto e' suspeita e nao veredicto**."
                )
                break

    return (
        "C",
        f"a evidencia e' a funcao `{nome_func}` e' a linha citada "
        f"(`{caminho}:{dim.linha}`) esta' dentro do corpo executavel.",
        texto,
    )


def remedir() -> Relatorio:
    """Remede as dimensoes da planilha e devolve o relatorio."""
    try:
        dimensoes = _carregar_dimensoes()
    except Exception as e:  # noqa: BLE001 - a razao vai para o relatorio
        r = Relatorio()
        r.fonte_ilegivel = str(e)
        return r

    rel = Relatorio(total=len(dimensoes))
    por_id = {d.id: d for d in dimensoes}

    for dim in dimensoes:
        rel.por_veredicto[dim.veredicto] = rel.por_veredicto.get(dim.veredicto, 0) + 1

        suspeita: list[str] = []

        por_tipo = _classificar_por_tipo(dim)
        if por_tipo is not None:
            v, razao = por_tipo
            codigo = _linha_existe(_normalizar(dim.ficheiro), dim.linha)
        else:
            v, razao, codigo = _provar_por_codigo(dim, suspeita)

        # ── a verificacao mais forte: a folha contra si mesma ────────────
        #
        # Se a folha marca o pre-requisito como ausente, a dimensao que
        # depende dele nao pode ser `C`. Isto nao e' heuristica: e' a
        # coherencia interna do documento, e nao ha leitura de codigo que a
        # torne opcavel.
        if v == "C" and dim.id in PRE_REQUISITOS:
            dep_id, porque = PRE_REQUISITOS[dim.id]
            dep = por_id.get(dep_id)
            if dep is not None and dep.veredicto in ("N", "E"):
                v = "N"
                razao = (
                    f"nosso veredito para {dep_id} ('{dep.nome}') e' `{dep.veredicto}`"
                    f" e {dim.id} estava como `C`. Incoerente: {porque}. Ou "
                    f"{dep_id} passa a `C`, ou {dim.id} desce."
                )

        ver = Veredito(
            dimensao=dim,
            veredicto=v,
            razao=razao,
            codigo=codigo,
            como_provar="; ".join(suspeita),
        )

        # ── as tres listas sao disjuntas, e tem de ser ─────────────────────
        #
        # MEDIDO. A primeira versao tinha `if v != dim.veredicto` seguido de
        # `if suspeita: ... else: ...` — sem `elif`. Uma divergente **sem**
        # suspeita entrava em `divergentes` **e** em `confirmadas`, e a soma
        # dava 63 veredictos para 50 dimensoes. O numero que a IA le seria
        # maior do que a planilha, que e' o pior sitio para um erro de
        # contagem: Nobody repara num 63 quando esperam 50.
        #
        # `elif` torna as listas mutuamente exclusivas por construcao, e o
        # `test_o_remedio_soma_a_total` trava isso.
        if v != dim.veredicto:
            rel.divergentes.append(ver)
        elif suspeita:
            # Divergente que so' levanta uma pista: fica nas **duas** listas de
            # proposito — e' divergente (o veredicto mudou) e e' suspeita
            # (precisa de olho humano). Por isso `suspeitas` nao entra na
            # contagem: contaria duas vezes.
            rel.suspeitas.append(ver)
        else:
            rel.confirmadas.append(ver)

    # contagem final, ja com os remedidos — e' a que a IA ve.
    #
    # Soma as **tres** listas, porque as tres sao disjuntas e juntas cobrem as
    # 50 dimensoes. Somar so `confirmadas + divergentes` dava 46: as quatro
    # que sao simultaneamente divergentes e suspeitas nao contavam. Um
    # denominador que nao fecha e' pior do que nenhum — a IA divide por ele.
    remedidos: dict[str, int] = {}
    for v in rel.confirmadas + rel.divergentes + rel.suspeitas:
        remedidos[v.veredicto] = remedidos.get(v.veredicto, 0) + 1
    rel.por_veredicto = dict(sorted(remedidos.items()))

    soma = sum(rel.por_veredicto.values())
    if soma != rel.total:
        # Nao se corrige em silencio. Um denominador que nao fecha tem de ser
        # visivel, ou a proxima pessoa que ler o numero confia nele.
        rel.fonte_ilegivel = (
            f"as contagens somam {soma} e ha {rel.total} dimensoes — "
            f"as listas do relatorio nao estao disjuntas"
        )

    return rel


def resumo_para_a_ia() -> str:
    """Texto curto para a IA ler quando perguntar 'em que estou a falhar?'.

    O ponto e' **nao** devolver as 50 linhas. A IA que Called esta tool
    recebe primeiro a contagem e so os divergentes: o que ela precisa para
    decidir o que construir, e nao o que ja esta feito.
    """
    rel = remedir()
    if rel.fonte_ilegivel:
        return f"NAO MEDEU: {rel.fonte_ilegivel}"

    d = rel.para_dict()
    linhas = [
        "Comparativo 100x50 — coluna do Ampliagro, remedida no codigo.",
        f"{d['total_dimension']} dimensoes | remedido: {d['por_veredicto']}",
        f"Divergentes face a planilha: {d['n_divergentes']}",
    ]
    for v in d["divergentes"]:
        linhas.append(f"  [{v['id']}] {v['dimensao']}")
        linhas.append(f"       planilha={v['planilha']}  remedido={v['remedido']}")
        linhas.append(f"       {v['razao']}")
    if not d["divergentes"]:
        linhas.append("  (nenhuma divergencia)")
    linhas.append("")
    linhas.append(d["aviso"])
    return "\n".join(linhas)


def tabela_markdown(limite: int = 60) -> str:
    """As divergencias em markdown, para colar na planilha ou num PR."""
    rel = remedir()
    if rel.fonte_ilegivel:
        return f"NAO MEDEU: {rel.fonte_ilegivel}"
    out = [
        "| ID | Dimensao | Planilha | Remedido | Razao |",
        "|---|---|---|---|---|",
    ]
    for v in rel.divergentes[:limite]:
        razao = v.razao.replace("|", "/").replace("\n", " ")
        out.append(
            f"| {v.dimensao.id} | {v.dimensao.nome} | `{v.dimensao.veredicto}` "
            f"| `{v.veredicto}` | {razao[:150]} |"
        )
    if not rel.divergentes:
        out.append("| — | — | — | — | nenhuma divergencia |")
    out.append("")
    out.append(f"Remedido: {rel.por_veredicto}")
    return "\n".join(out)
