import json

d = json.load(open("iad4.json", encoding="utf-8"))
n = 0
for tr in d["testResults"]:
    for a in tr.get("assertionResults", []):
        if a["status"] != "failed":
            continue
        n += 1
        msg = ""
        if a.get("failureMessages"):
            msg = a["failureMessages"][0].strip().split("\n")[0][:110]
        print("%2d. %s" % (n, a["fullName"][:90]))
        print("     " + msg)
