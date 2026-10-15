import io

CAM = "tests/unit/ia_rail_dom.test.js"
t = io.open(CAM, encoding="utf-8").read()
antes = "      expect(b.getAttribute('aria-pressed')).toBe('true');\n      expect(b).not.toContain('disabled');"
depois = "      expect(b.getAttribute('aria-pressed')).toBe('true');\n      expect(b.outerHTML).not.toContain('disabled');"
assert t.count(antes) == 1, t.count(antes)
io.open(CAM, "w", encoding="utf-8").write(t.replace(antes, depois))
print("ok")
