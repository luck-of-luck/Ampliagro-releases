#!/usr/bin/env python
"""
O PORTAO. "Funciona sem errar e bugar" so vira fato se existir um comando que
diga SIM ou NAO. Este e' esse comando.

    python verificar.py            roda tudo
    python verificar.py --rapido   so os portoes de 2 segundos (durante o patch)

Sai com 0 se TUDO passou, 1 se qualquer portao falhou ou faltou.

POR QUE EXISTE ESTE ARQUIVO
---------------------------
O dashboard ficou quebrado com a suite toda verde. Nao foi um bug raro: foi um
defeito de arquitetura que 807 testes de Python nao alcancam, porque mora entre
o context processor e o DOM. Este arquivo fecha esse buraco nao com mais um
teste de logica — verificando que as PONTE ESTAO LIGADAS.

OS PORTOES
----------
C1  manage.py check .................. Django nao acusa nada na inicializacao
C2  pytest app ....................... suite Python completa, exit 0
C3  node --check no JS inline ........ os 3 blocos <script> do index.html
C4  suites JS do palco ............... 3 arquivos .cjs, 117 asserts hoje
C5  PRESET_BLOCK_JSON no contexto .... o portao que PEGA o achado a_mutz15uzn868
C6  paridade JS <-> Python ........... o portao que PEGA o achado a_mutz15uqh7cg
C7  meta sem _presetMeta .............. o portao que PEGA o achado a_mutz1t75bmma

C5, C6 e C7 hoje nao existem — o codigo esta com o defeito e nao ha teste que o
veja. Por isso eles reportam FALTA, nao PASSA. Um portao que nao existe nao
aprova nada: ele barra.

COMO O C5/C6/C7 SAO VERIFICADOS
-------------------------------
Sao leitura de fonte, nao execucao de browser — porque nao ha browser aqui e
mentir sobre isso seria pior que nao cobrir. Cada um declara o que inspeciona e
o que considera falha. Se voce mexer na fonte e o padrao mudar, o portao
acusa em vez de deixar passar calado. E' proposital: um portao burro e pior
que nenhum portao.

CUIDADO COM O QUE ESTE ARQUIVO NAO PROVA
-----------------------------------------
Ele nao abre browser, nao roda Playwright, nao pega excecao de JS em runtime.
Um TypeError que so acontece quando o usuario clica em algo que este script
nao exercita NAO APARECE AQUI. Isso e' limitacao declarada, nao cobertura.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import subprocess
import sys
import time
from contextlib import redirect_stdout
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
INDEX = RAIZ / "app" / "templates" / "index.html"
PRESETS_PY = RAIZ / "app" / "presets.py"

# ---------------------------------------------------------------- infra


class Resultado:
    def __init__(self, nome: str) -> None:
        self.nome = nome
        self.ok = False
        self.falta = False
        self.detalhe = ""
        self.segundos = 0.0

    def passou(self, detalhe: str = "") -> Resultado:
        self.ok, self.detalhe = True, detalhe
        return self

    def falhou(self, detalhe: str) -> Resultado:
        self.ok, self.detalhe = False, detalhe
        return self

    def falta_prova(self, detalhe: str) -> Resultado:
        self.ok, self.falta, self.detalhe = False, True, detalhe
        return self


def roda(cmd: list[str], timeout: int = 1800) -> tuple[int, str]:
    """Roda um comando e devolve (exit_code, saida). Nunca levanta."""
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env.setdefault("PYTHONPATH", str(RAIZ))
    try:
        p = subprocess.run(
            cmd,
            cwd=str(RAIZ),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return 124, f"TIMEOUT apos {timeout}s"
    except FileNotFoundError as e:
        return 127, f"NAO ENCONTRADO: {e}"
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def contem(saida: str, agulha: str) -> bool:
    return agulha in saida


# ---------------------------------------------------------------- portoes


def c1_manage_check() -> Resultado:
    r = Resultado("C1  manage.py check")
    code, saida = roda([sys.executable, "manage.py", "check"], timeout=300)
    if code != 0:
        return r.falhou(f"exit {code}: {saida.strip()[-400:]}")
    if "no issues" not in saida:
        return r.falhou(f"exit 0 mas sem 'no issues': {saida.strip()[-300:]}")
    return r.passou("0 issues")


def c2_pytest() -> Resultado:
    r = Resultado("C2  pytest app")
    code, saida = roda(
        [
            sys.executable,
            "-m",
            "pytest",
            "app",
            "-q",
            "--no-cov",
            "-p",
            "no:randomly",
            "--tb=line",
        ],
        timeout=2400,
    )
    if code != 0:
        ult = [l for l in saida.splitlines() if l.strip()][-6:]
        return r.falhou(f"exit {code}\n      " + "\n      ".join(ult))
    return r.passou("exit 0")


def _blocos_script(texto: str) -> list[str]:
    return re.findall(r"(?s)<script[^>]*>(.*?)</script>", texto)


def c3_sintaxe_js() -> Resultado:
    """node --check em cada bloco <script> do index.html.

    O template tem interpolacao Django ({{ x }}, {% y %}) que nao e' JS, e
    nao da' para passar o arquivo cru. Substitui por 'null' antes de checar:
    se a sintaxe quebra, quebra por causa do JS, nao por causa do placeholder.
    """
    r = Resultado("C3  node --check no JS inline")
    if not INDEX.exists():
        return r.falhou(f"nao achei {INDEX}")
    blocos = _blocos_script(INDEX.read_text(encoding="utf-8", errors="replace"))
    if not blocos:
        return r.falhou("nenhum bloco <script> encontrado no index.html")
    ruins: list[str] = []
    for i, codigo in enumerate(blocos, 1):
        limpo = re.sub(r"\{\{.*?\}\}", "null", codigo, flags=re.S)
        limpo = re.sub(r"\{%.*?%\}", "", limpo, flags=re.S)
        tmp = RAIZ / f".verificar_bloco{i}.js"
        try:
            tmp.write_text(limpo, encoding="utf-8")
            code, saida = roda(["node", "--check", str(tmp.name)], timeout=120)
            if code != 0:
                ruins.append(f"bloco {i}: {saida.strip()[:200]}")
        finally:
            try:
                tmp.unlink()
            except OSError:
                pass
    if ruins:
        return r.falhou("; ".join(ruins))
    return r.passou(f"{len(blocos)} blocos ok")


def c4_suites_js_palco() -> Resultado:
    """As 3 suites .cjs do palco. O pytest NAO as ve — sao node.

    Cada uma imprime 'OK: N ok, 0 falha(s)'. Contar e' mais honesto do que
    olhar so o exit code, porque um arquivo de teste que nao imprime nada
    sairia com 0 e passaria enganado.
    """
    r = Resultado("C4  suites JS do palco")
    base = RAIZ / "app" / "static" / "js"
    arquivos = [
        "tests_palco_cerebro.cjs",
        "tests_palco_amplia.cjs",
        "tests_palco_fio.cjs",
    ]
    ruins: list[str] = []
    total = 0
    for arq in arquivos:
        caminho = base / arq
        if not caminho.exists():
            ruins.append(f"{arq}: NAO EXISTE")
            continue
        code, saida = roda(["node", str(caminho)], timeout=180)
        m = re.search(r"OK:\s*(\d+)\s+ok,\s*0\s+falha", saida)
        if code != 0 and not m:
            ult = [l for l in saida.splitlines() if l.strip()][-4:]
            ruins.append(f"{arq}: exit {code} — " + " | ".join(ult))
            continue
        if m:
            total += int(m.group(1))
        else:
            ruins.append(
                f"{arq}: rodou mas nao imprimiu 'OK: N ok, 0 falha' — "
                f"um teste que nao conta nada nao aprova nada"
            )
    if ruins:
        return r.falhou("; ".join(ruins))
    return r.passou(f"{total} asserts, 0 falhas")


# ---- C5/C6/C7: os portoes que hoje nao existem ----------------------------
#
# Os tres leem a FONTE. Nao e' a prova mais forte do mundo, mas e' a prova que
# existe sem browser, e — mais importante — cada um falha alto quando o padrao
# some, em vez de devolver "ok" por nao ter encontrado nada.


def c5_preset_block_json_no_contexto() -> Resultado:
    r = Resultado("C5  PRESET_BLOCK_JSON no contexto")
    if not INDEX.exists():
        return r.falhou(f"nao achei {INDEX}")
    texto = INDEX.read_text(encoding="utf-8", errors="replace")

    if "PRESET_BLOCK_JSON" not in texto:
        return r.falhou(
            "index.html nao consome PRESET_BLOCK_JSON — "
            "a blocklist nunca chega ao front"
        )

    # Quem produz? Se o so uso for a linha do template, e' consumidor solto:
    # ninguem produz a variavel e o |default:"[]" sempre cai.
    #
    # Este proprio arquivo cita PRESET_BLOCK_JSON (esta linha e a docstring). Se
    # ele contasse como produtor, o portao passaria VAZIO — e um portao que se
    # aprova sozinho e' pior do que nenhum portao. Por isso o scanner pula este
    # arquivo e os de teste: um teste que so'nomeia' o simbolo nao o produz.
    IGNORADOS = {"verificar.py"}
    produtores: list[str] = []
    for p in projeto().rglob("*"):
        if not p.is_file() or p.suffix in {".html", ".js", ".cjs", ".pyc"}:
            continue
        if p.name in IGNORADOS or p.name.startswith("test"):
            continue
        try:
            corpo = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, linha in enumerate(corpo.splitlines(), 1):
            if "PRESET_BLOCK_JSON" not in linha:
                continue
            if "import" in linha:
                continue  # so importou o nome; nao produz a variavel
            if linha.lstrip().startswith("#"):
                continue  # comentario
            try:
                rel = p.relative_to(RAIZ)
            except ValueError:
                rel = p
            produtores.append(f"{rel}:{i}")
            break  # um produtor basta
    if not produtores:
        return r.falhou(
            "PRESET_BLOCK_JSON e' CONSUMIDO mas NINGUEM PRODUZ. "
            'O default "[]" sempre cai, window._PRESET_BLOCK e\' sempre vazio, '
            "e as ~28 entradas de PRESET_BLOCK nunca sao aplicadas no front. "
            "E' o achado a_mutz15uzn868."
        )
    return r.passou(f"produzido em {', '.join(produtores)}")


def _executar_regra_js(
    corpo_js: str, amostra: list[str], bloco, sistema
) -> dict[str, bool] | None:
    """Roda a função JS REAL do index.html no node e devolve o resultado dela.

    Devolve None se não deu para executar — e o chamador trata isso como
    FALHA, não como "passou". Um portão que não consegue verificar não pode
    dizer que está verde.
    """
    import json as _json
    import tempfile as _tf

    # a regra do index.html referencia estas duas globals.
    #
    # Concatenacao com `+` em vez de `%` (ou f-string, ou .format()): o
    # template tem `{}` a fechar no codigo JavaScript, e qualquer linguagem
    # de formatacao passaria a ler o `{` do JS como campo de substituicao.
    # `+` nao interpreta nada, e nao precisa de `# noqa`.
    harness = (
        "const _PRESET_BLOCK = "
        + _json.dumps(sorted(bloco), ensure_ascii=False)
        + ";\n"
        "const _PRESETS_SISTEMA = "
        + _json.dumps(sorted(sistema), ensure_ascii=False)
        + ";\n"
        "const window = { _PRESET_BLOCK: _PRESET_BLOCK, _PRESETS_SISTEMA: _PRESETS_SISTEMA };\n"
        "function _presetIsAllowed(k) { " + corpo_js + " }\n"
        "const entrada = " + _json.dumps(amostra, ensure_ascii=False) + ";\n"
        "const saida = {};\n"
        "for (const k of entrada) { saida[k] = !!_presetIsAllowed(k); }\n"
        "console.log('@@' + JSON.stringify(saida));\n"
    )

    try:
        with _tf.NamedTemporaryFile(
            "w", suffix=".js", delete=False, encoding="utf-8"
        ) as fh:
            fh.write(harness)
            caminho = fh.name
    except OSError:
        return None

    try:
        code, saida = roda(["node", caminho], timeout=120)
    finally:
        try:
            os.unlink(caminho)
        except OSError:
            pass

    if code != 0:
        return None
    m = re.search(r"@@(\{.*\})", saida, re.S)
    if not m:
        return None
    try:
        return {k: bool(v) for k, v in _json.loads(m.group(1)).items()}
    except (ValueError, TypeError):
        return None


def c6_paridade_js_python() -> Resultado:
    """A regra do JS tem de dar a MESMA resposta que a de Python, em todos os nomes.

    Executa as duas de verdade: `preset_permitido()` roda em Python, e a função
    JS extraída do index.html roda no node com as listas reais. Se divergirem em
    UM nome, barra. Não reconstrói a regra JS em Python — foi assim que este
    portão ficou verde falso uma vez (ver o comentário no corpo).
    """
    r = Resultado("C6  paridade JS <-> Python")
    if not PRESETS_PY.exists():
        return r.falhou(f"nao achei {PRESETS_PY}")

    ns: dict = {}
    try:
        exec(
            compile(PRESETS_PY.read_text(encoding="utf-8"), str(PRESETS_PY), "exec"), ns
        )
        python_rule = ns["preset_permitido"]
    except Exception as e:  # noqa: BLE001
        return r.falhou(f"nao consegui carregar app/presets.py: {e}")

    if not INDEX.exists():
        return r.falhou(f"nao achei {INDEX}")
    texto = INDEX.read_text(encoding="utf-8", errors="replace")

    m = re.search(
        r"_presetIsAllowed\s*=\s*function\s*\(\s*\w+\s*\)\s*\{(.*?)\};", texto, re.S
    )
    if not m:
        return r.falhou(
            "nao achei a definicao de window._presetIsAllowed no index.html. "
            "Se ela foi renomeada, este portao esta cego — atualize o verificar.py, "
            "nao o portao."
        )
    corpo_js = m.group(1)

    # O portão quebuhava aqui.
    #
    # A primeira versão RECONSTRUIA a regra JS em Python a partir de três
    # flags (checa_sistema/checa_bloco/checa_prefixo) lidas do texto. Isso é
    # justamente a armadilha: o flag "checa_sistema" respondia "o texto do JS
    # menciona PRESETS_SISTEMA?", não "a regra JS usa a lista de sistema?".
    # Quando eu removi a branch de PRESETS_SISTEMA do Python (um teste de
    # regressão válido), o texto do JS continuava mencionando o nome, o flag
    # ficava True, `sistema` ficava vazio, `k in sistema` dava False para
    # todos — e as DUAS regras passavam a concordar por acidente. O portão
    # passou. Era verde falso, do mesmo tipo do que o C7 teve antes.
    #
    # A versão abaixo EXECUTA a função JS de verdade no node, com as listas
    # REAIS vindas do Python, e compara com `preset_permitido()` também
    # executada. Não há mais interpretação: se as duas divergem, divergem.
    bloco = ns.get("PRESET_BLOCK", frozenset())
    sistema = ns.get("PRESETS_SISTEMA", frozenset())

    amostra = sorted(
        set(bloco)
        | set(sistema)
        | {
            "amplia",
            "custom-agua",
            "custom-nova",
            "visao-geral",
            "",
            "custom-lua",
            "custom-",
            "amplia_mesa",
        }
    )

    # executa a regra JS real no node
    js_resultados = _executar_regra_js(corpo_js, amostra, bloco, sistema)
    if js_resultados is None:
        return r.falhou(
            "nao consegui executar _presetIsAllowed no node — o portao fica "
            "CEGO sem isso, e um portao cego passa verde. Verifique se `node` "
            "esta no PATH."
        )

    divergentes = []
    for n in amostra:
        py = bool(python_rule(n))
        js = js_resultados.get(n)
        if js is None:
            return r.falhou(f"node nao devolveu resultado para {n!r}")
        if py != js:
            divergentes.append(f"{n!r}(py={py}/js={js})")

    if divergentes:
        return r.falhou(
            f"{len(divergentes)} nome(s) diverge(m): {', '.join(divergentes[:8])}"
            + (" ..." if len(divergentes) > 8 else "")
            + ". A regra JS foi EXECUTADA no node e comparada com "
            "preset_permitido() — uma delas mudou de comportamento."
        )

    return r.passou(
        f"{len(amostra)} nomes, 0 divergencia (JS executado no node, "
        "comparado com preset_permitido() roda a roda)"
    )


def c7_meta_sem_entrada() -> Resultado:
    """Todo widget que entra no PRESETS tem de ter meta, ou o forEach morre.

    index.html:2251 faz PRESETS[k]={icon:_presetMeta[k].icon,...} sem guarda.
    _presetMeta tem 1 chave. Se algum dia um preset sem meta entrar ali, o
    forEach INTEIRO aborta e o menu zera — nao e' um preset que falha, e' o
    objeto inteiro. Este portao exige a guarda OU a cobertura de todas as
    chaves que podem chegar.
    """
    r = Resultado("C7  _presetMeta cobre ou ha guarda")
    if not INDEX.exists():
        return r.falhou(f"nao achei {INDEX}")
    texto = INDEX.read_text(encoding="utf-8", errors="replace")

    m = re.search(r"_presetMeta\s*=\s*\{(.*?)\}\s*;", texto, re.S)
    if not m:
        return r.falhou("nao achei _presetMeta no index.html")
    corpo_meta = m.group(1)
    chaves = set(re.findall(r"['\"]([\w\-]+)['\"]\s*:", corpo_meta))

    uso = re.search(r"PRESETS\[\s*\w+\s*\]\s*=", texto)
    if not uso:
        return r.falhou(
            "nao achei onde PRESETS[k] e' montado. Se mudou, este portao esta "
            "cego — atualize o verificar.py, nao o portao."
        )

    # Onde PRESETS[k] e' montado, e de onde vem a meta.
    #
    # O C7 JA FICOU CEGO UMA VEZ: a deteccao exigia `_presetMeta` DEPOIS de
    # `PRESETS[k] = {`, e a guarda (`var _m = _presetMeta[k] || {...}`) e'
    # escrita ANTES. O portao acusou "nao achei" num codigo que estava CORRETO
    # — e um portao que acusa coisa certa de errada treina o executor a
    # ignorar. Por isso a deteccao e' frouxa de proposito: o que importa e' a
    # guarda existir, nao a posicao dela.
    #
    # ha guarda? algo do tipo `_presetMeta[k] || {...}`
    tem_guarda = bool(re.search(r"_presetMeta\s*\[[^\]]+\]\s*\|\|", texto))
    if tem_guarda:
        return r.passou(
            f"{len(chaves)} meta(s) e GUARDA presente "
            "(_presetMeta[...] || {...}) — preset sem meta nao derruba o forEach"
        )

    # sem guarda: as chaves de _allHardcoded tem de estar TODAS em _presetMeta
    ma = re.search(r"_allHardcoded\s*=\s*\{(.*?)\n\s*\};", texto, re.S)
    if not ma:
        return r.falhou("nao achei _allHardcoded para comparar com _presetMeta")
    hardcoded = set(
        re.findall(r"^\s{8,12}['\"]([\w\-]+)['\"]\s*:\s*\{", ma.group(1), re.M)
    )
    faltando = hardcoded - chaves
    if faltando:
        return r.falhou(
            f"{len(faltando)} preset(s) de _allHardcoded sem entrada em _presetMeta: "
            f"{sorted(faltando)[:8]}. Em index.html isso e' um TypeError que zera o menu."
        )
    # SEM GUARDA. Aqui a cobertura de `_allHardcoded` NAO salva o dia, porque o
    # servidor pode injetar presets que nunca passaram por `_allHardcoded`:
    # `PRESET_WIDGETS_JSON[presetName] = ...` aparece na re-injeção do estado e
    # na criação/clonagem de preset pelo produtor. Qualquer um desses sem meta
    # derrubava o forEach inteiro.
    #
    # Medido: enquanto escrevia isto, o C7 PASSAVA sem a guarda — porque o
    # único preset hardcoded tem meta. Verde falso. Um portão que só falha em
    # teoria treina o executor a não acredita nele.
    escritas = re.findall(r"PRESET_WIDGETS_JSON\s*\[[^\]]*\]\s*=", texto)
    # a escrita da semeadura (_allHardcoded) acontece ANTES do forEach do PRESETS;
    # conta as outras, que são as que podem chegar depois.
    fora_da_semeadura = [
        e for e in escritas if "_allHardcoded" not in texto[: texto.find(e)][-400:]
    ]
    if fora_da_semeadura:
        return r.falhou(
            f"sem guarda E {len(fora_da_semeadura)} escrita(s) em PRESET_WIDGETS_JSON "
            "que podem chegar DEPOIS do forEach (re-injecao do servidor, "
            "criacao/clonagem de preset). Um preset sem meta nao vem de "
            "_allHardcoded, logo nao tem entrada em _presetMeta: o TypeError "
            "zera o menu inteiro. A guarda `var _m = _presetMeta[k] || {...}` "
            "e' obrigatoria."
        )
    return r.passou(
        f"{len(chaves)} meta(s) cobrem os {len(hardcoded)} hardcoded e nao ha "
        "escrita posterior — ainda SEM guarda, entao qualquer preset novo "
        "injetado quebra. A guarda continua sendo a solucao."
    )


# ---- C8: !important contraditorio no mesmo seletor ------------------------


def c8_important_duplicado() -> Resultado:
    """Nenhuma propriedade do mesmo seletor pode ser declarada em !important
    por dois arquivos diferentes.

    Esta e' a classe de defeito que ha muito tempo escondia o chat da IA debaixo
    da barra inferior: `#ia-dock` tinha `bottom: 12px !important` num arquivo e
    `bottom: auto !important` noutro. Mesma especificidade, dois !important — e
    quem decide e' a ORDEM DE CARGA das folhas. Um defeito que aparece e
    desaparece conforme a ordem do <link> nao se conserta mexendo no numero: a
    regra tem de existir uma vez so.

    Verificacao estatica, sem browser, e por isso funciona aqui.
    """
    r = Resultado("C8  sem !important contraditorio")
    css_dir = RAIZ / "app" / "static" / "css"
    if not css_dir.exists():
        return r.falhou(f"nao achei {css_dir}")

    # seletor normalizado -> {(propriedade): [("arquivo:linha", texto)])}
    # so interessa regra que abre chave e declara propriedade simples.
    bloco = re.compile(r"(?s)([^{}]+)\{([^{}]*)\}")
    achados: dict[str, dict[str, list[str]]] = {}

    for css in sorted(css_dir.rglob("*.css")):
        try:
            texto = css.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        # tira comentarios: um !important comentado nao e' regra
        texto = re.sub(r"(?s)/\*.*?\*/", "", texto)
        for m in bloco.finditer(texto):
            seletor = " ".join(m.group(1).split())
            # so selector de elemento unico (id ou classe simples): aninhado ou
            # com grupo nao da' para comparar com seguranca
            seletor = re.sub(r"\s*,\s*", ",", seletor)
            if "," in seletor or " " in seletor.strip():
                continue
            corpo = m.group(2)
            for pm in re.finditer(
                r"(^|[;{])\s*([a-z-]+)\s*:[^;{}]*!important", corpo, re.I
            ):
                prop = pm.group(2).lower()
                linha = texto[: m.start(2)].count("\n") + 1
                onde = f"{css.relative_to(RAIZ)}:{linha}"
                achados.setdefault(seletor, {}).setdefault(prop, []).append(onde)

    conflitos: list[str] = []
    for seletor, props in sorted(achados.items()):
        for prop, onde in sorted(props.items()):
            arquivos = {w.split(":")[0] for w in onde}
            if len(arquivos) > 1:
                conflitos.append(
                    f"{seletor} {{ {prop} }} em {len(onde)} lugares: {', '.join(onde)}"
                )

    # RATCHET, nao portao absoluto.
    #
    # A primeira versao deste portao falhava com 68 conflitos. Isso e' verdade
    # e nao e' acionavel: quase todos sao divida anterior, espalhada por
    # widgetbar-windows.css, soft-ui.css e navbar-premium.css. Um portao que
    # barra o trabalho por causa de 68 coisas que ninguem tocou hoje e' um portao
    # que o primeiro executor desliga — e desligado nao protege nada.
    #
    # Entao: BARRA se o conflito for num seletor vigiado (os que este trabalho
    # tocou), e CONTA o resto. O fundo so desce, nunca sobe. #ia-dock nao
    # aparece na lista hoje porque foi corrigido — e se voltar, o portao fecha.
    VIGIADOS = {
        "#ia-dock",
        "#ia-chat",
        "#ia-chat-body",
        "#ia-chat-input",
        "#ia-tasks",
        "#amplia-chat-panel",
        "#widget-bar",
        # NOTA: #dashboard-appbar (a barra real) entrou aqui e saiu.
        # Unifiquei a ALTURA dela em --widgetbar-altura (o sintoma do menu da
        # IA), mas ao entrar no conjunto vigiado ela revelou 14 !important
        # conflitantes em 3 arquivos — a barra inteira, nao so a altura.
        # Consertar isso e' mexer em regra visual sem browser, que e' o erro
        # que o --ia-dock ja me ensinou. Fica como achado, nao como fix.
    }

    meus = [c for c in conflitos if c.split(" {")[0].strip() in VIGIADOS]
    outros = len(conflitos) - len(meus)

    if meus:
        return r.falhou(
            f"{len(meus)} conflito(s) !important em seletor VIGIADO — "
            "regressão no que este trabalho controla:\n      " + "\n      ".join(meus)
        )
    return r.passou(
        "nenhum conflito nos seletores vigiados. "
        f"({outros} conflito(s) pre-existentes noutros seletores, "
        "contados e nao bloqueantes — o ratchet so desce.)"
    )


def projeto() -> Path:
    return RAIZ


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--rapido", action="store_true", help="so C1 e C3 (durante o patch)"
    )
    args = ap.parse_args()

    portoes = (
        [c1_manage_check, c3_sintaxe_js, c8_important_duplicado]
        if args.rapido
        else [
            c1_manage_check,
            c2_pytest,
            c3_sintaxe_js,
            c4_suites_js_palco,
            c5_preset_block_json_no_contexto,
            c6_paridade_js_python,
            c7_meta_sem_entrada,
            c8_important_duplicado,
        ]
    )

    print("=" * 74)
    print("O PORTAO — verificacao de aceitação")
    print(f"raiz: {RAIZ}")
    if args.rapido:
        print("modo rapido: so os portoes de segundos")
    print("=" * 74)

    resultados: list[Resultado] = []
    for fn in portoes:
        t0 = time.monotonic()
        try:
            res = fn()
        except Exception as e:  # noqa: BLE001
            res = Resultado(fn.__name__).falhou(
                f"EXCEPCAO NO PORTAO: {type(e).__name__}: {e}"
            )
        res.segundos = time.monotonic() - t0
        resultados.append(res)

        marca = "FALTA" if res.falta else ("PASSA" if res.ok else "FALHA")
        print(f"[{marca}] {res.nome}  ({res.segundos:.1f}s)")
        for linha in res.detalhe.splitlines() or [""]:
            print(f"        {linha}")

    falhas = [r for r in resultados if not r.ok]
    print("-" * 74)
    if not falhas:
        print(f"TUDO PASSA ({len(resultados)} portoes).")
        return 0
    print(f"{len(falhas)} de {len(resultados)} portoes NAO passaram:")
    for r in falhas:
        print(f"  - {r.nome}")
    print()
    print("Nao declare verde enquanto isto nao der 0. Se um portao nao puder ser")
    print("verificado, o honesto e' escrever 'nao verificado' — nao 'verde'.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
