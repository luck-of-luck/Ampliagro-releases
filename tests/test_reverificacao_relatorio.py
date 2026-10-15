"""Reverificacao em lote das alegacoes do relatorio de arquitectura.

Cada bloco diz o que a alegacao afirmava e o que o codigo faz hoje.
Este ficheiro NAO substitui a leitura — e um filtro de primeira linha que
diz quais das 19 alegacoes Vale a pena abrir a plao. O que fica "CONFIRMADO"
aqui e' o que o teste prova executando; o que fica "REFUTADO" precisa de
leitura humana antes de ser acreditado.
"""

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def fonte(*partes) -> str:
    p = RAIZ.joinpath(*partes)
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


BASE = fonte("config", "settings", "base.py")
PROD = fonte("config", "settings", "prod.py")
COMPOSE = fonte("docker-compose.prod.yml")
CADDY = fonte("Caddyfile")
IOT = fonte("app", "iot", "views.py")
CANBAN = fonte("app", "api", "views", "kanban.py")
SEG = fonte("app", "seguranca.py")
REQS = fonte("requirements.txt")

# ─────────────────────────────────────────────────────────────────────────────
# Infra / producao
# ─────────────────────────────────────────────────────────────────────────────


def test_csp_permite_o_webllm():
    """O WebLLM carrega de esm.run e fala com o HuggingFace.

    A alegacao era que a CSP o bloqueava e o modelo nunca carregava. Com
    `script-src` sem `esm.run` e sem `'wasm-unsafe-eval'`, o motor nao
    arranca — e o sintoma e' um produto que parece funcionar.
    """
    assert "esm.run" in BASE, "CSP sem esm.run: o WebLLM nao carrega"
    assert "wasm-unsafe-eval" in BASE, (
        "CSP sem 'wasm-unsafe-eval': o WebGPU compila os shaders e falha"
    )
    m = re.search(r"CSP_CONNECT\s*=\s*(.*)", BASE)
    if m:
        for dominio in ("huggingface.co", "hf.co"):
            assert dominio in BASE, f"CSP sem connect para {dominio}"


def test_o_proxy_nao_sao_ignora():
    """A app so ouve no loopback e o Django sabe que o pedido ja e' https.

    Sem `SECURE_PROXY_SSL_HEADER`, o Django ve `http` atras do Caddy e
    redireciona em loop — o sintoma e' um502 que parece problema de
    certificates.
    """
    assert "SECURE_PROXY_SSL_HEADER" in PROD, (
        "prod.py sem SECURE_PROXY_SSL_HEADER: o Django ve http atras do proxy"
    )
    assert "127.0.0.1:8000:8000" in COMPOSE, (
        "a porta 8000 continua exposta no host: o Caddy deixa de ser a "
        "unica porta de entrada e o TLS e' contornavel"
    )
    assert "X-Forwarded-Proto" in CADDY, "Caddy sem X-Forwarded-Proto"


def test_a_app_ouve_so_no_loopback():
    """`ports:` sem `127.0.0.1:` publica o Django directamente."""
    for linha in COMPOSE.splitlines():
        if re.match(r"\s*-\s*\"?\d+:8000", linha):
            assert "127.0.0.1" in linha, (
                f"porta exposta sem bind ao loopback: {linha.strip()}"
            )


def _sem_prosa(texto: str) -> str:
    """O codigo sem comentarios nem conteudo de docstrings.

    `iot/views.py` documenta em several pontos o codigo que JA FOI
    removido — o `Device.objects.get(device_eui=...)` sem escopo e' o
    exemplo. Sem esta filtragem, o teste falha pela documentacao de uma
    correccao, que e' o oposto do que se quer.
    """
    try:
        import ast

        arvore = ast.parse(texto)
    except SyntaxError:
        return texto

    linhas_a_limpar = set()
    for no in ast.walk(arvore):
        # Docstrings: o no e um Constant str dentro de Module/FunctionDef.
        if isinstance(no, ast.Constant) and isinstance(no.value, str):
            linhas_a_limpar.update(range(no.lineno, (no.end_lineno or no.lineno) + 1))
    # Comentarios, via tokenize.
    import io as _io
    import tokenize

    try:
        for tok in tokenize.generate_tokens(_io.StringIO(texto).readline):
            if tok.type == tokenize.COMMENT:
                linhas_a_limpar.add(tok.start[0])
    except tokenize.TokenError:
        pass

    return "\n".join(
        ln for i, ln in enumerate(texto.splitlines(), 1) if i not in linhas_a_limpar
    )


# ─────────────────────────────────────────────────────────────────────────────
# IoT
# ─────────────────────────────────────────────────────────────────────────────


