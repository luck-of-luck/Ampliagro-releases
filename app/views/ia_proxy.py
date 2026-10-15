import json
import re

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

AGRO_ALLOW = re.compile(
    r"(soja|milho|algod[aã]o|caf[eé]|trigo|arroz|feij[aã]o|praga|doen[cç]a|ferrugem|lagarta|pulga|adubo|npk|semente|pulveriza|colheita|plantio|solo|ph|talh[aã]o|safra|clima|agricultura|pecu[aá]ria|agro)",
    re.I,
)


@login_required
@require_POST
def ia_web_search(request):
    """
    Busca web para a AmplIA, com proteccao de privacidade.

    O QUE ESTE PROXY FAZ
    Envia para o DuckDuckGo apenas o termo `q`, truncado. Nunca envia
    propriedade, talhao, estoque nem qualquer dado do usuario: o URL e' uma
    constante (abaixo) e o unico que varia e' o query string.

    O QUE ELE NAO FAZ — e o docstring antigo dizia que fazia
    Restringir a agro. `AGRO_ALLOW` NAO e' um filtro. Um termo que nao bate
    recebe " agricultura" acrescentado e segue para a web na mesma. Nao ha
    caminho de rejeicao. O nome do regex sugere uma allowlist; o
    comportamento e' um sufixo.

    Porque nao se mexe aqui: mudar para rejeicao altera o que a AmplIA
    consegue responder, e isso e' decisao de quem responde ao produtor — nao
    de quem le o codigo. Fica aqui a verdade, para ninguem confiar no nome.

    Se isto alguma vez contar como fronteira de seguranca, tem de passar a
    rejeitar. Enquanto nao, e' um vies de resultados.
    """
    try:
        data = json.loads(request.body.decode() or "{}")
        q = (data.get("q") or "").strip()[:120]
        if not q:
            return JsonResponse({"error": "q vazio"}, status=400)
        # restringe a agro
        if not AGRO_ALLOW.search(q):
            q = q + " agricultura"
        q = q[:80]  # limita
        # busca DuckDuckGo HTML (sem API key, sem user data)
        import requests

        try:
            r = requests.get(
                "https://html.duckduckgo.com/html/",
                params={"q": q},
                headers={"User-Agent": "AmpliagroBot/1.0"},
                timeout=6,
            )
            html = r.text
            # extrai 3 snippets simples
            snippets = re.findall(
                r'<a[^>]+class="result__a"[^>]*>(.*?)</a>.*?<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
                html,
                re.S,
            )
            # fallback: captura result__snippet
            if not snippets:
                snippets = [
                    (m, "")
                    for m in re.findall(r'class="result__snippet"[^>]*>(.*?)</', html)[
                        :3
                    ]
                ]
                snippets = [
                    (re.sub(r"<[^>]+>", "", a)[:80], re.sub(r"<[^>]+>", "", b)[:180])
                    for a, b in snippets
                ]
            else:
                snippets = [
                    (re.sub(r"<[^>]+>", "", a)[:80], re.sub(r"<[^>]+>", "", b)[:180])
                    for a, b in snippets[:3]
                ]
            if not snippets:
                snippets = [(q, "Sem resultado web, responda com dados locais.")]
            return JsonResponse(
                {
                    "q": q,
                    "snippets": [{"title": t, "snippet": s} for t, s in snippets[:3]],
                }
            )
        except Exception as e:
            return JsonResponse(
                {
                    "q": q,
                    "snippets": [
                        {"title": q, "snippet": f"Offline ou erro web: {str(e)[:60]}"}
                    ],
                }
            )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
