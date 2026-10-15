import io

CAM = "tests/unit/ia_rail_dom.test.js"
t = io.open(CAM, encoding="utf-8").read()

# Remover o lixo "return codecs.charmap_encode..." que ficou após o }); do it('clicar no X...')
# O padrão: '    );\n\n    return codecs.charmap_encode...' deve virar '    );\n'
# O arquivo tem essa sequência logo após o it('clicar no X...')

# Procurar o padrão: '    );\n\n    return codecs.charmap_encode'
# Substituir por: '    );\n'

antes = (
    "    );\n\n    return codecs.charmap_encode(input,self.errors,encoding_table)[0]"
)
depois = "    );\n"
idx = t.find(antes)
if idx >= 0:
    t = t.replace(antes, depois)
    print(f"Corrigido na posição {idx}")
    io.open(CAM, "w", encoding="utf-8").write(t)
    print("OK")
else:
    print("Padrão não encontrado, buscando...")
    idx = t.find("return codecs.charmap_encode")
    if idx >= 0:
        print(f"Achou return codecs em {idx}")
        print(repr(t[idx - 100 : idx + 200]))
