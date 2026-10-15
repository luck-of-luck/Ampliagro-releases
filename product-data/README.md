# Product Data — mapas curados

> `.gitignore` contém `product-data/`: os mapas são gerados localmente.

- `animal_aquatico_real_map.json` — 26 culturas animal/aquático IBGE
- `vegetal_real_map.json` — 29 culturas vegetal IBGE

Cada entrada mapeia o nome da cultura para `grupo`, `ibge` (código SIDRA) e
`agrodoc`. Gerado por `python manage.py seed_*_real --apply`, que escreve em
`product-data/` com espelho na raiz por compatibilidade.
