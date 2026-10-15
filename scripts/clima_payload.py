"""Dump do payload REAL de `/api/weather/` para o harness de JavaScript.

Existe para os dois lados da verificação viverem em sítios diferentes e
reproduzíveis: este Python fala com o servidor, e `verifica_clima_chat.mjs`
fala com o JavaScript do navegador. Nenhum dos dois sabe do outro — que é o
que os mantém honestos.

    python scripts/clima_payload.py [caminho.json]

Com `[saida]` escreve em ficheiro (UTF-8, sem escapes). Sem argumento,
imprime em stdout. Os valores vêm do servidor de verdade, com o fallback
nomeado a entrar quando não há rede nem chave — que é exactamente o caso em
que o número é inventado e o carimbo tem de sobreviver.
"""

from __future__ import annotations

import json
import os
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

import django  # noqa: E402

django.setup()


def main() -> int:
    from app.api.views.iot import _get_real_weather
    from app.models import Propriedade

    destino = sys.argv[1] if len(sys.argv) > 1 else None

    prop = Propriedade.objects.exclude(cidade="").order_by("id").first()
    if prop is None:
        print(
            "não há propriedade com cidade; cria uma primeiro",
            file=sys.stderr,
        )
        return 2

    # `_get_real_weather` é a de `utils` — a mesma que a rota usa. Chamá-la
    # pelo nome da rota (`iot._get_real_weather`) seria mais honesto, e o
    # harness de teste já prova que são a mesma função.
    payload = _get_real_weather(prop)
    if payload is None:
        print("a propriedade não tem cidade; nada a medir", file=sys.stderr)
        return 2

    texto = json.dumps(payload, ensure_ascii=False, indent=2)
    if destino:
        with open(destino, "w", encoding="utf-8") as f:
            f.write(texto)
        print(f"payload escrito em {destino}", file=sys.stderr)
    else:
        print(texto)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
