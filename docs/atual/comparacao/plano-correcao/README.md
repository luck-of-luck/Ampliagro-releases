# Plano-correção backend — índice (G-01 a G-06)

> Escopo: só backend. Ordem de execução: FASE 0 → G-01 → G-02 → G-03 → G-04 → G-05 → G-06. G-02 depende de G-01 (FK Cultivar); G-03 depende de G-01 (testemunha); G-05 depende de G-01 (ciclo_max) + ZARC semeada (VISAO Fase 1.1). Nada de G-03 em diante sem G-01 passando no critério de saída.

- [00-ancora-visao.md](00-ancora-visao.md) — FASE 0 + regra de escrita
- [G-01-cultivar.md](G-01-cultivar.md) — Cultivar + Safra.cultivar
- [G-02-lote-semente.md](G-02-lote-semente.md) — LoteSemente 1-1 RastroItem
- [G-03-ensaio-cultivar.md](G-03-ensaio-cultivar.md) — EnsaioCultivar + FaixaEnsaio + ranking puro
- [G-04-viveiro.md](G-04-viveiro.md) — Viveiro + LoteMuda
- [G-05-safrinha.md](G-05-safrinha.md) — só código no proativo
- [G-06-mix-pastagem.md](G-06-mix-pastagem.md) — MixPastagem por piquete
