import io

CAM = "tests/unit/ia_rail_dom.test.js"
t = io.open(CAM, encoding="utf-8").read()

# O problema: há um }); extra em algum lugar
# Vamos localizar exatamente onde está o problema

# Primeiro, achar o it('clicar no X cancela a seleção')
idx = t.find("it('clicar no X cancela a sele")
if idx < 0:
    idx = t.find('it("clicar no X cancela a sele')
print(f"Achou it clicar no X em {idx}")

if idx >= 0:
    # Encontrar o fim deste it contando chaves
    start = t.find("{", idx)
    if start >= 0:
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
            # Verificar o que vem depois
            # Procurar o próximo it, describe, ou }); final
            prox = t.find("    it(", fim_it)
            if prox < 0:
                prox = t.find("  describe(", fim_it)
            if prox < 0:
                # Procurar o }); que fecha o describe
                prox = t.find("});", fim_it)
                if prox >= 0:
                    prox += 2

            if prox >= 0:
                meio = t[fim_it:prox]
                print(f"Conteúdo entre fim_it e próximo bloco: {repr(meio[:300])}")

                # Se houver lixo (return codecs, charmap_encode, etc.)
                if "return codecs" in meio or "charmap_encode" in meio:
                    print("ACHOU LIXO!")
                    # Limpar: manter até fim_it, pular até prox
                    t_limpo = t[:fim_it] + "\n\n" + t[prox:]
                    with open(
                        "tests/unit/ia_rail_dom.test.js", "w", encoding="utf-8"
                    ) as f:
                        f.write(t[:fim_it] + "\n\n" + t[prox:])
                    print("ARQUIVO LIMPO!")
                else:
                    print("Sem lixo detectado entre os blocos")
            else:
                print("Não achou próximo bloco")
        else:
            print("Não achou fim do it")
    else:
        print("Não achou início do bloco")
else:
    print("Não achou it clicar no X")
