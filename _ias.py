import json

d = json.load(open("iad.json", encoding="utf-8"))
grupos = {}
for tr in d["testResults"]:
    for a in tr.get("assertionResults", []):
        if a["status"] != "failed":
            continue
        msgs = []
        for m in a.get("failureMessages", []):
            msgs.append(m.strip().split("\n")[0][:200])
        chave = " | ".join(msgs)[:180]
        nome = a["fullName"]
        grupos.setdefault(chave, []).append(nome)

saida = []
for chave, nomes in sorted(grupos.items(), key=lambda kv: -len(kv[1])):
    saida.append(f"### {len(nomes)} testes  =>  {chave}")
    for n in nomes:
        saida.append(f"    - {n}")
    saida.append("")

open("iad_grupos.txt", "w", encoding="utf-8").write("\n".join(saida))
print("grupos:", len(grupos))
for chave, nomes in sorted(grupos.items(), key=lambda kv: -len(kv[1])):
    print(f"{len(nomes):3d}  {chave[:150]}")
