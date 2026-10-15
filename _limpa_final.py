import io

CAM = "tests/unit/ia_rail_dom.test.js"
t = io.open(CAM, encoding="utf-8").read()

# O teste está em 25000
idx = 25004
start = t.find("{", idx)
print(f"Início do bloco em {t.find('{', 25000)}")

start = t.find("{", 25004)
d = 1
fim_it = None
for k in range(start + 1, len(t)):
    if t[k] == "{":
        d += 1
    elif t[k] == "}":
        d -= 1
        if d == 0:
            fim_it = k + 1
            print(f"Fim do it em {fim_it}")
            break

if fim_it:
    print(f"Fim do it em {fim_it}")
    # Verificar o que vem depois
    prox = t.find("    it(", fim_it)
    if prox < 0:
        prox = t.find("  describe(", fim_it)
    if prox < 0:
        prox = t.find("});", fim_it)
        if prox >= 0:
            prox += 2

    if prox >= 0:
        meio = t[fim_it:prox]
        print(f"Conteúdo entre ({len(meio)} chars): {repr(meio[:500])}")

        if (
            "return codecs" in meio
            or "charmap_encode" in meio
            or "return codecs.charmap_encode" in meio
        ):
            print("ACHOU LIXO!")
            t_limpo = t[:fim_it] + "\n\n" + t[prox:]
            with open("tests/unit/ia_rail_dom.test.js", "w", encoding="utf-8") as f:
                f.write(t[:fim_it] + "\n\n" + t[prox:])
            print("ARQUIVO LIMPO!")
        else:
            print("Sem lixo detectado")
            print(f"Conteúdo: {repr(meio[:300])}")
    else:
        print("Não achou próximo bloco")
else:
    print("Não achou fim do it")
