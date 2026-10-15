import io

CAM = "tests/unit/ia_rail_dom.test.js"
t = io.open(CAM, encoding="utf-8").read()

# Encontrar o describe
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

if fim:
    print(f"Total chars no describe: {fim - start}")
    # Verificar se há }) extra
    bloco = t[start:fim]
    # Contar it(
    its = bloco.count("it(")
    print(f"Total its: {its}")
    # Contar });
    fecha = bloco.count("});")
    print(f"Total }});: {fecha}")

    # Verificar balanceamento
    abertas = bloco.count("{")
    fechadas = bloco.count("}")
    print(f"{{ : {abertas}, }} : {fechadas}")
