"""Verifica as AFIRMACOES do PLANO-EXECUCAO.md contra o codigo.

Este ficheiro existe por causa do §2.9 do proprio plano: *"nenhuma promessa
entra no manifesto sem teste que a confirme"*. Um plano de execucao que
nao se auto-verifica e a mesma classe de documento que ele critica.

Cada teste mede UMA afirmacao do plano. Se o codigo mudar, o plano tem de
mudar — e este ficheiro diz qual.
"""

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PLANO = RAIZ / "docs" / "sistema" / "PLANO-EXECUCAO.md"


def _fonte(*partes: str) -> str:
    p = RAIZ.joinpath(*partes)
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


def test_o_plano_existe_e_tem_as_partes():
    txt = PLANO.read_text(encoding="utf-8")
    for parte in ("PARTE 1", "PARTE 2", "PARTE 3", "PARTE 4", "PARTE 5"):
        assert parte in txt, f"o plano perdeu a {parte}"


# ─────────────────────────────────────────────────────────────────────────────
# 1.1 — o achado que o plano chama de maior
# ─────────────────────────────────────────────────────────────────────────────


def test_as_culturas_tem_regras_agronomicas():
    """MARCADOR DE PROGRESSO — o plano §1.1 diz que nenhuma cultura tinha regra.

    MEDIDO 2026-10-05: `milho` (janela 2-3) e `cafe` (janela 11-3) ja tem
    regra. A Onda 1 item 1.4 comecou.

    Este teste **passa sempre**. Nao e' um guarda de qualidade: e' o contador
    `M3` da Parte 5 do plano — "culturas com regra agronomica", hoje 0, alvo
    15. Fixa o que ja foi feito e escreve no ecra o que falta, para a Onda
    1.4 ter um alvo que se move.

    Porque um teste destes e melhor do que `assert len(regras) == 0`:
    aquele quebrava a cada regra nova que alguem escrevia, e a Onda 1.4
    deixava de poder ser feita sem falhar o CI. Um teste que falha quando o
    trabalho avanca e' um teste que trava o trabalho.
    """
    from app.api.culture_config import get_culture_business_rules

    # As 15 do alvo da Onda 1.4. Um subconjunto que representa a maior parte
    # da area plantada do Brasil.
    alvo = (
        "soja",
        "milho",
        "cafe",
        "algodao",
        "cana",
        "arroz",
        "feijao",
        "trigo",
        "pastagem",
    )

    com_regra = [c for c in alvo if len(get_culture_business_rules(c)) > 0]

    # Uma janela tem de existir para a regra contar. Uma regra sem janela nao
    # diz ao produtor quando plantar, que e' o objectivo.
    com_janela = [
        c for c in alvo if (get_culture_business_rules(c).get("planting_window") or {})
    ]

    sys.stderr.write(
        "\n[M3] culturas com regra: %d/%d | com janela de plantio: %d/%d\n"
        % (len(com_regra), len(alvo), len(com_janela), len(alvo))
    )

    assert com_regra, (
        "nenhuma cultura tem regra agronomica. A Onda 1.4 nao comecou, ou "
        "alguem limpou o `cultures-config.json`."
    )


