import io

CAM = "tests/unit/ia_rail_dom.test.js"
t = io.open(CAM, encoding="utf-8").read()

# Buscar variações
termos = [
    "clicar no X",
    "clicar no X cancela",
    "clicar no X cancela a sele",
    "cancelar a sele",
    "cancelar",
    "it('clicar",
    'it("clicar',
]
for termo in termos:
    idx = t.find(termo)
    if idx >= 0:
        print(f'Achou: "{termo}" em {idx}')
    else:
        print(f"NÃO achou: {termo}")

# Buscar todos os "it("
idx = 0
count = 0
while True:
    idx = t.find("it(", idx)
    if idx < 0:
        break
    # Pegar o nome do teste
    fim = t.find(")", idx + 3)
    if fim > idx:
        nome = t[idx : fim + 1]
        if "clicar" in nome.lower() or "cancel" in nome.lower():
            print(f"  Achou teste: {nome[:80]} em {idx}")
    idx = fim + 1
