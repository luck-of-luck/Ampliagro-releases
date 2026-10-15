import io

t = open("tests/unit/ia_rail_dom.test.js", encoding="utf-8").read()
i = t.find("describe('o print da tela'")
j = t.find("describe('o print so existe no app")
print("de", i, "ate", j, "tamanho", j - i)
io.open("print_old.txt", "w", encoding="utf-8").write(t[i : j - 2])
