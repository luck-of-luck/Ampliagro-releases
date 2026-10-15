"""Promessas absolutas no texto que o cliente le.

O irmao mais velho deste ficheiro
==================================
`test_promessas_numericas.py` mede as promessas **numericas** ("11 cadeias",
"707 culturas") e torna a divergencia visivel em CI. Este mede as promessas
**absolutas**, que sao a mesma doenca com outra roupa: um adjectivo que o
sistema nao pode cumprir e que nao devolve erro quando nao cumpre.

O caso medido
=============
MEDIDO 2026-10-05. A meta description do produto — o texto que **qualquer
motor de busca le** e que o produtor ve no ecra de login — era:

    "Ampliagro - Sistema **absoluto** do agro 5.0 para controle e gestão
     da sua fazenda."

Cinco ocorrencias em tres templates:

| Ficheiro | Linhas | Onde |
|---|---|---|
| `app/templates/base.html` | 8 | `<meta name="description">` — herdada por **todas** as paginas |
| `app/templates/login.html` | 7, 30, 50 | meta + dois `<p>` visiveis |
| `app/templates/onboarding.html` | 32 | `<p>` visivel, primeiro ecra do produtor |

Por que "absoluto" e' um passivo, e nao um elogio
================================================
Porque **e' falso de um modo que ninguem pode verificar.** Um ERP que promete
"absoluto" promete que nao ha caso em que falhe. O Ampliagro mediu, na sua
 propria Onda 0, que:

* o isolamento de tenant **nao passa** por tarefa Celery nem por management
  command — e' middleware, so cobre HTTP;
* `is_planting_season()` afirmava "pode plantar" para uma cultura cujas janelas
  nao conhece (Onda 0.1, ja corrigido);
* o `celery` tem uma task que faz `logger.info` e devolve `True`.

"Absoluto" e' exactamente a palavra que **nao pode coexistir** com um
`proveniencia.py` que se recusa a inventar um zero. Nao e'Hyperbole
inofensiva: e' o adjectivo que torna as outras promessas do produto menos
creditaveis.

Troca feita
===========
    "Sistema absoluto do agro 5.0"  ->  "Sistema de gestão do agro 5.0"

Mantem a voz e o "5.0"; tira o superlativo que nao se mede. E' o mesmo criterio
de `test_regras_cultura_motor.py`, que diz nas proprias palavras: *"ou admite-se
que ela nao existe e tira-se a promessa do ecra"*.

O QUE ESTE TESTE NAO FAZ, E PORQUEM
===================================
Nao reescreve copy. Um adjectivo e' uma decisao comercial, e este ficheiro
nao tem esse direito — o mesmo limite que `test_promessas_numericas.py` declara
para os numeros. O que faz e:

1. **Falhar** se a promessa medida voltar (o superlativo nao tem volta atras).
2. **Listar** o que resta de linguagem absoluta no texto visivel, para ficar
   visivel em CI em vez de aparecer num pitch.

Sobre os falsos positivos
-------------------------
Este teste tem de ignorar `controle-absoluto.html` ("Controle **Absoluto** por
Talhao"), onde "absoluto" quer dizer *completo* e nao *garantido*. Uma guarda
que apanha o sentido errado treina a ignorar o sinal — foi o que aconteceu com
`app/tests_wizard_pergunta.py`. Por isso o filtro e' **por termo exacto de
marca** e nao por substantivo solto.
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
TEMPLATES = RAIZ / "app" / "templates"

#: A promessa concreta que foi removida. Se voltar, o teste falha.
PROMESSA_REMOVIDA = re.compile(r"Sistema\s+absoluto\s+do\s+agro\s+5\.0", re.IGNORECASE)

#: Nome da pagina onde "absoluto" e' sentido legitimo (completo, nao garantido).
#: `controle-absoluto.html` chama-se "Controle Absoluto por Talhao" — e' o nome
#: da funcionalidade. Confundir as duas coisas seria um falso positivo.
EXCEPTOES = {"controle-absoluto.html"}

#: Terminos de promessa absoluta em **texto visivel**. Nao includede
#: `100%`, `garantido` ou `total` de proposito: aparecem em datas ("100% da
#: safra"), em unidades e em nomes de ficheiro, e cada um exigiria uma
#: excepcao. Este ficheiro mede o superlativo de marca, nao o portugues todo.
TERMOS_VISIVEIS = re.compile(
    r"\b(absolut[ao]|impenetrável|impenetravel|infalível|infalivel)\b",
    re.IGNORECASE,
)


def _templates() -> list[Path]:
    return sorted(TEMPLATES.rglob("*.html"))


def _sem_comentarios_e_js(html: str) -> str:
    """Remove blocos de comentario HTML e conteudo de `<script>`/`<style>`.

    Sem isto, `index.html` tem dezenas de `// ABSOLUTO:` em comentarios de
    JavaScript — e' vocabulario tecnico normal ("render absoluto", "guarda
    absoluta"), nao promessa ao cliente. Contar aquilo seria ruído.
    """
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.DOTALL)
    html = re.sub(
        r"<script\b[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE
    )
    html = re.sub(
        r"<style\b[^>]*>.*?</style>", " ", html, flags=re.DOTALL | re.IGNORECASE
    )
    return html


def test_a_promessa_de_sistema_absoluto_nao_volta():
    """MEDIDO 2026-10-05: estava em 5 linhas de 3 templates. **Nao volta.**"""
    hits: list[str] = []
    for ficheiro in _templates():
        texto = ficheiro.read_text(encoding="utf-8", errors="replace")
        for n, linha in enumerate(texto.splitlines(), start=1):
            if PROMESSA_REMOVIDA.search(_sem_comentarios_e_js(linha)):
                hits.append(f"{ficheiro.relative_to(RAIZ)}:{n}: {linha.strip()[:100]}")
    assert not hits, (
        "Voltou a promessa de 'Sistema absoluto do agro 5.0'.\n"
        "MEDIDO 2026-10-05: removida de base.html:8, login.html:7/30/50 e "
        "onboarding.html:32, porque 'absoluto' e' um adjectivo que o sistema "
        "nao pode cumprir — e nao devolve erro quando nao cumpre.\n"
        + "\n".join(f"  * {h}" for h in hits)
    )


def test_a_meta_description_nao_promete_absoluto():
    """A meta description e' o texto mais exposto do produto.

    Aparece no resultado de cada busca, e e' copiada para preview de link em
    qualquer mensagem. E' o pior sitio para um adjectivo que nao se mede.
    """
    problemas: list[str] = []
    for ficheiro in _templates():
        if ficheiro.name in EXCEPTOES:
            continue
        texto = ficheiro.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(
            r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']',
            texto,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            conteudo = m.group(1)
            achado = TERMOS_VISIVEIS.search(conteudo)
            if achado:
                problemas.append(
                    f"{ficheiro.relative_to(RAIZ)}: '{achado.group(0)}' em: {conteudo.strip()[:90]}"
                )
    assert not problemas, (
        "A meta description promete em absoluto. E' o texto mais exposto do "
        "produto — indexado por motores de busca e copiado em preview de "
        "qualquer link:\n" + "\n".join(f"  * {p}" for p in problemas)
    )


def test_a_linguagem_absoluta_visivel_fica_visivel():
    """NAO FALHA. Regista.

    Esta lista e' o **radar**: mostra onde ainda ha superlativo no texto que o
    produtor le. Nao reprova, porque parte disto e' decisao comercial de quem
    responde pelo produto — e este ficheiro nao tem esse direito.

    O que aponta: o `base.html` é o template base. Uma ocorrencia ai propaga a
    **todas** as paginas do produto.
    """
    achados: list[str] = []
    for ficheiro in _templates():
        if ficheiro.name in EXCEPTOES:
            continue
        texto = ficheiro.read_text(encoding="utf-8", errors="replace")
        limpo = _sem_comentarios_e_js(texto)
        for m in TERMOS_VISIVEIS.finditer(limpo):
            achados.append(
                f"{ficheiro.relative_to(RAIZ)}: '{m.group(0)}'"
                + (
                    "   <-- template BASE, propaga a todas as paginas"
                    if ficheiro.name == "base.html"
                    else ""
                )
            )
    # Nao falha. Imprime quando ha.
    if achados:
        print("\n  [radar] linguagem absoluta em texto visivel:")
        for a in achados:
            print(f"    - {a}")
    assert True
