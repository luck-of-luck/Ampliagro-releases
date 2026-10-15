import json

d = json.load(open("iad2.json", encoding="utf-8"))
print("total", d.get("numTotalTests"), "failed", d.get("numFailedTests"))
n = 0
for tr in d["testResults"]:
    for a in tr.get("assertionResults", []):
        if a["status"] != "failed":
            continue
        n += 1
        nome = a["fullName"]
        msg = ""
        if a.get("failureMessages"):
            msg = a["failureMessages"][0].strip().split("\n")[0][:110]
        print("%2d. %s" % (n, nome[:95]))
        print("     " + msg)
