import io, re

t = io.open(r"app/guias/catalogo.py", encoding="utf-8").read()
matches = re.findall(r'rota\s*:\s*"([^"]+)"', t)
print("Total rotas:", len(matches))
for m in matches:
    print("  " + m)
