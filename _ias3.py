import io
import json

d = json.load(open("iad3.json", encoding="utf-8"))
linhas = []
n = 0
for tr in d["testResults"]:
    for a in tr.get("assertionResults", []):
        if a["status"] != "failed":
            continue
        n += 1
        msg = ""
        if a.get("failureMessages"):
            msg = a["failureMessages"][0].strip().split("\n")[0][:120]
        linhas.append("%2d. %s" % (n, a["fullName"][:90]))
        linhas.append("     " + msg)
io.open("iad3.txt", "w", encoding="utf-8").write("\n".join(linhas))
print("falhas:", n)
