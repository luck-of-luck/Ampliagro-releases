import sys

sys.stdout.reconfigure(encoding="utf-8")

with open(r"app/api/views.py", encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

# Find ibge_proxy_data function
start = None
end = None
for i, line in enumerate(lines):
    if "def ibge_proxy_data" in line:
        start = i
    if (
        start is not None
        and i > start
        and line.strip().startswith("def ")
        and line.strip() != lines[start].strip()
    ):
        end = i
        break
    if start is not None and i > start and line.strip().startswith("@"):
        end = i
        break

# Print the function
func_lines = lines[start:end]
for line in func_lines:
    print(line.rstrip())
