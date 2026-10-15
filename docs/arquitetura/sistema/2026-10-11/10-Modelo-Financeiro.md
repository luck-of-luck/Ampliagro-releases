# Modelo Financeiro (Lançamentos, Contas, Parcelamentos, Conciliação, NF-e) — Estado 2026-10-11

> Fonte: `app/models/financeiro.py` (384 linhas)

---

## 1. LancamentoFinanceiro (`app/models/financeiro.py:47-166`)

### Tipos e Categorias
| Tipo | Categorias |
|------|------------|
| `RECEITA` | `VENDA_PROD`, `VENDA_ANIMAL`, `VENDA_LEITE`, `OUTRO` |
| `DESPESA` | `INSUMO`, `FOLHA`, `MANUTENCAO`, `COMBUSTIVEL`, `FRETE`, `IMPOSTO`, `SERVICO`, `ENERGIA`, `OUTRO` |

### Regra de Ouro: `CATEGORIAS_SO_DESPESA`
```python
CATEGORIAS_SO_DESPESA = frozenset({
    "INSUMO", "FOLHA", "MANUTENCAO", "COMBUSTIVEL",
    "FRETE", "IMPOSTO", "SERVICO", "ENERGIA"
})
```

**Regra em `clean()`:** Se `tipo == "RECEITA"` e `categoria in CATEGORIAS_SO_DESPESA` → `ValidationError`

> **Caso real que motivou:** R$ 100,00 tipo RECEITA, categoria FOLHA, descrição "pagamento dos funcionarios". Painel somava na receita, ROI subia, produtor multiplicava hectare. Ninguém notou — valor pequeno passa vida inteira sem ser notado. `app/services/dre.py` JÁ classificava FOLHA como despesa operacional; painel confiava no campo `tipo`. Dois lugares discordavam. Agora dado incoerente não entra.

### Campos Principais
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `propriedade` | FK(Propriedade) | CASCADE |
| `tipo` | CharField(10) | `RECEITA` / `DESPESA` |
| `categoria` | CharField(20) | 25 opções |
| `valor` | DecimalField(12,2) | |
| `data` | DateField | Data do lançamento |
| `descricao` | TextField | |
| `participante` | CharField(120) | Cliente/fornecedor (LCDPR) |
| `participante_doc` | EncryptedCharField(255) | CPF/CNPJ criptografado (LCDPR) |
| `talhao` | FK(Talhao) | SET_NULL |
| `safra` | FK(Safra) | SET_NULL |
| `pago` | BooleanField | Default False |
| `data_pagamento` | DateField | Nullable |

### LCDPR Fields
| Campo | Registro | Descrição |
|-------|----------|-----------|
| `conta_bancaria` | 0050 | FK(ContaBancaria, PROTECT) |
| `tipo_documento_lcdpr` | Q100 | 1=NF, 2=Fatura, 3=Recibo, 4=Contrato, 5=Folha, 6=Outros |
| `numero_documento` | Q100 | Número do documento |
| `tipo_lancamento_lcdpr` | Q100 | 1=Receita atividade rural, 2=Despesa custeio/investimento, 3=Produtos entregues adiantamento |
| `saldo_lcdpr` | Q100 | Saldo acumulado após lançamento |

---

## 2. ContaBancaria (`app/models/financeiro.py:168-193`)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `propriedade` | FK(Propriedade) | CASCADE |
| `banco` | CharField(100) | Nome do banco |
| `agencia` | CharField(20) | |
| `conta` | CharField(30) | |
| `digito` | CharField(5) | Dígito verificador |
| `tipo` | CharField(20) | CORRENTE, POUPANCA, INVESTIMENTO |
| `saldo_atual` | DecimalField(14,2) | Default 0 |
| `ativa` | BooleanField | Default True |

**Constraint:** `unique_together = ("propriedade", "banco", "agencia", "conta", "digito")`

---

## 3. MovimentacaoBancaria (`app/models/financeiro.py:195-217`)

| Campo | Tipo |
|-------|------|
| `conta` | FK(ContaBancaria) |
| `data` | DateField |
| `descricao` | TextField |
| `valor` | DecimalField(14,2) |
| `tipo` | `CREDITO` / `DEBITO` |
| `hash_unico` | CharField(64, unique=True, default=uuid4) |

