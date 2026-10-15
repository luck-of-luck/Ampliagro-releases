import io

t = open("tests/unit/ia_rail_dom.test.js", encoding="utf-8").read()
i = t.find("  describe('os botoes que produzem pecas')")
assert i > 0, "nao achei o describe dos botoes"

d = 0
start = t.find("{", i)
fim = None
for k in range(start, len(t)):
    if t[k] == "{":
        d += 1
    elif t[k] == "}":
        d -= 1
        if d == 0:
            fim = k + 1
            break
io.open("bloco_antigo2.txt", "w", encoding="utf-8").write(t[i:fim])
print("de", i, "ate", fim, "tamanho", fim - i)
print("comeca:", repr(t[i : i + 45]))
print("acaba:", repr(t[fim - 50 : fim]))
