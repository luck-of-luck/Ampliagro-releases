import io
import re

CAM = "tests/unit/ia_rail_dom.test.js"
t = io.open(CAM, encoding="utf-8").read()

# Find the describe block for 'o print da tela'
idx = t.find("o print da tela")
print("o print da tela at", idx)

start = t.find("{", t.find("o print da tela"))
print("start brace at", t.find("{", t.find("o print da tela")))

d = 0
fim = None
start_idx = t.find("{", t.find("o print da tela"))
for k in range(start_idx, len(t)):
    c = t[k]
    if c == "{":
        d += 1
    elif c == "}":
        d -= 1
        if d == 0:
            print("Fim do describe em", k)
            break
