# Modelo Estoque, Movimentação, Ordens de Compra & Inventário — Estado 2026-10-11

> Fonte: `app/models/estoque.py` (123 linhas)

---

## 1. EstoqueItem (`app/models/estoque.py:20-48`)

### Categorias
| Código | Descrição |
|--------|-----------|
| `INSUMO` | Insumo (semente, fertilizante, defensivo, etc.) |
| `PRODUTO` | Produto Beneficiado (grãos, leite, carne) |
| `RACAO` | Ração |
| `EMBALAGEM` | Embalagem |
| `PECA` | Peça de Reposição |
| `FERRAMENTA` | Ferramenta |
| `OUTRO` | Outro |

### Campos
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `propriedade` | FK(Propriedade) | CASCADE |
| `categoria` | CharField(20) | Choices CATEGORIAS_ESTOQUE |
| `nome` | CharField(150) | |
| `quantidade` | DecimalField(10,2) | Saldo atual |
| `quantidade_minima` | DecimalField(10,2) | Default 0 — alerta ruptura |
| `quantidade_maxima` | DecimalField(10,2) | Nullable — alerta excesso |
| `valor_unitario` | DecimalField(10,2) | Default 0 |
| `unidade` | CharField(20) | sc, kg, L, un, etc. |
| `local` | CharField(100) | Armazém, silo, oficina |
| `data_validade` | DateField | Alerta vencimento |
| `observacao` | TextField | |

**Indexes:** `["propriedade", "data_validade"]`, `["propriedade", "categoria"]`

---

## 2. MovimentacaoEstoque (`app/models/estoque.py:50-70`)

### Tipos de Movimentação
| Código | Descrição |
|--------|-----------|
| `ENTRADA` | Compra, produção, devolução |
| `SAIDA` | Venda, consumo, perda |
| `TRANSFERENCIA` | Entre locais/armazéns |
| `AJUSTE` | Inventário, quebra, vencimento |

### Campos
| Campo | Tipo |
|-------|------|
| `item` | FK(EstoqueItem) |
| `tipo` | CharField(20) — choices TIPO_MOVIMENTACAO |
| `quantidade` | DecimalField(10,2) |
| `lote` | CharField(50) — rastreabilidade |
| `nf` | CharField(50) — Nota Fiscal |
| `data` | DateField — default now |
| `responsavel` | CharField(100) |
| `observacao` | TextField |

---

## 3. OrdemCompra (`app/models/estoque.py:72-90`)

### Status
| Código | Descrição |
|--------|-----------|
| `RASCUNHO` | Rascunho (padrão) |
| `APROVADA` | Aprovada internamente |
| `PEDIDA` | Enviada ao fornecedor |
| `RECEBIDA` | Itens recebidos no estoque |
| `CANCELADA` | Cancelada |

### Campos
| Campo | Tipo |
|-------|------|
| `propriedade` | FK(Propriedade) |
| `fornecedor` | CharField(150) |
| `data_emissao` | DateField — default now |
| `data_prevista` | DateField — entrega esperada |
| `status` | CharField(20) — default `RASCUNHO` |
| `valor_total` | DecimalField(12,2) |
| `observacao` | TextField |

---

## 4. Inventario & InventarioItem (`app/models/estoque.py:92-123`)

### Inventario
| Campo | Tipo |
|-------|------|
| `propriedade` | FK(Propriedade) |
| `data` | DateField — default now |
| `responsavel` | CharField(100) |
| `status` | `ABERTO` / `CONCLUIDO` |
| `observacao` | TextField |

### InventarioItem
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `inventario` | FK(Inventario) | |
| `estoque_item` | FK(EstoqueItem) | |
| `quantidade_sistema` | DecimalField(10,2) | O que o sistema diz |
| `quantidade_contada` | DecimalField(10,2) | Nullable — o que contou |