def test_o_motor_nao_assume_permissividade_quando_nao_sabe():
    """**GUARDA.** Onda 0.1 item 0.1 — o motor nao afirma o que nao sabe.

    Este teste foi, ate 2026-10-05, um *marcador de divida*: passava enquanto o
    defeito existisse, e falhava no momento em que a correcao fosse feita. A
    correcao foi feita por outro processo (`culture_config.py:436-437`), o
    marcador disparou, e esta e' a versao definitiva: **passa porque o defeito
    esta corrigido, e volta a falhar se ele voltar.**

    > Um marcador de divida e' um registo do que esta errado. Um guarda e' a
    > promessa de que nao volta a estar. Este passou a ser a segunda coisa.

    A propriedade tem **dois lados**, e os dois importam:

    | cultura | tem janela? | resposta correcta |
    |---|---|---|
    | sem regra | nao | **`None`** — "nao se sabe" |
    | com janela | sim | **`True`/`False`** — uma medicao |

    Um guarda que so verifica o primeiro deixa passar o erro invertido: `False`
    para tudo. Seria trocar uma mentira por outra — e `False` e' pior, porque
    **parece uma resposta.**

    MEDIDO 2026-10-05: este teste fixava a cultura **pelo nome** (`soja` com
    "0 regras"). E' a forma mais rapida de escrever o guarda e a que parte
    primeiro: quando a Onda 0.2 da §1.1 criou regras para `soja`, o teste
    ficou vermelho — **nao por o motor voltar a mentir, mas por a cultura
    deixar de servir de exemplo**.

    Um guarda que depende de uma linha de dados que outra tarefa vai mudar e'
    um guarda que mede a coisa errada. Agora a cultura sem regra e'
    **descoberta**, nao nomeada: o teste pergunta ao catalogo qual e' a que
    ainda nao tem janela. Se um dia TODAS tiverem, o teste passa a dizer
    isso em vez de falhar a fingir que ainda existe uma cultura sem regra.
    """
    from app.api.culture_config import CultureBusinessEngine, get_culture_business_rules

    # Descobrir a cultura sem janela, em vez de a nomear.
    sem_regra = None
    for slug in _slugs_de_cultura():
        if not get_culture_business_rules(slug).get("planting_window"):
            sem_regra = slug
            break

    assert sem_regra is not None, (
        "Nenhuma cultura sem janela para testar. Ou as 488 ganharam agronomia "
        "— bom, e entao este guarda ja nao tem o que vigiar e deve ser "
        "reescrito para testar o motor com `rules = {}` injectado — ou o "
        "catalogo parou de ser lido, o que e' pior."
    )

    # --- lado 1: sem regra, NAO pode afirmar -------------------------------
    r = CultureBusinessEngine(sem_regra).is_planting_season()
    assert r is None, (
        "is_planting_season() voltou a assumir permissividade. Sem regra, tem de "
        "devolver `None` (nao se sabe) e nunca `True` (afirmacao sem medicao). "
        f"Se esta a falhar, alguem reintroduziu o default permissivo — e' "
        f"exactamente o defeito que `validators.py:40` proibe. (cultura={sem_regra!r})"
    )

    # `None` e' o unico valor aceitavel. `False` tambem e' mentira.
    assert r is not False, (
        "`False` para uma cultura sem janela e' uma AFIRMACAO ('esta fora da "
        "janela') sobre uma janela que nao existe. O estado honesto e `None`."
    )


def test_o_motor_responde_sim_ou_nao_quando_a_janela_existe():
    """Segundo lado do mesmo guarda: com regra, tem de haver resposta.

    Sem este, `return None` no topo de `is_planting_season` passaria o teste
    anterior e **destruiria o produto**: o painel deixava de dizer quando
    plantar. A Onda 0.1 troca uma permissividade inventada por uma ausencia
    declarada — **nas duas pontas**.

    MEDIDO 2026-10-05: a `rules` e' injectada a mao, e nao lida do catalogo.
    E' deliberado. A janela `10..3` deste teste nao e' a janela da soja — e'
    uma janela que atravessa o ano, para exercitar o ramo `else` de
    `is_planting_season`, que e' o ramo que nenhuma cultura real tem hoje.
    Ler do catalogo faria este teste depender de uma tabela que a §1.1 manda
    mudar, e o passaria a medir outra coisa.
    """
    from datetime import date

    from app.api.culture_config import CultureBusinessEngine

    engine = CultureBusinessEngine(_qualquer_slug())
    vazio = engine.rules
    engine.rules = {"planting_window": {"start_month": 10, "end_month": 3}}
    try:
        dentro = engine.is_planting_season(date(2026, 11, 15))
        fora = engine.is_planting_season(date(2026, 6, 15))
    finally:
        engine.rules = vazio

    assert dentro is True, (
        f"Com janela definida (out-mar), novembro tem de dar `True`. Veio {dentro!r}. "
        "Se `None`, a correccao da Onda 0.1 foi longe demais."
    )
    assert (
        fora is False
    ), f"Com janela definida (out-mar), junho tem de dar `False`. Veio {fora!r}."


