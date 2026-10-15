import sys, re, pathlib
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
t = pathlib.Path('tests/unit/ia_rail_dom.test.js').read_text(encoding='utf-8')
for m in list(re.finditer(r'abreMenu|submenu|ia-rail-menu', t))[:5]:
    print('=' * 60)
    print(t[max(0, m.start() - 300):m.start() + 400].replace('\r', ''))