**Idempotência:** `hash_unico` gerado no cliente → servidor faz `update_or_create` por `hash_unico`. Mesmo push duas vezes = mesmo registo.

---

## 4. Parcelamento (`app/models/financeiro.py:219-262`)

| Campo | Tipo |
|-------|------|
| `tipo` | `PAGAR` / `RECEBER` |
| `status` | `ABERTA`, `PAGA`, `CANCELADA`, `VENCIDA` |
| `numero` | IntegerField (número da parcela) |
| `total_parcelas` | IntegerField |
| `valor_total/valor_parcela` | DecimalField(14,2) |
| `data_vencimento` | DateField |
| `juros_mes/multa_atraso` | DecimalField(5,2) / DecimalField(14,2) |

---

## 5. ConciliacaoBancaria (`app/models/financeiro.py:264-297`)

| Campo | Descrição |
|-------|-----------|
| `saldo_sistema_inicio/fim` | Saldo do sistema no período |
| `saldo_banco_inicio/fim` | Saldo do extrato bancário |
| `diferenca` | Diferença (deve ser 0) |
| `status` | `ABERTA`, `FECHADA`, `COM_DIFERENCA` |

**Constraint:** `unique_together = ("conta", "data_fim")`

---

## 6. NotaFiscalImportada (`app/models/financeiro.py:313-364`)

**Problema resolvido:** Import de NF-e duplicava itens no estoque.

**Identidade:** Chave de acesso NF-e (44 dígitos) — única por documento, não se repetem.

```python
chave = models.CharField(max_length=44)  # 44 dígitos sem barras
```

**Constraint:** `unique_together = ("propriedade", "chave")` — mesmo produtor não tem duas notas com mesma chave; propriedades diferentes podem ter mesmo número sem colidir.

**O que NÃO é:** Arquivo fiscal, substitui SEFAZ, registo de fornecedor. **É:** Marca de que este documento já foi lido — para o `ok: true` ser verdade.

---

## 7. NotificacaoTemplate (`app/models/financeiro.py:366-384`)

Templates para notificações push/email/whatsapp com variáveis (`['cultura', 'valor', 'data']`).

---

## 8. EncryptedCharField (`app/seguranca.py`)

Usado em `participante_doc` (CPF/CNPJ do participante no LCDPR) — criptografado em repouso.

---

## 9. Indexes & Constraints

| Modelo | Index/Constraint |
|--------|------------------|
| `LancamentoFinanceiro` | `["propriedade", "data"]`, `["propriedade", "tipo"]`, `["propriedade", "data", "tipo"]` |
| `ContaBancaria` | `unique_together (propriedade, banco, agencia, conta, digito)` |
| `MovimentacaoBancaria` | ordering `["-data", "-criado_em"]` |
| `Parcelamento` | ordering `["data_vencimento"]` |
| `ConciliacaoBancaria` | `unique_together ("conta", "data_fim")`, ordering `["-data_fim"]` |
| `NotaFiscalImportada` | `unique_together ("propriedade", "chave")`, index `["propriedade", "emissao"]` |
| `PushSubscription` | `unique_together ("user", "endpoint")` |

---

## 9. Guardas de Regressão

| Teste | O que impede |
|-------|--------------|
| `tests/test_lcdpr_campos_fiscais.py` | Campos fiscais obrigatórios no LCDPR |
| `tests/test_cascata_cultura.py` | PROTECT em Cultura impede cascade delete |
| `tests/test_cascata_financeiro.py` | Integridade financeira |
| `app/tests_cache_painel.py` | Cache por usuário isolado |

---

## 10. Casos de Uso Críticos

### Import NF-e → Estoque
1. `NotaFiscalImportada` verifica chave 44 dígitos
2. Se nova → cria `LancamentoFinanceiro` (DESPESA, INSUMO)
3. Atualiza `EstoqueItem` via signal `baixar_estoque_insumo`

### Conciliação Bancária
1. Usuário informa `saldo_banco_inicio/fim`
2. Sistema calcula `saldo_sistema_inicio/fim` via `MovimentacaoBancaria`
3. `diferenca` deve ser 0 → `FECHADA`, senão `COM_DIFERENCA`

### Parcelamento → Fluxo de Caixa
- `Parcelamento` gera `LancamentoFinanceiro` futuros via signal
- `data_vencimento` alimenta `agenda_financeira` no dashboard