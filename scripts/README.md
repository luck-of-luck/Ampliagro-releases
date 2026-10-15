# Scripts — Ampliagro

> **Raiz:** `C:\Trabalho\Projetos\Ativos\Ampliagro\scripts\`

Scripts Python utilitários movidos da raiz para `scripts/` em 2026-08-30.

| Grupo | Exemplos | Para quê |
|---|---|---|
| `check_*.py` | `check_culture_sources.py`, `check_groups.py`, `check_bom.py` | Auditoria de culturas / IBGE / grupos |
| `find_*.py` | `find_modal.py`, `find_click_handler.py`, `find_render2.py` | Caça handlers, modais, triggers no JS/templates |
| `get_ibge_*.py` | `get_ibge_full.py`, `get_ibge_func.py` | Testa proxy IBGE/SIDRA |
| `test_*.py` | `test_pevs_fix.py`, `test_sidra_3939.py`, `test_proxy_logic.py` | Provas de PEVS, proxy, SIDRA |
| `_check.py`, `_check2.py`, `_find_unbalanced.py`, `_fix_all.py` | — | Checagem de sintaxe/imports, chaves desbalanceadas, fix em lote |
| `verificar_*.py`, `verifica_*.mjs` | `verificar_regressoes.py`, `verificar_mcp_amplia.py` | Verificação de regressões e do MCP |
| `split_*.py`, `patch_relations.py` | `split_views.py`, `split_models.py` | Refatorações pontuais de estrutura |
| `*.mjs` / `rodar_testes_cjs.mjs` | — | Ponte para os testes `.cjs` do frontend |
| `backup_db.py`, `limpar_tabelas_orfas.py`, `timescale-init.sql` | — | Operação de banco e TimeSeries |

## Uso

```bash
# a partir da raiz
python scripts/_check.py
python scripts/check_culture_sources.py
python scripts/test_pevs_fix.py
```

`scripts/rodar_testes_cjs.mjs` roda os testes `.cjs` de `app/static/js/` e é o
mesmo que `npm run test:cjs`.

Estes scripts usam paths relativos à raiz (`app/`, `config/`), então o `cwd`
precisa ser a raiz do projeto. Os `.bat` em `tools\bat\` já fazem
`cd /d "%~dp0\..\.."` antes de chamar `python`.

## Migração

* **Antes:** `C:\Users\lucas\Documents\Projetos_geral\Ampliagro\_check.py`
* **Agora:** `C:\Trabalho\Projetos\Ativos\Ampliagro\scripts\_check.py`
* Stubs não necessários — chame por `python scripts\<arquivo>.py`
