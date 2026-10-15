# G-04 — Viveiro e LoteMuda (muda clonal)

## Por que existe

Nicho 8 (micropropagação/viveiro) não tem nenhum cadastro: muda nasce sem origem. O comprador que paga por procedência (§2.2 VISAO: quem compra o resultado) precisa da cadeia matriz → lote → talhão. Sem isso, a muda é número sem dono (VISAO Fase 3.3).

## Cirurgia

1. `Viveiro` em novo `app/models/viveiro.py` (módulo próprio: domínio novo, não cabe em core/safra):
   - `propriedade` FK CASCADE related `viveiros` (dado operacional, não catálogo)
   - `nome` CharField(100), `tipo` choices [in_vitro, estaquia, enxertia, semente]
   - `protocolo` TextField(blank) — texto do produtor, nunca seed oficial
   - `fonte_dado` default `declarado`
2. `LoteMuda`:
   - `viveiro` FK CASCADE related `lotes`
   - `origem_matriz` CharField(150, blank) — texto; sem tabela de matriz semeada (seria meta)
   - `cultura` FK PROTECT null (sétimo PROTECT; estender `tests_cascata_cultura.py`)
   - `qtd_produzida` Integer(null), `qtd_expedida` Integer default 0 (soma pode ser 0; produzida null é ausência)
   - `data_repique`, `data_aclimatacao`, `data_expedicao` Date(null) — cada etapa nula até acontecer (não gerar data = proibição §0.3)
   - `talhao_destino` FK SET_NULL null/blank (muda plantada; talhão sobrevive)
   - `sobrevivencia_pct` Decimal(null) — null até contar
   - Index `[viveiro, -criado_em]`; `criado_em` auto_now_add
3. Export em `app/models/__init__.py` (padrão linhas 1-121).
4. Serializer + ViewSet escopo propriedade + `perform_create` checando `propriedade.user` (padrão `rastreabilidade.py:78-84`).
5. Teste: lote sem datas passa; expedição sem talhão passa; DELETE viveiro leva lotes; DELETE cultura com muda vinculada dá ProtectedError.

## O que NÃO entra

- Sem protocolo oficial por espécie, sem taxa de multiplicação padrão, sem tela.

## Critério de saída

- Cadeia matriz(texto) → lote → talhão rastreável via API; nenhuma data gerada pelo sistema.
