# G-06 — MixPastagem (mix forrageiro por piquete)

## Por que existe

`Piquete` (`pecuaria.py:189-216`) tem área/capacidade/status/animais, mas não diz o que está plantado nele. Sem o mix, a capacidade UA/ha é número sem lastro — exatamente o que VISAO §2.1 proíbe (número sem origem).

## Cirurgia

1. `MixPastagem` em `app/models/pecuaria.py` (ao lado de `Piquete`):
   - `piquete` FK CASCADE related `mixes` (mix morre com o piquete; sem piquete não há mix)
   - `cultura` FK PROTECT (oitavo PROTECT; estender teste cascata) — espécie forrageira do catálogo
   - `pct` Decimal(5,2) com Min/Max 0-100 — 0 aqui é soma válida (0% da espécie), não razão
   - `taxa_semeadura_kg_ha` Decimal(null) — null até declarar
   - `data_semeadura` Date(null)
   - `fonte_dado` default `declarado`
   - unique_together (piquete, cultura)
2. Validação de soma 100%: **aviso, não bloqueio**. Bloquear soma != 100 impede piquete com área não semeada (aceiro, cocho) — inventar exigência para ter o que registrar (crítica `producao.py:471-472`). `clean()` emite `ValidationError` só se soma > 100 (impossível físico); soma < 100 passa com campo `pct_nao_atribuido` calculado (100 - soma, pode ser positivo; nunca negativo).
3. Serializer + ViewSet escopo `propriedade` via `piquete__propriedade__user` (piquete não tem user direto — atravessar como `MovimentoEstoque` atravessa `rastro_item__propriedade__user`, `rastreabilidade.py:386-389`).
4. Teste: mix 60+30 passa com `pct_nao_atribuido`=10; 60+50 recusa; DELETE piquete leva mixes; DELETE cultura com mix dá ProtectedError.

## O que NÃO entra

- Sem taxa recomendada por espécie (tabela sem fonte = meta), sem tela, sem cálculo de suporte UA (isso é G futuro com lastro).

## Critério de saída

- Piquete com mix soma ≤ 100 sempre; `pct_nao_atribuido` visível no GET; nenhuma taxa gerada pelo sistema.
