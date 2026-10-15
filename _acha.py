import io
import re

t = open("tests/unit/ia_rail_dom.test.js", encoding="utf-8").read()
for m in re.finditer(r"describe\('([^']*)'", t):
    print(m.start(), "|", m.group(1))
