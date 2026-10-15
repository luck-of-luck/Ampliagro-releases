import io
import re

CAM = "tests/unit/ia_rail_dom.test.js"
t = io.open(CAM, encoding="utf-8").read()

idx = t.find("describe('o print da tela'")
print("describe em {}".format(idx))

start = t.find("{", idx)
print("inicio bloco em {}".format(start))

d = 0
fim = None
for k in range(start, len(t)):
    if t[k] == "{":
        d += 1
    elif t[k] == "}":
        d -= 1
        if d == 0:
            fim = k + 1
            print("Fim do describe em {}".format(fim))
            break
    if k > start + 50000:
        print("Muito longe, parando")
        break

if fim:
    print("Total chars no describe: {}".format(fim - start))
    bloco = t[start:fim]
    its = bloco.count("it(")
    print("Total its: {}".format(its))
    fecha = bloco.count("});")
    print("Total }});: {}".format(fecha))

    abertas = bloco.count("{")
    fechadas = bloco.count("}")
    print("{{ : {}, }} : {}".format(abertas, fechadas))

    for m in re.finditer(r"^\s*\}\);\s*$", bloco, re.MULTILINE):
        print("  }); extra na pos {} do bloco".format(m.start()))
