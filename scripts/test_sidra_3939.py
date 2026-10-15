import json
import urllib.error
import urllib.request

# Test different URL formats for table 3939
formats = [
    "https://apisidra.ibge.gov.br/values/t/3939/n3/35/D4/all/v/105/p/2022?formato=json",
    "https://apisidra.ibge.gov.br/values/t/3939/n3/35/D4/0/v/105/p/2022?formato=json",
    "https://apisidra.ibge.gov.br/values/t/3939/n3/35/cD4/all/v/105/p/2022?formato=json",
    "https://apisidra.ibge.gov.br/values/t/3939/n3/35/v/105/p/2022/d4/0?formato=json",
]

for fmt in formats:
    try:
        req = urllib.request.Request(fmt, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            print(f"{fmt[:80]} -> {len(data)} rows")
            if len(data) > 1:
                for row in data[1:3]:
                    d4c = row.get("D4C", "")
                    d4n = row.get("D4N", "")
                    v = row.get("V", "")
                    print(f"  D4C={d4c} D4N={d4n} V={v}")
    except urllib.error.HTTPError as e:
        print(f"{fmt[:80]} -> HTTP {e.code} {e.read().decode()[:100]}")
    except Exception as e:
        print(f"{fmt[:80]} -> {e}")
