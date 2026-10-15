"""Sondagem em massa: que concorrentes tem pagina oficial alcançavel?

So uma celula `F` exige uma citacao numa pagina alcancada. Antes de escrever
uma so celula nova, e' preciso saber **que paginas existem e respondem**. Esta
sonda faz isso para os 100, e separa três situacoes:

    ALCANCADA   devolveu texto — daqui pode sair celula `F`
    PARCIAL     respondeu, mas o texto e' curto: SPA, ou pagina de login
    INALCANCAVEL nao respondeu

O resultado diz onde vale a pena gastar o effort de ler.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from concorrentes import CONCORRENTES  # noqa: E402
from verificar_evidencia import buscar, limpar  # noqa: E402

#: Temas que interessam a TUDO o sector. Se um destes aparecer, o produto fala
#: do assunto e ha citacao possivel.
TEMAS = {
    "T": ["traceability", "trazabilidad", "rastreabilidade"],
    "L": ["LCDPR"],
    "N": ["NF-e"],
    "O": ["offline", "sin conexi", "sem internet"],
    "M": ["machine", "machines", "maquina", "telemetr", "ISOBUS", "maquin"],
    "S": ["satellite", "satelit", "satélit", "NDVI", "drone"],
    "A": ["API"],
    "W": ["WhatsApp"],
    "C": ["carbon", "carbono", "emissoes", "emisiones"],
    "I": ["AI", "IA", "inteligencia artificial", "machine learning"],
    "Irr": ["irrigation", "irrigacao", "irrigação"],
    "Cow": ["cattle", "gado", "pecuaria", "pecuária", "bovine", "leche", "leite"],
}


def classificar(url: str) -> tuple[str, str]:
    estado, html = buscar(url, timeout=25)
    if estado != "OK":
        return "INALCANCAVEL", estado
    t = limpar(html)
    if len(t) < 400:
        return "PARCIAL", f"{len(t)} chars — SPA ou pagina de login"
    return "ALCANCADA", f"{len(t):,} chars"


if __name__ == "__main__":
    print("=" * 92)
    print("SONDAGEM — as paginas oficiais dos 100 concorrentes")
    print("=" * 92)

    contagem = {"ALCANCADA": 0, "PARCIAL": 0, "INALCANCAVEL": 0, "SEM_FONTE": 0}
    alcancadas: list[tuple[str, str, str, str]] = []
    for i, (nome, _pais, _seg, fonte) in enumerate(CONCORRENTES, 1):
        if not fonte.startswith("http"):
            fonte = "https://" + fonte.lstrip("/")
        if not fonte or fonte == "—":
            contagem["SEM_FONTE"] += 1
            continue
        estado, detalhe = classificar(fonte)
        contagem[estado] += 1
        marca = {"ALCANCADA": "OK  ", "PARCIAL": "PARC", "INALCANCAVEL": "----"}[estado]
        print(
            f"  [{i:3}] {marca} {nome[:30]:32} {fonte[:44]:46} {detalhe[:24]}",
            flush=True,
        )
        if estado == "ALCANCADA":
            alcancadas.append((nome, fonte, "", detalhe))

    print()
    print("=" * 92)
    print("RESUMO")
    print("=" * 92)
    for k, v in contagem.items():
        print(f"  {k:14} {v}")
    print()
    print("  Paginas onde vale a pena procurar citacao:")
    for nome, fonte, _c, detalhe in alcancadas:
        print(f"    {nome:32} {fonte[:50]:52} {detalhe}")
