import io

CAM = "tests/unit/ia_rail_dom.test.js"
t = io.open(CAM, encoding="utf-8").read()

# O problema: há um }); extra em algum lugar
# Vamos reconstruir a seção problemática limpa

# Encontrar o it('clicar no X cancela a seleção')
idx = t.find("it('clicar no X cancela a sele")
if idx < 0:
    idx = t.find('it("clicar no X cancela a sele')
print(f"Achou it clicar no X em {idx}")

if idx >= 0:
    # Encontrar o fim deste it (o próximo 'it(' ou 'describe(' ou '});' final do describe)
    # Contar chaves a partir do {
    start = t.find("{", idx)
    if start >= 0:
        d = 1
        for k in range(start + 1, len(t)):
            if t[k] == "{":
                d += 1
            elif t[k] == "}":
                d -= 1
                if d == 0:
                    fim_it = k + 1
                    print(f"Fim do it em {fim_it}")
                    # Verificar o que vem depois
                    print(f"Depois do it: {repr(t[fim_it : fim_it + 100])}")
                    break

# Agora vamos limpar: remover qualquer lixo após o it até o próximo it ou describe
# O lixo começa após o fim do it
if fim_it:
    # Procurar o próximo it ou describe
    prox = t.find("    it(", fim_it)
    if prox < 0:
        prox = t.find("  describe(", fim_it)
    if prox < 0:
        prox = t.find("});", fim_it)
        if prox >= 0:
            prox += 2
    print(f"Próximo bloco em {prox}")

    # O que está entre fim_it e prox?
    meio = t[fim_it:prox]
    print(f"Conteúdo entre: {repr(meio[:300])}")

    # Se houver lixo, remover
    if "return codecs" in meio or "charmap_encode" in meio:
        print("ACHOU LIXO!")
        t_limpo = t[:fim_it] + "\n\n" + t[prox:]
        with open("tests/unit/ia_rail_dom.test.js", "w", encoding="utf-8") as f:
            f.write(t_limpo)
        print("LIMPO!")
    else:
        print("Sem lixo detectado nessa região")
