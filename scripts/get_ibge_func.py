import sys

sys.stdout.reconfigure(encoding="utf-8")

with open(r"app/api/views.py", encoding="utf-8", errors="ignore") as f:
    c = f.read()

idx = c.find("def ibge_proxy_data")
# Find the function body
pos = c.find("{", idx)
brace = 1
start = pos + 1
while pos < len(c):
    pos += 1
    ch = c[pos]
    if ch == "{":
        brace += 1
    elif ch == "}":
        brace -= 1
        if brace == 0:
            print(c[idx : pos + 1])
            break
