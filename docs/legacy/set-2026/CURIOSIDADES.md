# Curiosidades — Dados de Mercado do Ampliagro

> **Projeto:** `C:\Trabalho\Projetos\Ativos\Ampliagro`  •  **Atualizado:** 2026-08-30  •  **Grafo:** 1809 nodes / 3501 edges / 170 comunidades (graphify update 2026-08-30, commit atual)
> **Localização docs:** `docs/CURIOSIDADES.md` (movido de raiz para `docs/` em 2026-08-30 — stub na raiz redireciona)

## O que este documento contém

Uma auditoria completa das 139 culturas do grupo **Plantio & Cultivo**,
mapeando quais têm dados reais (IBGE/SIDRA ou AgroDoc) e quais usam
**valores sintéticos (fallback)** — ou seja, "chutações" educadas.

---

## O Cenário Geral

| Status | Quantidade | % |
|---|---|---|
| Dados reais do IBGE/SIDRA | 60 culturas | 43% |
| **Fallback sintético** | **79 culturas** | **57%** |
| Sem dado nenhum | 0 | 0% |

**Conclusão:** Maioria das culturas do Ampliagro exibe dados
de fallback (valores estimados). 3 culturas com mapeamento IBGE
quebrado foram **corrigidas** — agora usam fallback corretamente
para nunca mais retornar `no_data`.

---

## As 79 culturas que SÓ TÊM FALLBACK

Nenhuma dessas culturas tem mapeamento IBGE/SIDRA ativo.
Os valores que aparecem nos cards vêm exclusivamente do
`fallback_data.py` — números razoáveis para uma fazenda típica,
mas **não são dados oficiais**. Inclui 3 culturas que tinham
mapeamentos IBGE quebrados e foram corrigidas para usar fallback.

### Frutas (24) — o grupo mais carente

| Cultura | Notas |
|---|---|
| Nectarina | Sem IBGE, sem AgroDoc |
| Ameixa | Sem IBGE, sem AgroDoc |
| Jaca | Sem IBGE |
| Graviola | Sem IBGE |
| Cupuaçu | Sem IBGE |
| Açaí | **TEM IBGE** (5457/45982) ✓ |
| Buriti | Sem IBGE |
| Bacuri | Sem IBGE |
| Cajá | Sem IBGE |
| Murici | Sem IBGE |
| Pitanga | Sem IBGE |
| Jabuticaba | Sem IBGE |
| Kiwi | Sem IBGE |
| Morango | Sem IBGE |
| Framboesa | Sem IBGE |
| Amora | Sem IBGE |
| Acerola | Sem IBGE |
| Carambola | Sem IBGE |
| Atemoia | Sem IBGE |
| Pinha | Sem IBGE |
| Pequi | Sem IBGE |
| Limão | **TEM IBGE** ✓ |
| Tangerina | **TEM IBGE** ✓ |
| Pêssego | **TEM IBGE** ✓ |

> Nota: Limão, Tangerina e Pêssego estão na lista correta de frutas com
> IBGE (aparecem em `IBGE_TABELAS` e `PRODUCT_MAP`). Os que não têm
> checkmark realmente não têm IBGE.

### Hortaliças (28) — quase todas sem IBGE

| Cultura | Notas |
|---|---|
| Alface | Sem IBGE |
| Rúcula | Sem IBGE |
| Agrião | Sem IBGE |
| Espinafre | Sem IBGE |
| Couve | Sem IBGE |
| Brócolis | Sem IBGE |
| Couve-flor | Sem IBGE |
| Repolho | Sem IBGE |
| Cenoura | Sem IBGE |
| Beterraba | Sem IBGE |
| Rabanete | Sem IBGE |
| Inhame | Sem IBGE |
| Cará | Sem IBGE |
| Pimentão | Sem IBGE |
| Pimenta | Sem IBGE |
| Berinjela | Sem IBGE |
| Quiabo | Sem IBGE |
| Pepino | Sem IBGE |
| Abóbora | Sem IBGE |
| Abobrinha | Sem IBGE |
| Chuchu | Sem IBGE |
| Vagem | Sem IBGE |
| Milho Verde | Sem IBGE |
| Alcachofra | Sem IBGE |
| Aspargo | Sem IBGE |
| Salsinha | Sem IBGE |
| Cebolinha | Sem IBGE |
| Coentro | Sem IBGE |
| Manjericão | Sem IBGE |

### Florestais (11) — nenhuma tem IBGE

| Cultura |
|---|
| Eucalipto |
| Pinus |
| Teca |
| Mogno |
| Cedro |
| Ipê |
| Araucária |
| Sândalo |
| Bambu |
| Acácia |
| Paricá |

### Especiarias (8) — nenhuma tem IBGE

| Cultura |
|---|
| Canela |
| Cravo-da-índia |
| Noz-moscada |
| Gengibre |
| Açafrão |
| Baunilha |
| Cominho |
| Cúrcuma |

### Medicinais (9) — nenhuma tem IBGE

| Cultura |
|---|
| Camomila |
| Hortelã |
| Capim-limão |
| Alecrim |
| Orégano |
| Erva-doce |
| Guaco |
| Babosa |
| Equinácea |

### Oleaginosas (4) — sem IBGE

| Cultura | Notas |
|---|---|
| Soja (Oleaginosa) | Subproduto, sem IBGE próprio |
| Canola | Sem IBGE |
| Linhaça | Sem IBGE |
| Chia | Sem IBGE |