def _slugs_de_cultura():
    """Os slugs que o catalogo expoe, para poder DESCOBRIR um sem janela.

    Usa `_indice_culturas()` — o MESMO indice que `_cultura()` consulta para
    resolver um slug. A primeira versao deste teste parseava o
    `cultures-config.json` por conta propria e encontrou **zero** culturas: o
    ficheiro e' `{"groups": [...]}` com `cultures` dentro de grupos e
    subgrupos, e um parser que o le como lista devolve `[]` sem errar.

    E' a mesma razao pela qual `alert_engine.py:267` e' a unica outra coisa
    que sabe fazer esta ligacao: dois leitores do catalogo que nao falam com
    o mesmo indice divergem, e divergem em silencio.
    """
    from app.api.culture_config import _indice_culturas

    return list(_indice_culturas().keys())


def _qualquer_slug():
    """Um slug que o motor aceite, para poder injectar `rules` a mao."""
    slugs = _slugs_de_cultura()
    return slugs[0] if slugs else "soja"


# ─────────────────────────────────────────────────────────────────────────────
# 1.2 — Bucket A: as 8 afirmacoes que continuam vivas
# ─────────────────────────────────────────────────────────────────────────────


def test_a1_lcdpr_gera_os_registos_conhecidos():
    """O plano afirmava 6 registos; ja foram implementados 8.

    MEDIDO 2026-10-05: o exportador passou de 160 para 533 linhas e passou a
    gerar `0010` (parametros de tributacao) e `0045` (exploracao por mais de
    uma pessoa). O Q200 — o resumo mensal, que era o item 1.1 da Onda 1 e o
    mais barato porque os dados ja eram calculados — continua em falta.

    Este teste foi escrito para detectar exactamente isto: quando um registo
    novo aparece, o plano fica obsoleto sem ninguem dizer. E o que happened.
    """
    txt = _fonte("app", "services", "lcdpr_export.py")
    gerados = set(re.findall(r'_adicionar_linha\(reg_\w+,\s*"([^"]+)"', txt))

    # Ja implementados. Todos estes tem de estar la.
    implementados = {"0000", "0010", "0030", "0040", "0045", "0050", "Q100"}
    em_falta = implementados - gerados
    assert not em_falta, (
        f"o exportador deixou de gerar {sorted(em_falta)}. O plano §1.2 A1 "
        "esta obsoleto."
    )

    # O Q200 continua a faltar. Se aparecer, o plano §2.1 esta obsoleto e o
    # item 1.1 da Onda 1 esta feito.
    if "Q200" in gerados:
        return  # nada a dizer — foi implementado
    # Enquanto nao aparecer, o plano mantem "6 de 9" no §1.2 e a Onda 1
    # mantem o item 1.1 por fazer. Este `return` e' o que impede o teste de
    # falhar por causa de um item que ja foi feito.


def test_a3_continua_sem_ota():
    """O plano afirma: zero codigo de OTA."""
    raiz_app = RAIZ / "app"
    padroes = re.compile(
        r"ota_update|esptool|mpremote|micropython|firmware_upload", re.I
    )
    for py in raiz_app.rglob("*.py"):
        if padroes.search(py.read_text(encoding="utf-8", errors="replace")):
            # Nao e falha se for so um comentario/docstring a descrever a
            # ausencia. Verifica-se a linha.
            for ln in py.read_text(encoding="utf-8", errors="replace").splitlines():
                if padroes.search(ln) and not ln.strip().startswith("#"):
                    pytest_skip = "docstring" in ln.lower()
                    if not pytest_skip:
                        raise AssertionError(
                            f"{py.relative_to(RAIZ)}:{ln.strip()[:60]} parece "
                            "codigo de OTA. O plano §1.2 A3 diz que nao ha."
                        )


def test_a4_tasks_py_e_placeholder():
    """O plano afirma: 13 linhas, `return True`, comentado como Placeholder."""
    txt = _fonte("app", "tasks.py")
    assert "Placeholder" in txt or "placeholder" in txt, (
        "app/tasks.py deixou de se declarar placeholder. O plano §1.2 A4 e o "
        "§2.7 item 3 estao obsoletos — a task foi implementada."
    )
    assert "return True" in txt, "app/tasks.py mudou. Actualize o §1.2 A4."


def test_a5_celery_continua_armado_por_var():
    """O plano afirma: `BEAT_SCHEDULE` so com `AMPLIA_CELERY_BEAT=1`."""
    txt = _fonte("app", "ia", "proativo_tasks.py")
    assert (
        'os.environ.get("AMPLIA_CELERY_BEAT") == "1"' in txt
    ), "o gate do Celery mudou. Actualize o §1.2 A5 e o §2.7."


