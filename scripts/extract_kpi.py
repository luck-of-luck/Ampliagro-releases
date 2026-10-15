import re

with open("app/templates/index.html", encoding="utf-8") as f:
    text = f.read()

for m in re.finditer(r"<script.*?>.*?</script>", text, re.DOTALL):
    if "kpi-accordion-container" in m.group(0):
        with open("scratch/kpi_script.js", "w", encoding="utf-8") as out:
            out.write(m.group(0))
        print("Script extracted to scratch/kpi_script.js")
        break