### Grãos (2) — sem IBGE

| Cultura |
|---|
| Quinoa |
| Amaranto |

### Ornamentais (3) — sem IBGE

| Cultura |
|---|
| Flores de Corte |
| Plantas Envasadas |
| Mudas Florestais |

---

## As 3 culturas com mapeamento IBGE quebrado — CORRIGIDAS

Essas culturas tinham blocos `ibge` no `cultures-config.json` que
apontavam para códigos SIDRA incorretos/promíscuos e o frontend
tentava buscá-las via proxy, resultando em `no_data`.

Correções aplicadas:
- `cultura-lentilha`: removido `ibge` do config (código 40116=Linho)
- `cultura-grao-de-bico`: removido `ibge` do config (código 40111=Fava) e removido de `PRODUCT_MAP`
- `cultura-gergelim`: removido `ibge` do config (código 40123=Rami)

Todas agora permanecem no fallback e o frontend não tenta consultá-las via IBGE.

---

## Dados que são reais de verdade

As 60 culturas com dados IBGE/SIDRA reais usam a **tabela 5457**
(Produção Agrícola Municipal) e retornam 4 variáveis históricas:
Quantidade Produzida, Área Plantada, Rendimento Médio, Valor da
Produção. Os valores são oficiais do IBGE.

Além disso, **Soja** e **Milho** também têm dados do **AgroDoc**
(preço de saca atualizado), que é a única fonte com preço real
de mercado.

### PEVS (Produção Extração Vegetal e Silvicultura)

Para culturas florestais e extrativas que não cobertas pela tabela
5457 (PAM), o proxy agora utiliza também as tabelas PEVS:

| Tabela | Descrição | Produtos incluídos |
|---|---|---|
| 289 | Extração Vegetal | Buriti (fibra), Pequi (amêndoa) |
| 291 | Silvicultura | Eucalipto (madeira), Pinus (lenha), Acácia-negra (casca) |

PEVS retorna 2 variáveis: Quantidade Produzida e Valor da Produção
(sem dados de área ou rendimento médio, pois são atividades extrativas).

---

## O que significa "fallback"

O `fallback_data.py` contém uma fazenda imaginária para cada cultura:
- Área plantada típica (ex: 20 ha de tomate, 3000 ha de soja)
- Produtividade média brasileira (ex: 60 t/ha de tomate)
- Preço estimado (ex: R$ 137,00 a saca de soja)
- Receita calculada

Os números são baseados em médias nacionais (IBGE, Conab) mas
**não são específicos da fazenda do usuário** — servem apenas para
mostrar gráficos e indicadores de exemplo.

---

## Resumo em uma frase

**Das 139 culturas do Ampliagro, ~65 (47%) têm dados oficiais
do IBGE/SIDRA ou PEVS. As outras ~74 (53%) usam valores aproximados de um
"fazendinha hipotética". Inclui 5 culturas com dados PEVS (florestais/extrativos),
3 mapeamentos IBGE corrigidos para usar fallback, e ~66 culturas sem dados
oficiais capturáveis.**

---

## Bônus: culturas com dados no backend mas sem frontend

Existem 6 culturas que o proxy IBGE conhece (têm entrada em
`IBGE_TABELAS` e `PRODUCT_MAP`) mas **não existem como cultura
no frontend** (`cultures-config.json`). Ou seja: os dados estão
prontos para serem usados, mas não há uma cultura para exibi-los.

| Cultura | Código SIDRA |
|---|---|
| Cacau | 40141 |
| Erva-mate | 40258 |
| Azeitona | 40133 |
| Palmito | 45983 |
| Noz | 40266 |
| Marmelo | 40265 |

**Por que isso importa:** se um dia o usuário quiser cadastrar
Cacau, os dados de mercado já estão disponíveis — mas a cultura
precisa ser adicionada ao `cultures-config.json` para aparecer
na lista de culturas do sistema.

---

## 📦 Reorganização 2026-08-30 — Novo caminho do projeto

* **Caminho antigo:** `C:\Users\lucas\Documents\Projetos_geral\Ampliagro`
* **Caminho novo:** `C:\Trabalho\Projetos\Ativos\Ampliagro`  (definido em `.hurc-harness/state/session/index.json` e `AGENTS.md`)
* **Docs movidos para:** `docs/` (`docs/CURIOSIDADES.md`, `docs/PLANO_RESOLUCAO.md`, `docs/COMOESTAOHTML`, `docs/index_bekup_dashbord`)
* **.bat movidos para:** `tools/bat/` (`demo.bat`, `git-auto.bat`, `git-push.bat`, `runserver_dev.bat`) — stubs na raiz redirecionam via `%~dp0tools\bat\`
* **.ps1 movido para:** `tools/ps1/git-auto.ps1` — usa `$PSScriptRoot\..\..` para achar a raiz
* **_*.py movidos para:** `scripts/` (`_check.py`, `_check2.py`, `_find_unbalanced.py`, `_fix_all.py`)
* **Grafo atualizado:** `graphify update` em 2026-08-30 → 1106→**1809 nodes**, 2229→**3501 edges**, 124→**170 comunidades** (ver `graphify-out/GRAPH_REPORT.md` e `graphify-out/graph.json`)

> Para recriar o grafo após novas mudanças: `graphify update "C:\Trabalho\Projetos\Ativos\Ampliagro"` (sem custo LLM) e `graphify label` se quiser renomear comunidades com LLM.
