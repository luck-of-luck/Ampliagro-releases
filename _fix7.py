import io

CAM = "tests/unit/ia_rail_dom.test.js"
t = io.open(CAM, encoding="utf-8").read()

# O lixo está em: '    );\n\n    return codecs.charmap_encode(input,self.errors,encoding_table)[0]'
# Substituir por apenas '    );\n'
padrao = (
    "    );\n\n    return codecs.charmap_encode(input,self.errors,encoding_table)[0]"
)
subst = "    );\n"
if t.find(padrao) >= 0:
    t = t.replace(padrao, subst)
    io.open(CAM, "w", encoding="utf-8").write(t)
    print("Corrigido com sucesso!")
else:
    print("Padrão não encontrado, tentando busca ampla...")
    idx = t.find("return codecs.charmap_encode")
    if idx >= 0:
        print(f"Encontrado return codecs em {idx}")
    else:
        print("Nem return codecs achou")
    # Tentar busca ampla
    idx = t.find("return codecs")
    if idx >= 0:
        print(f'Achou "return codecs" em {idx}: {repr(t[idx : idx + 100])}')
    else:
        print("Nada de codecs")
