# G-05 — Alerta safrinha (só código, sem model)

## Por que só código

Todos os campos existem: `ZARC.data_fim_plantio` (`producao.py:393`), `Cultivar.ciclo_max` (G-01), motor proativo com `regras_deterministicas` + `IAAlertaProativo` (`proativo.py`, `copiloto.py:729-737` manda importar a regra, não duplicar). Criar model seria gerar superfície para cumprir meta (VISAO §0.3).

## Cirurgia

1. Função pura em `app/ia/proativo.py` ao lado de `regras_deterministicas`:
   - `limite_safrinha(fim_janela: date, ciclo_dias: int | None) -> date | None` — None quando ciclo ou janela ausentes (sem_dado propaga, não inventa).
   - `risco_safrinha(hoje, limite) -> bool | None` — None quando limite None.
2. Regra no mesmo `regras_deterministicas` (não em handler solto — a trava vive no handler central, lição `chamado_intents.py:596`): para cada `Safra` com `cultura`+`ZARC` do município e `cultivar.ciclo_max`, se `hoje + ciclo > fim_janela` → `IAAlertaProativo` com `fonte="Embrapa — ZARC"` ao lado (VISAO Fase 1.1: fonte ao lado da data).
3. ZARC vazia (VISAO §0.2: 0 registros) → zero alertas, zero datas geradas. Teste varre o payload à procura de ISO date com ZARC vazia (espelho Fase 1.1).
4. Não alertar sobre safra concluída/colhida (lição `copiloto.py:729-731`: alertar sobre trabalho feito desliga a notificação).

## Critério de saída

- Com ZARC semeada + cultivar com ciclo: alerta dispara no dia certo. Com ZARC vazia: nenhum alerta e nenhum date no payload. Safra colhida: silêncio.
