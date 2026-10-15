# Modelo Aquícola (Lote, Despesca) — Estado 2026-10-11

> Fonte: `app/models/aquatico.py` (77 linhas)

---

## 1. LoteAquatico (`app/models/aquatico.py:26-58`)

### Espécies
| Código | Descrição |
|-------|-----------|
| `TILAPIA` | Tilápia |
| `TAMBAQUI` | Tambaqui |
| `CARPA` | Carpa |
| `PINTADO` | Pintado |
| `PIRARUCU` | Pirarucu |
| `TRUTA` | Truta |
| `CAMARAO` | Camarão |
| `OUTRO_PEIXE` | Outro peixe |
| `OUTRO_CRUSTACEO` | Outro crustáceo |

### Sistemas de Produção
| Código | Descrição |
|-------|-----------|
| `VIVEIRO_ESCAVADO` | Viveiro escavado |
| `TANQUE_REDE` | Tanque-rede |
| `TANQUE_ELEVADO` | Tanque elevado / caixa d'água |
| `AQUAPONIA` | Aquaponia |
| `BIOFLOCOS` | Bioflocos (BFT) |
| `OUTRO` | Outro |

### Campos
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `propriedade` | FK(Propriedade) | CASCADE |
| `especie` | CharField(15) | Choices ESPECIES_AQUATICO |
| `sistema` | CharField(20) | Choices SISTEMAS_AQUATICO, default `VIVEIRO_ESCAVADO` |
| `ambiente` | CharField(100) | Viveiro/tanque onde está o lote |
| `quantidade` | IntegerField | Indivíduos |
| `biomassa_media` | DecimalField(8,2) | Peso médio por indivíduo (g) |
| `data_povoamento` | DateField | |
| `observacao` | TextField | |

**Indexes:** `["propriedade", "especie"]`

---

## 2. Despesca (`app/models/aquatico.py:60-77`)

Registro de colheita/despesca por lote.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `lote` | FK(LoteAquatico) | CASCADE |
| `data` | DateField | Default now |
| `quantidade_kg` | DecimalField(8,2) | kg colhidos |
| `valor_estimado` | DecimalField(8,2) | Valor estimado da colheita |
| `observacao` | TextField | |

**Ordering:** `["-data"]`

---

## 3. Relacionamentos

```
Propriedade (1) ──────< (N) LoteAquatico
LoteAquatico (1) ────< (N) Despesca
```

---

## 4. Fluxo de Produção Aquícola

### Povoamento
1. Cria `LoteAquatico` com `quantidade` indivíduos e `data_povoamento`
2. `biomassa_media` estimada inicial (g/indivíduo)

### Crescimento
- `biomassa_media` atualizada periodicamente via pesagem amostral
- Alimentação registrada via `Racao` (tipo `VOLUMOSO`/`CONCENTRADO`)

### Despesca (Colheita)
1. Cria `Despesca` com `quantidade_kg` e `valor_estimado`
2. Atualiza `LoteAquatico.quantidade` (baixa) — **via signal ou manual**
3. Gera `LancamentoFinanceiro` tipo `RECEITA` categoria `VENDA_PROD`

---

## 5. Integração com Financeiro (LCDPR)

### LancamentoFinanceiro gerado
| Campo LCDPR | Valor |
|-------------|-------|
| `tipo` | `RECEITA` |
| `categoria` | `VENDA_PROD` |
| `tipo_lancamento_lcdpr` | `1` (Receita atividade rural) |
| `participante` | Comprador/frigorífico |
| `tipo_documento_lcdpr` | `1` (Nota Fiscal) |

---

## 6. Guardas de Regressão

| Teste | O que impede |
|-------|--------------|
| `tests/test_lote_semente_g02.py` | Semente rastreável (paralelo) |
| `tests/test_viveiro_g04.py` | Viveiro (paralelo) |

---

## 7. Extensões Futuras (G-04, G-06)

| Feature | Status | Referência |
|---------|--------|------------|
| `Viveiro` (G-04) | Modelo separado `app/models/viveiro.py` | `docs/sistema/PLANO-EXECUCAO.md` §2.1 |
| `MixPastagem` aquático | Não implementado | `PLANO-EXECUCAO.md` G-06 |
| `Racao` aquícola | Usa `Racao` genérico com `especie_alvo=PEIXE` | `app/models/pecuaria.py` |

---

## 8. API Views Relacionadas

| View | Arquivo | Endpoint |
|------|---------|----------|
| `LoteAquaticoViewSet` | `app/api/views/aquatico.py` | `/api/lotes-aquaticos/` |
| `DespescaViewSet` | `app/api/views/aquatico.py` | `/api/despescas/` |

---

## 9. Intenções IA Relacionadas

| Intent | Descrição |
|--------|-----------|
| `resumo_aquatico` | Resumo da piscicultura (lotes, biomassa, despesca) |
| `cadastrar_lote_aquatico` | Cadastra novo lote |
| `registrar_despesca` | Registra colheita |

---

## 10. Checklist de Operação

- [ ] `LoteAquatico.biomassa_media` atualizada periodicamente
- [ ] `Despesca` gera `LancamentoFinanceiro` automaticamente
- [ ] `quantidade` do lote baixada na despesca
- [ ] `Racao` com `especie_alvo=PEIXE` para alimentação
- [ ] `calendario_sanitario` inclui protocolos aquícolas