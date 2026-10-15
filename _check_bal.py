import io
import re

CAM = "tests/unit/ia_rail_dom.test.js"
t = io.open(CAM, encoding="utf-8").read()

idx = t.find("describe('o print da tela'")
print(f"describe em {idx}")

start = t.find("{", idx)
print(f"inicio bloco em {start}")

d = 0
fim = None
for k in range(start, len(t)):
    if t[k] == "{":
        d += 1
    elif t[k] == "}":
        d -= 1
        if d == 0:
            fim = k + 1
            print(f"Fim do describe em {fim}")
            break
    if k > start + 50000:
        print("Muito longe, parando")
        break

if fim:
    print(f"Total chars no describe: {fim - start}")
    bloco = t[start:fim]
    its = bloco.count("it(")
    print(f"Total its: {its}")
    fecha = bloco.count("});")
    print(f"Total }});: {fecha}")

    abertas = bloco.count("{")
    fechadas = bloco.count("}")
    print("{{ : {}, }} : {}".format(abertas, fechadas))

    # Procurar }); extras
    for m in re.finditer(r"^\s*\}\);\s*$", bloco, re.MULTILINE):
        print("  }); extra na pos {} do bloco".format(m.start()))
