import io

CAM = "tests/unit/ia_rail_dom.test.js"
t = io.open(CAM, encoding="utf-8").read()

# O problema: linha 606 tem '    );' linha 607 vazia, linha 607 tem lixo 'return codecs.charmap_encode...'
# Vamos remover a linha vazia + a linha de lixo
# Procurar o padrão: '    );\n\n    return codecs.charmap_encode'
idx = t.find(
    "    );\n\n    return codecs.charmap_encode(input,self.errors,encoding_table)[0]"
)
if idx >= 0:
    # Substituir por apenas '    );\n'
    novo = (
        t[:idx]
        + "    );\n"
        + t[
            idx
            + len(
                "    );\n\n    return codecs.charmap_encode(input,self.errors,encoding_table)[0]"
            ) :
        ]
    )
    io.open(CAM, "w", encoding="utf-8").write(novo)
    print("Corrigido!")
else:
    print("Padrão não encontrado, buscando...")
    idx2 = t.find("return codecs.charmap_encode")
    if idx2 >= 0:
        print(f"Achou em {idx2}: {repr(t[idx2 : idx2 + 80])}")
    else:
        print("Nem o return codecs achou")
