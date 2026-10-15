import json
import urllib.request

# Test table 3939 (PPM livestock) for Bovino in SP
url = "https://apisidra.ibge.gov.br/values/t/3939/n3/35/c79/2670/p/2020-2024/v/105/f/n?formato=json"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=20) as resp:
    data = json.loads(resp.read().decode())
    print("Tab3939 (Bovino/SP):", len(data), "rows")
    for row in data[1:]:
        print(" ", row["D4N"], ":", row["V"], "cabecas")
    print()

# Test table 3940 (aquaculture) for Tilapia in SP
url2 = "https://apisidra.ibge.gov.br/values/t/3940/n3/35/c654/32877/p/2020-2024/v/4146,215/f/n?formato=json"
req2 = urllib.request.Request(url2, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req2, timeout=20) as resp2:
    data2 = json.loads(resp2.read().decode())
    print("Tab3940 (Tilapia/SP):", len(data2), "rows")
    for row in data2[1:]:
        print(" ", row["D3N"], "|", row["D4N"], "=", row["V"])