# ─────────────────────────────────────────────────────────────────────────────
# 1.3 — Bucket B: o que os documentos dizem e esta errado
# ─────────────────────────────────────────────────────────────────────────────


def test_b1_a_proveniencia_tem_seis_estados():
    """O plano afirma 6 estados. Os dois documentos de entrada diziam 3."""
    from app.ia.proveniencia import TODOS

    assert len(TODOS) == 6, (
        f"proveniencia.TODOS tem {len(TODOS)} estados, o plano §1.3 B1 diz 6. "
        "Actualize."
    )


def test_b2_os_commands_iot_existem():
    """O plano afirma que o `9.md` errou: os comandos existem."""
    base = RAIZ / "app" / "management" / "commands"
    for nome in ("mqtt_listener.py", "sync_inmet.py"):
        assert (base / nome).exists(), (
            f"{nome} desapareceu de app/management/commands. O plano §1.3 B2 "
            "afirma que existe — e agora seria verdade o que o 9.md disse."
        )


def test_b3_a_chave_de_seguranca_tem_uso():
    """O plano afirma 6 ocorrencias em `app/seguranca.py`."""
    txt = _fonte("app", "seguranca.py")
    assert txt.count("AMPLIAGRO_DATA_KEY") >= 4, (
        "seguranca.py deixou de usar AMPLIAGRO_DATA_KEY. O plano §1.3 B3 "
        "afirma que usa — o que o 9.md dizia ser zero."
    )


def test_b4_o_caderno_existe():
    """O plano afirma que o Caderno de Campo foi construido."""
    assert (RAIZ / "app" / "models" / "caderno.py").exists()
    assert (RAIZ / "app" / "api" / "views" / "caderno.py").exists()
    assert (RAIZ / "app" / "migrations" / "0065_nota_campo.py").exists()


# ─────────────────────────────────────────────────────────────────────────────
# 2.x — os activos de que o plano depende
# ─────────────────────────────────────────────────────────────────────────────


def test_o_texto_do_plano_esta_limpo():
    """Nenhum caractere CJK no plano.

    Nao e estetica. Um caractere corrompido no meio de uma frase torna a
    frase ilegive, e um plano que ninguem consegue ler nao e um plano.
    """
    t = PLANO.read_text(encoding="utf-8")
    cjk = re.findall(r"[\u4e00-\u9fff\u3040-\u30ff]", t)
    assert not cjk, f"{len(cjk)} caracteres CJK no plano. Corrija antes de circular."


def test_cada_secao_do_destrinchamento_tem_evidencia():
    """Regra que o plano §0 promete: cada affirmacao carrega `ficheiro:linha`.

    Medir a *densidade* de referencias em todas as linhas dava 27% e nao
    dizia nada — porque a maioria das linhas de um plano e prosa, sequencia e
    fecho, que legitimamente nao citam ficheiros.

    O que interessa e o sitio onde as afirmacoes vivem: cada bloco `## 2.x` do
    destrinchamento. Se um deles perder a referencia, e porque virou opiniao.
    """
    t = PLANO.read_text(encoding="utf-8")

    # Cada secao `## 2.x` ate ao proximo `## `.
    blocos = re.split(r"\n## (?=2\.\d)", t)
    secoes = [b for b in blocos if re.match(r"2\.\d", b)]
    assert len(secoes) >= 9, (
        f"esperava pelo menos 9 secoes 2.x no destrinchamento, encontrei "
        f"{len(secoes)}. O plano mudou de forma."
    )

    sem_evidencia = []
    for b in secoes:
        titulo = b.split("\n", 1)[0].strip()[:40]
        if not re.search(r"\.(py|js|html|json)\b|:[0-9]+|grep|Select-String|->", b):
            sem_evidencia.append(titulo)

    assert not sem_evidencia, (
        "secoes do destrinchamento sem referencia a ficheiro:linha ou "
        f"comando: {sem_evidencia}.\n\nO plano §0 prometeu evidencia em cada "
        "afirmacao; uma seccao sem referencia e uma opiniao com formatacao "
        "de plano."
    )
