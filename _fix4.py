import io

CAM = "tests/unit/ia_rail_dom.test.js"
t = io.open(CAM, encoding="utf-8").read()

# O erro está na linha 606: há um '});' extra seguido de 'return codecs.charmap_encode...'
# Vou remover tudo a partir de '    );\n\n    return codecs.charmap_encode'
# até o próximo 'it(' ou 'describe(' ou fim do arquivo

idx = t.find("    );\n\n    return codecs.charmap_encode")
if idx >= 0:
    # Encontrar o próximo 'it(' ou 'describe(' após o lixo
    fim_lixo = t.find("\n    it(", idx)
    if fim_lixo < 0:
        fim_lixo = t.find("\n    describe(", idx)
    if fim_lixo < 0:
        fim_lixo = len(t)

    # Remover o lixo
    novo = t[:idx] + "\n\n" + t[fim_lixo:]
    io.open(CAM, "w", encoding="utf-8").write(novo)
    print(f"Removido lixo de {idx} a {fim_lixo}")
    print("OK")
else:
    print("Padrão não encontrado")