def test_o_iot_so_aceita_gateway():
    """So `Gateway.api_key` autentica. Nem `device_eui`, nem TTN aberto.

    `device_eui` e' um identificador de hardware que viaja em claro pelo
    radio: qualquer um que o ouca num packet escreve telemetria em nome da
    placa. `api_key` e' o unico que o servidor pode revogar.

    NOTA: `device_eui` aparece legitimamente neste ficheiro como chave de
    PESQUISA (`Device.objects.get(device_eui=eui, gateway=gw)`) depois de
    autenticado. O que nao pode e' estar no lugar da credencial. Por isso o
    teste nao procura a string — procura um filtro por `device_eui` que NAO
    esteja protegido por `gateway` nem por `propriedade__user`.
    """
    m = re.search(
        r"def\s+_resolve_auth\(\s*request\s*\)(.*?)(?=\ndef\s|\nclass\s)", IOT, re.S
    )
    assert m, "nao encontrei a funcao de autenticacao em iot/views.py"
    corpo_auth = m.group(1)

    # `device_eui` aparece na EXPLICACAO de que foi removido. O que se
    # verifica e' o CODIGO, nao a prosa — senao o proprio comentario que
    # documenta a correccao faria o teste falhar.
    codigo_auth = "\n".join(
        ln for ln in corpo_auth.splitlines() if not ln.strip().startswith("#")
    )
    assert "device_eui" not in codigo_auth, (
        "a autenticacao do IoT volta a mencionar device_eui:\n" + codigo_auth
    )
    assert "Gateway" in corpo_auth, (
        "a autenticacao do IoT nao verifica Gateway.api_key"
    )

    # `iot/views.py` tem docstrings que descrevem o codigo ANTIGO
    # (`Device.objects.get(device_eui=...)` sem escopo). Tambem nao sao
    # codigo — sao a historia do bug. Filtra-se a prosa toda.
    iot_codigo = _sem_prosa(IOT)

    for filtro in re.finditer(
        r"Device\.objects\.(?:filter|get)\(([^)]*device_eui[^)]*)\)", iot_codigo
    ):
        cond = filtro.group(1)
        assert ("gateway" in cond) or ("propriedade__user" in cond), (
            "filtro por device_eui sem gateway nem propriedade__user: ("
            + cond.strip()
            + ")\nUm EUI sem escopo deixa adivinhar a existencia de "
            "dispositivos de outra fazenda."
        )

    # A docstring do modulo nao pode prometer o fallback que foi removido.
    cabecalho = IOT[: IOT.find('"""', 3)]
    assert "fallback para devices sem gateway" not in cabecalho, (
        "a docstring de iot/views.py ainda descreve `device_eui` como "
        "fallback de autenticacao. O codigo removeu-o; a prosa nao — e um "
        "leitor que confie na docstring escreve um cliente que manda so o "
        "EUI e recebe 401."
    )


def test_os_commands_iot_estao_vivos():
    """`mqtt_listener` e `sync_inmet` existem em `app/management/commands/`.

    A alegacao do relatorio era que tinham sido apagados do git tree. Estao
    la — e em `app/management/`, que e' onde o Django os descobre. A copia
    em `app/iot/management/` era duplicata morta e foi removida de proposito.
    """
    base = RAIZ / "app" / "management" / "commands"
    for nome in ("mqtt_listener.py", "sync_inmet.py"):
        assert (base / nome).exists(), f"{nome} ausente de app/management/commands"


# ─────────────────────────────────────────────────────────────────────────────
# Fiscal
# ─────────────────────────────────────────────────────────────────────────────


def test_a_chave_de_seguranca_tem_uso():
    """`AMPLIAGRO_DATA_KEY` e' usada em `app/seguranca.py`.

    A alegacao era "zero instancias, substituida por Gateway.api_key". Sao
    coisas diferentes: uma cifra dados em reposo, a outra autentica
    dispositivos. Trocar uma pela outra nao e' uma migracao.
    """
    assert "AMPLIAGRO_DATA_KEY" in SEG, (
        "seguranca.py deixou de usar AMPLIAGRO_DATA_KEY — e' a chave de "
        "cifra em repouso, nao a de autenticacao IoT"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Os 500s
# ─────────────────────────────────────────────────────────────────────────────


def test_o_agenda_analises_nao_importa_um_modulo_que_nao_existe():
    """O `ModuleNotFoundError` em cada request a `/api/agenda-analises/`.

    `from .serializers import SafraSerializer` dentro de
    `app/api/views/kanban.py` resolvia para `app.api.views.serializers`, que
    nao existe. Os serializers ja vinham do wildcard do topo do modulo.
    """
    assert not re.search(r"from\s+\.serializers\s+import", CANBAN), (
        "kanban.py voltou a importar de `.serializers` — modulo inexistente"
    )
    assert "agenda_analises_data" in CANBAN


# ─────────────────────────────────────────────────────────────────────────────
# Dependencias
# ─────────────────────────────────────────────────────────────────────────────


def test_o_async_tem_a_posta_redis():
    """`channels-redis` declarado. Sem ele, o channel layer cai para
    InMemoryChannelLayer e o fan-out de WebSocket funciona numa processo e
    falha com varios workers — o sintoma e' "as notificacoes chegam umas
    vezes"."""
    assert "channels-redis" in REQS, "channels-redis ausente de requirements"
    if "CHANNEL_LAYERS" in BASE:
        assert "RedisChannelLayer" in BASE, "CHANNEL_LAYERS sem RedisChannelLayer"
