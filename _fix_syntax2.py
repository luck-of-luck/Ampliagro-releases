import io

CAM = "tests/unit/ia_rail_dom.test.js"
t = io.open(CAM, encoding="utf-8").read()

# O problema: em "clicar no X cancela a seleção", há um }); extra
# Procurar o padrão problemático
problema = """      expect(r.motivo).toBe('cancelado');
    });

    return codecs.charmap_encode"""

# Verificar se existe
idx = t.find(
    "expect(r.motivo).toBe('cancelado');\n    });\n\n    return codecs.charmap_encode"
)
if idx >= 0:
    print("Achou o problema")
    # Corrigir: remover o }); extra e o return codecs... que é lixo
    # O padrão é:
    #       expect(r.motivo).toBe('cancelado');
    #     });
    #
    #     return codecs.charmap_encode...
    # Deveria ser apenas:
    #       expect(r.motivo).toBe('cancelado');
    #     });
    # E depois continua com o próximo it
    t = t.replace(
        "      expect(r.motivo).toBe('cancelado');\n    });\n\n    return codecs.charmap_encode",
        "      expect(r.motivo).toBe('cancelado');\n    });\n\n    /* AREA_MENOR dispara recusa",
    )
    print("Corrigido")
    io.open(CAM, "w", encoding="utf-8").write(t)
    print("ok")
else:
    print("Padrão não encontrado, buscando variações...")
    # Buscar variações
    idx = t.find("expect(r.motivo).toBe('cancelado')")
    if idx >= 0:
        print("Achou expect em", idx)
        print(repr(t[idx : idx + 200]))
    else:
        print("Nem o expect achou")
