with open(r"app/templates/index.html", encoding="utf-8", errors="ignore") as f:
    c = f.read()

# Find all calls to showCultureDetail
import re

for m in re.finditer(r"showCultureDetail\([^)]+\)", c):
    start = max(0, m.start() - 100)
    end = min(len(c), m.end() + 50)
    print("=== showCultureDetail call ===")
    print(c[start:end])
    print()

# Also find calls to showCultureMiniPanel
for m in re.finditer(r"showCultureMiniPanel\([^)]+\)", c):
    start = max(0, m.start() - 100)
    end = min(len(c), m.end() + 50)
    print("=== showCultureMiniPanel call ===")
    print(c[start:end])
    print()
