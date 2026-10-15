"""Ranking de ensaio de cultivares — funcao PURA (sem BD, sem request).

Pura de proposito: o ranking e' aritmetica sobre faixas, e aritmetica
testavel sem banco nao quebra quando o schema muda. A view chama isto;
o teste unitario tambem, sem `TestCase` do Django.

sem_dado propaga: testemunha sem medicao -> delta None (nao 0). Media
sobre zero medicoes -> None. Um ranking que inventa delta elegendo
vencedor sem dado e' a "mesa invisivel" do plano-correcao G-03.
"""


def ranking_ensaio(faixas, testemunha_id=None):
    """faixas: lista de dicts {cultivar_id, produtividade_sc_ha|None}.

    Devolve lista ordenada [{cultivar_id, media_sc_ha|None, delta_pct|None}].
    Ordena por media desc; None por ultimo (sem_dado nao ganha ranking).
    """
    from decimal import Decimal

    grupos = {}
    for f in faixas or []:
        cid = f.get("cultivar_id")
        if cid is None:
            continue
        grupos.setdefault(cid, []).append(f.get("produtividade_sc_ha"))

    linhas = []
    for cid, valores in grupos.items():
        nums = [float(v) for v in valores if v is not None]
        media = sum(nums) / len(nums) if nums else None
        linhas.append({"cultivar_id": cid, "media_sc_ha": media, "delta_pct": None})

    base = None
    if testemunha_id is not None:
        for linha in linhas:
            if linha["cultivar_id"] == testemunha_id:
                base = linha["media_sc_ha"]
                break
    if base is not None:
        for linha in linhas:
            if linha["media_sc_ha"] is not None:
                linha["delta_pct"] = round(
                    (linha["media_sc_ha"] - base) / base * 100, 2
                )

    linhas.sort(key=lambda l: (l["media_sc_ha"] is None, -(l["media_sc_ha"] or 0)))
    # Decimal -> float honesto p/ JSON (sem str fantasma).
    for linha in linhas:
        if isinstance(linha["media_sc_ha"], Decimal):
            linha["media_sc_ha"] = float(linha["media_sc_ha"])
    return linhas