### Property: `diferenca()`
```python
@property
def diferenca(self):
    if self.quantidade_contada is not None:
        return self.quantidade_contada - self.quantidade_sistema
    return 0
```
> Positivo = sobra física; Negativo = falta/furto/quebra

---

## 5. Fluxos Principais

### Compra → Recebimento → Estoque
1. `OrdemCompra` status `APROVADA` → `PEDIDA` (envia ao fornecedor)
2. Recebimento físico → status `RECEBIDA`
2. Cria `MovimentacaoEstoque` tipo `ENTRADA` + `LancamentoFinanceiro` (DESPESA/INSUMO)

### Consumo Interno
1. Aplicação insumo (`AplicacaoInsumo`) → signal `baixar_estoque_insumo`
2. Cria `MovimentacaoEstoque` tipo `SAIDA`
3. Atualiza `EstoqueItem.quantidade` (F expression atômica)

### Venda Produto
1. `LancamentoFinanceiro` tipo `RECEITA` categoria `VENDA_PROD`
2. `MovimentacaoEstoque` tipo `SAIDA` (produto beneficiado)

### Inventário Físico
1. Cria `Inventario` status `ABERTO`
2. Para cada item: preenche `quantidade_contada`
3. `diferenca()` → gera `MovimentacaoEstoque` tipo `AJUSTE`
4. Status `CONCLUIDO` → trava edição

---

## 6. Alertas de Ruptura/Vencimento

| Alerta | Condição | Intent |
|--------|----------|--------|
| Ruptura | `quantidade <= quantidade_minima` | `estoque_baixo` |
| Excesso | `quantidade >= quantidade_maxima` | (nenhum — só relatório) |
| Vencimento | `data_validade <= hoje + 30 dias` | `calendario_sanitario` / `monitorar_pragas` |

---

## 5. Integração LCDPR

| Evento | Registro LCDPR | Campo |
|--------|----------------|-------|
| Compra insumo | `0050` (Contas bancárias) + `Q100` | `conta_bancaria`, `tipo_lancamento_lcdpr=2` |
| Venda produto | `Q100` | `tipo_lancamento_lcdpr=1` |
| Movimentação bancária | `0050` | `banco`, `agencia`, `conta` |

---

## 6. Guardas de Regressão

| Teste | O que impede |
|-------|--------------|
| `tests/test_lcdpr_campos_fiscais.py` | Conta bancária obrigatória no LCDPR |
| `tests/test_cascata_cultura.py` | PROTECT em Cultura |
| `tests/test_escrita_tenancy.py` | Escrita isolada por propriedade |

---

## 7. API Views

| ViewSet | Arquivo | Endpoint |
|---------|---------|----------|
| `EstoqueItemViewSet` | `app/api/views/estoque.py` | `/api/estoque/` |
| `MovimentacaoEstoqueViewSet` | `app/api/views/faltantes.py` | `/api/movimentacao-estoque/` |
| `OrdemCompraViewSet` | `app/api/views/faltantes.py` | `/api/ordens-compra/` |
| `InventarioViewSet` | `app/api/views/faltantes.py` | `/api/inventarios/` |

---

## 8. Intents IA Relacionadas

| Intent | Descrição |
|--------|-----------|
| `consultar_estoque` | Consulta saldo, alerta ruptura/vencimento |
| `listar_insumos` | Lista insumos com filtros |
| `criar_ordem_compra` | Gera pedido de compra (rascunho → confirma) |
| `estoque_baixo` | Itens abaixo do mínimo |

---

## 9. Checklist de Operação

- [ ] `quantidade_minima` preenchida para itens críticos
- [ ] `data_validade` preenchida → alerta 30 dias antes
- [ ] `MovimentacaoEstoque` criada para TODA entrada/saída
- [ ] `OrdemCompra` status `RECEBIDA` gera entrada no estoque
- [ ] Inventário periódico (mensal/trimestral) com `Inventario` + `InventarioItem`
- [ ] `quantidade_maxima` para itens perecíveis/estocagem cara