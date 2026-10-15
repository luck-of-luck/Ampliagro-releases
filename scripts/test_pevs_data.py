from datetime import date

import requests as req_lib

cy = date.today().year

# Get complete data for PE (26)
url_pe = f"https://apisidra.ibge.gov.br/values/t/289/n3/26/c193/3424/p/{cy - 9}-{cy}/v/allxp/f/n?formato=json"
resp = req_lib.get(url_pe, timeout=10)
data = resp.json()

print("PE (26) complete:")
print(f"Total rows: {len(data)}")
print(f"Columns: {data[0].keys() if data else 'empty'}")
print()
print("Filter out header row (D1N = Unidade da Federação):")
filtered = [row for row in data if row.get("D1N") != "Unidade da Federa\\u00e7\\u00e3o"]
print(f"Filtered rows: {len(filtered)}")
for row in filtered[:5]:
    print(
        f"  D1N: '{row.get('D1N')}', D2N: '{row.get('D2N')}', D3N: '{row.get('D3N')}', D4N: '{row.get('D4N')}', MN: '{row.get('MN')}', V: '{row.get('V')}'"
    )
