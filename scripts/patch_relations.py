import os
import re

directory = "app/models"

# The regex looks for ForeignKey, OneToOneField, or ManyToManyField,
# followed by an opening parenthesis, optional whitespace,
# and an unquoted model name (which starts with an uppercase letter).
pattern = re.compile(
    r"(models\.(?:ForeignKey|OneToOneField|ManyToManyField)\s*\(\s*)([A-Z][A-Za-z0-9_]*)"
)

for filename in os.listdir(directory):
    if filename.endswith(".py") and filename != "__init__.py":
        filepath = os.path.join(directory, filename)
        with open(filepath, encoding="utf-8") as f:
            content = f.read()

        # Replace occurrences
        new_content = pattern.sub(r'\1"\2"', content)

        if new_content != content:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Patched {filename}")

print("Done patching model references.")
