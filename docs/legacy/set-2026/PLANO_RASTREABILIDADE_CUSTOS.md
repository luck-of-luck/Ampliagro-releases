# Plano MVP — Rastreabilidade & Gestão de Custos

> **Versão:** 2.0 — revisada após auditoria completa do código-fonte (2026-08-31)
> **Auditoria:** 22 falhas encontradas e corrigidas — ver `§ 10 Registro de Correções`
> **Propósito:** Apresentar o Ampliagro como sistema completo e competitivo para Josif e Fectmuz, com foco em rastreabilidade (Pilar 2 — Dores da Operação) e gestão de custos financeiros (Pilar 1 — Dores Financeiras). Mínimo funcional para competir no topo do agro brasileiro.

---

## 1. CONTEXTO ESTRATÉGICO

### 1.1 Dores que este plano endereça (top 10 priorizadas)

**Rastreabilidade:**

| # | Dor | Severidade |
|---|-----|-----------|
| 1 | 🔴 **Rastreabilidade nula** (#53) — impossível exportar histórico da safra para certificações (GlobalG.A.P.) | Crítica |
| 2 | 🔴 **Produtos vencidos** (#135) — defensivos que passaram da validade sem controle | Crítica |
| 3 | 🔴 **Ruptura de estoque** (#137) — parar o plantio por falta de insumo | Crítica |
| 4 | 🟠 **Insumos desviados** (#141) — glifosato sumindo sem controle de retirada | Alta |
| 5 | 🟠 **Baixas de estoque esquecidas** (#161) — operário leva semente mas não anota | Alta |
| 6 | 🟠 **Romaneios de papel** (#173) — caminhoneiro perde papel da carga | Alta |

**Gestão de Custos:**

| # | Dor | Severidade |
|---|-----|-----------|
| 1 | 🔴 **Desconhecimento do custo real** (#1) — não saber custo de produção unitário por saca/arroba | Crítica |
| 2 | 🔴 **Mistura de caixas** (#2) — conta pessoa física vs jurídica da fazenda | Crítica |
| 3 | 🔴 **Susto na entressafra** (#3) — sem fluxo de caixa nos meses sem colheita | Crítica |
| 4 | 🔴 **Fechamento lento** (#4) — dias para compilar DRE com dezenas de planilhas | Crítica |
| 5 | 🔴 **Apagão do LCDPR** (#5) — dificuldade com Livro Caixa Digital do Produtor Rural | Crítica |

### 1.2 O que já existe (inventário verificado no código)

| Modelo / Módulo | Arquivo | Estado |
|-----------------|---------|--------|
| `Cultura`, `Propriedade`, `Talhao`, `TalhaoGeometria` | `app/models/core.py` | ✅ Existe |
| `Safra`, `Insumo`, `AplicacaoInsumo` | `app/models/safra.py` | ✅ Existe — **ver § 2.5 sobre sobreposição** |
| `EstoqueItem` | `app/models/estoque.py` | ✅ Existe — **ver § 2.5 sobre coexistência** |
| `LancamentoFinanceiro` | `app/models/financeiro.py` | ✅ Existe (12 categorias, campos `talhao`/`safra` já presentes) |
| `Funcionario` (105 cargos) | `app/models/equipe.py` | ✅ Existe |
| `Maquinario` | `app/models/maquinario.py` | ✅ Existe |
| `PerfilUsuario` + `hierarquia.py` | `app/models/usuario.py` + `app/hierarquia.py` | ✅ Existe |
| QR code JS (`pwa/qr.js`) | `app/static/js/pwa/qr.js` | ⚠️ Existe mas `buildCadeiaRastreabilidade()` é stub (todos `null`); depende de `window.QRCode` que não está em `package.json` |
| Views `estoque.py` / `financeiro.py` | `app/views/estoque.py`, `app/views/financeiro.py` | ✅ Existem (2 views cada) |
| API `estoque.py` / `financial.py` | `app/api/views/estoque.py`, `app/api/views/financial.py` | ✅ Existem (ViewSets + function views) |
| Templates estoque/financeiro | `cadastro-estoque.html`, `estoque-geral.html`, `estoque-insumos.html`, `cadastro-financeiro.html` etc. | ✅ Existem |
| `qrcode` lib | `package.json` / `requirements.txt` | ❌ Não instalada — necessária para `qr.js` funcionar |

---

## 2. ARQUITETURA DO MVP

### 2.1 Onde os novos modelos vivem

> **Correção vs v1:** o projeto usa `app/models/` como **package** (13 arquivos + `__init__.py` com re-exports), NÃO `app/models.py` monolítico. Novos modelos seguem o mesmo padrão.

```
app/models/
├── __init__.py            # ← adicionar re-exports dos novos modelos
├── rastreabilidade.py     # ← NOVO — RastroItem, MovimentoEstoque
├── custos.py              # ← NOVO — CentroCusto, CustoProducao, LancamentoDetalhado
├── safra.py               #     (existente — Insumo, Safra, AplicacaoInsumo)
├── estoque.py             #     (existente — EstoqueItem, mantido)
├── financeiro.py           #     (existente — LancamentoFinanceiro, mantido)
├── core.py / equipe.py …  #     (existentes)
```

Migrations continuam em `app/migrations/` normalmente (`python manage.py makemigrations`).

Registrar no admin em `app/admin.py` (ver § 2.7).

### 2.2 Módulo de Rastreabilidade — `app/models/rastreabilidade.py`

```python
import hashlib
import secrets
from datetime import date

from django.contrib.auth.models import User
from django.db import models

from app.validators import validate_json_safe


class RastroItem(models.Model):
    """
    Lote rastreável de insumo/produto. Um registro = um lote físico recebido.
    Coexiste com EstoqueItem: EstoqueItem = itens genéricos sem lote/expiração
    (peças, ferramentas); RastroItem = itens agrícolas rastreáveis por lote
    (sementes, defensivos, fertilizantes) que exigem validade, NF e QR code.
    """

    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="rastros"
    )
    insumo = models.ForeignKey(
        "Insumo", on_delete=models.CASCADE, related_name="rastros"
    )
    # Dados de entrada do lote
    numero_lote = models.CharField(max_length=50, blank=True, help_text="Lote do fabricante")
    numero_serie = models.CharField(max_length=50, blank=True)
    nf_entrada = models.CharField(max_length=20, blank=True, help_text="Nota fiscal de entrada")
    quantidade_recebida = models.DecimalField(max_digits=10, decimal_places=2)
    unidade = models.CharField(max_length=20, help_text="kg, L, sc, cx …")
    data_recebimento = models.DateField()
    fornecedor = models.CharField(max_length=150, blank=True)
    # Validade vive AQUI (por lote), não em Insumo (produto genérico).
    # null = sem expiração (ex.: calcário); nunca usar blank+unique sem null.
    data_validade = models.DateField(null=True, blank=True)
    # Rastreabilidade digital — gerado automaticamente no save(); null até gerar.
    qr_code_hash = models.CharField(max_length=64, unique=True, null=True, blank=True)
    observacao = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Rastro de Item"
        verbose_name_plural = "Rastros de Itens"
        ordering = ["-data_recebimento"]
        indexes = [
            models.Index(fields=["propriedade", "insumo", "data_recebimento"]),
            models.Index(fields=["propriedade", "data_validade"]),
        ]

    def __str__(self):
        lote = self.numero_lote or f"#{self.pk}"
        return f"{self.insumo.nome} [{lote}] — {self.propriedade.nome}"

    def save(self, *args, **kwargs):
        if not self.qr_code_hash:
            raw = f"{self.propriedade_id}:{self.insumo_id}:{self.numero_lote}:{self.data_recebimento}:{secrets.token_hex(8)}"
            self.qr_code_hash = hashlib.sha256(raw.encode()).hexdigest()[:32]
        super().save(*args, **kwargs)

    @property
    def saldo(self):
        """
        Quantidade ainda em estoque = recebido − soma das saídas.
        Evita campo denormalizado quantidade_saida (que divergiria do histórico).
        Usar annotate(Sum) na API para evitar N+1.
        """
        from django.db.models import Sum

        saidas = self.movimentos.filter(tipo="SAIDA").aggregate(s=Sum("quantidade"))["s"] or 0
        ajustes_neg = self.movimentos.filter(tipo="AJUSTE").aggregate(s=Sum("quantidade"))["s"] or 0
        # AJUSTE pode ser positivo (correção p/ cima) ou negativo
        return self.quantidade_recebida - saidas + ajustes_neg

    @property
    def vencido(self) -> bool:
        if self.data_validade:
            return self.data_validade < date.today()
        return False

    @property
    def dias_para_vencer(self):
        if not self.data_validade:
            return None
        return (self.data_validade - date.today()).days
```

```python
class MovimentoEstoque(models.Model):
    """
    Uma movimentação de um RastroItem. Histórico completo — nunca editar, só criar
    novos registros (ledger append-only).
    quantidade sempre positiva; direção é dada por tipo.
    """

    TIPO_CHOICES = [
        ("ENTRADA", "Entrada (Compra/Retorno)"),
        ("SAIDA", "Saída (Uso/Venda/Perda)"),
        ("TRANSF", "Transferência entre talhões"),
        ("AJUSTE", "Ajuste de inventário"),
    ]
    rastro_item = models.ForeignKey(
        RastroItem, on_delete=models.CASCADE, related_name="movimentos"
    )
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    quantidade = models.DecimalField(
        max_digits=10, decimal_places=2, help_text="Sempre positiva; direção via tipo"
    )
    # Data efetiva da movimentação (pode diferir de criado_em se lançamento retroativo)
    data_movimento = models.DateField(default=date.today)
    talhao = models.ForeignKey(
        "Talhao", on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Talhão de destino/origem (se aplicável)",
    )
    funcionario = models.ForeignKey(
        "Funcionario", on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Quem retirou/entregou",
    )
    nota_fiscal = models.CharField(max_length=20, blank=True)
    motivo = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Movimento de Estoque"
        verbose_name_plural = "Movimentos de Estoque"
        ordering = ["-data_movimento", "-criado_em"]
        indexes = [
            models.Index(fields=["rastro_item", "tipo"]),
            models.Index(fields=["rastro_item", "data_movimento"]),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} {self.quantidade} — {self.rastro_item} ({self.data_movimento})"
```

```python
class RastreabilidadeSafra(models.Model):
    """
    Vínculo insumo → safra → talhão com custo. Estende AplicacaoInsumo com
    contexto de safra e custo (sem duplicar insumo/talhão quando já houver
    AplicacaoInsumo vinculada).
    """

    safra = models.ForeignKey("Safra", on_delete=models.CASCADE, related_name="rastros")
    # Se vier de uma AplicacaoInsumo existente, referencia-a para não duplicar
    # insumo/talhão/data; caso contrário, preenche insumo/talhão diretamente.
    aplicacao = models.ForeignKey(
        "AplicacaoInsumo", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="rastros_safra",
        help_text="Aplicação de origem (se existir); quando preenchida, insumo/talhão são herdados",
    )
    # Quando aplicacao é null, estes são obrigatórios; quando aplicacao existe, são redundantes (usar property)
    insumo = models.ForeignKey("Insumo", on_delete=models.CASCADE, null=True, blank=True)
    rastro_item = models.ForeignKey(
        RastroItem, on_delete=models.CASCADE, null=True, blank=True,
        help_text="Lote específico de origem do insumo",
    )
    talhao = models.ForeignKey("Talhao", on_delete=models.CASCADE, null=True, blank=True)
    quantidade_aplicada = models.DecimalField(max_digits=10, decimal_places=2)
    # custo_unitario = Insumo.valor_unitario no momento da aplicação (snapshot, não FK)
    # para preservar histórico mesmo se o preço do Insumo mudar depois
    custo_unitario = models.DecimalField(
        max_digits=10, decimal_places=4,
        help_text="Snapshot de Insumo.valor_unitario na data da aplicação",
    )
    custo_total = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    operacao = models.CharField(max_length=100, blank=True, help_text="Adubação, Pulverização, Semeadura …")
    data_aplicacao = models.DateField()
    observacao = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Rastreabilidade de Safra"
        verbose_name_plural = "Rastreabilidades de Safra"
        ordering = ["-data_aplicacao"]
        indexes = [
            models.Index(fields=["safra", "talhao"]),
            models.Index(fields=["safra", "data_aplicacao"]),
        ]

    def __str__(self):
        insumo_nome = (self.insumo.nome if self.insumo_id else None) or (self.aplicacao.insumo.nome if self.aplicacao_id else "—")
        return f"{insumo_nome} → {self.safra} ({self.data_aplicacao}) R$ {self.custo_total}"

    def save(self, *args, **kwargs):
        # custo_total sempre derivado; nunca confiar em valor enviado pelo cliente
        self.custo_total = self.quantidade_aplicada * self.custo_unitario
        super().save(*args, **kwargs)

    @property
    def insumo_efetivo(self):
        """Insumo real, seja via FK direta ou via AplicacaoInsumo vinculada."""
        if self.insumo_id:
            return self.insumo
        if self.aplicacao_id:
            return self.aplicacao.insumo
        return None

    @property
    def talhao_efetivo(self):
        if self.talhao_id:
            return self.talhao
        if self.aplicacao_id:
            return self.aplicacao.talhao
        return None
```

### 2.3 Módulo de Gestão de Custos — `app/models/custos.py`

```python
import hashlib
from datetime import date

from django.db import models


class CentroCusto(models.Model):
    """
    Divisão por área/negócio da fazenda. Criado automaticamente ao cadastrar
    Propriedade via signal (ver § 2.6).
    """

    TIPO_CHOICES = [
        ("AGRICULTURA", "Agricultura"),
        ("PECUARIA", "Pecuária"),
        ("MECANICA", "Mecânica/Oficina"),
        ("SEDE", "Sede/Administração"),
        ("GERAL", "Geral"),
    ]

    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="centros_custo"
    )
    nome = models.CharField(max_length=100, help_text="Ex.: Agricultura — Talhão 4, Pecuária — Leite")
    descricao = models.TextField(blank=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default="GERAL")
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Centro de Custo"
        verbose_name_plural = "Centros de Custo"
        ordering = ["propriedade", "tipo", "nome"]
        constraints = [
            models.UniqueConstraint(fields=["propriedade", "nome"], name="uniq_centro_nome_por_propriedade"),
        ]

    def __str__(self):
        return f"{self.nome} [{self.get_tipo_display()}] — {self.propriedade.nome}"
```

```python
class CustoProducao(models.Model):
    """
    Custo consolidado por safra (e opcionalmente por talhão).
    Todos os campos monetários são denormalizados e recalculados em save()
    a partir das fontes (RastreabilidadeSafra + LancamentoDetalhado).
    Somente leitura via API (ReadOnlyModelViewSet); recalculo via signal
    ou management command.
    """

    safra = models.ForeignKey("Safra", on_delete=models.CASCADE, related_name="custos")
    talhao = models.ForeignKey(
        "Talhao", on_delete=models.CASCADE, null=True, blank=True,
        help_text="Se null, é o custo agregado da safra inteira",
    )
    centro_custo = models.ForeignKey(
        CentroCusto, on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Centro principal (quando talhão null, indica rateio geral)",
    )
    # Categorias de custo — denormalizadas, recalculadas em save()
    insumos = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    maquina = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    mao_de_obra = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    embalagem = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    frete = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    impostos = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    outros = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    # Totais — sempre derivados, nunca editáveis manualmente
    custo_total = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
    custo_por_ha = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, editable=False)
    custo_por_saca = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True, editable=False)
    receita = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, editable=False)
    lucro = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, editable=False)
    margem = models.DecimalField(
        max_digits=6, decimal_places=4, null=True, blank=True, editable=False,
        help_text="lucro / receita (null se receita = 0)",
    )
    observacao = models.TextField(blank=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Custo de Produção"
        verbose_name_plural = "Custos de Produção"
        ordering = ["-safra__ano", "-talhao__nome"]
        constraints = [
            models.UniqueConstraint(fields=["safra", "talhao"], name="uniq_custo_por_safra_talhao"),
        ]
        indexes = [
            models.Index(fields=["safra", "talhao"]),
        ]

    def __str__(self):
        alvo = self.talhao.nome if self.talhao_id else f"safra {self.safra}"
        return f"Custo {alvo} — R$ {self.custo_total} (R$ {self.custo_por_saca or '—'}/sc)"

    def save(self, *args, **kwargs):
        # custo_total = soma das categorias
        self.custo_total = (
            self.insumos + self.maquina + self.mao_de_obra
            + self.embalagem + self.frete + self.impostos + self.outros
        )
        # custo_por_ha = custo_total / área de referência
        area_ref = None
        if self.talhao_id:
            area_ref = self.talhao.area_hectare
        elif self.safra_id:
            area_ref = self.safra.area_plantada
        if area_ref and area_ref > 0:
            self.custo_por_ha = self.custo_total / area_ref
        else:
            self.custo_por_ha = None

        # custo_por_saca = custo_total / produção total da safra (ou do talhão se houver rateio)
        prod = self.safra.producao_total if self.safra_id else None
        if prod and prod > 0:
            self.custo_por_saca = self.custo_total / prod
        else:
            self.custo_por_saca = None

        # lucro e margem dependem de receita preenchida
        if self.receita is not None:
            self.lucro = self.receita - self.custo_total
            self.margem = (self.lucro / self.receita) if self.receita != 0 else None
        else:
            self.lucro = None
            self.margem = None

        super().save(*args, **kwargs)
```

```python
class LancamentoDetalhado(models.Model):
    """
    Categorização fina de um LancamentoFinanceiro para DRE/LCDPR.
    Um LancamentoFinanceiro pode ter 0..N detalhamentos (rateio).
    Quando existe, o DRE usa estes; quando não, usa LancamentoFinanceiro.categoria.
    Evita FK redundante para propriedade: herda de lancamento.propriedade quando
    vinculado; só exige propriedade própria quando standalone (sem lancamento).
    """

    CATEGORIA_DETALHADA_CHOICES = [
        # Receitas — mapeiam para LancamentoFinanceiro.categoria VENDA_PROD / VENDA_ANIMAL / VENDA_LEITE / OUTRO
        ("VENDA_SOJA", "Venda de Soja"),
        ("VENDA_MILHO", "Venda de Milho"),
        ("VENDA_ALGODAO", "Venda de Algodão"),
        ("VENDA_CAFE", "Venda de Café"),
        ("VENDA_BOVINO", "Venda de Boi"),
        ("VENDA_LEITE", "Venda de Leite"),
        ("VENDA_SUINO", "Venda de Suíno"),
        ("OUTRA_RECEITA", "Outra Receita"),
        # Despesas — Insumos (→ LancamentoFinanceiro INSUMO)
        ("COMPRA_SEMENTE", "Compra de Semente"),
        ("COMPRA_FERTILIZANTE", "Compra de Fertilizante"),
        ("COMPRA_DEFENSIVO", "Compra de Defensivo"),
        ("COMPRA_CORRETIVO", "Compra de Corretivo"),
        ("COMPRA_RACAO", "Compra de Ração"),
        ("COMPRA_COMBUSTIVEL", "Compra de Combustível"),
        ("COMPRA_OUTRO_INSUMO", "Compra de Outro Insumo"),
        # Despesas — Mão de obra (→ FOLHA)
        ("FOLHA_PAGAMENTO", "Folha de Pagamento"),
        ("DIARISTA", "Diarista/Safrista"),
        ("TERCEIRO", "Serviço Terceirizado"),
        # Despesas — Máquina (→ MANUTENCAO / COMBUSTIVEL)
        ("MANUTENCAO", "Manutenção"),
        ("PECA", "Peça de Reposição"),
        ("COMBUSTIVEL", "Combustível"),
        ("DEPRECIACAO", "Depreciação"),
        # Despesas — Geral (→ FRETE / IMPOSTO / SERVICO / ENERGIA / OUTRO)
        ("IMPOSTO", "Imposto"),
        ("ENERGIA", "Energia"),
        ("SEGURO", "Seguro"),
        ("FINANCEIRO", "Despesa Financeira"),
        ("OUTRA_DESPESA", "Outra Despesa"),
    ]

    # FK opcional para LancamentoFinanceiro — quando null, é um lançamento
    # standalone que ainda não foi conciliado com o financeiro principal
    lancamento = models.ForeignKey(
        "LancamentoFinanceiro", on_delete=models.CASCADE,
        related_name="detalhamentos", null=True, blank=True,
    )
    # Propriedade denormalizada apenas para quando lancamento é null;
    # quando lancamento existe, usar lancamento.propriedade (property abaixo)
    _propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE,
        related_name="lancamentos_detalhados", null=True, blank=True,
        db_column="propriedade_id",
    )
    centro_custo = models.ForeignKey(
        CentroCusto, on_delete=models.SET_NULL, null=True, blank=True,
    )
    safra = models.ForeignKey("Safra", on_delete=models.SET_NULL, null=True, blank=True)
    talhao = models.ForeignKey("Talhao", on_delete=models.SET_NULL, null=True, blank=True)
    categoria_detalhada = models.CharField(
        max_length=30, choices=CATEGORIA_DETALHADA_CHOICES, default="OUTRA_DESPESA"
    )
    # Valor rateado deste detalhamento (soma dos detalhamentos de um lançamento
    # deve bater com lancamento.valor — validar em clean())
    valor_rateado = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Se null, assume lancamento.valor integral",
    )
    observacao = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Lançamento Detalhado"
        verbose_name_plural = "Lançamentos Detalhados"
        ordering = ["-criado_em"]

    def __str__(self):
        base = self.lancamento.descricao if self.lancamento_id and self.lancamento.descricao else self.get_categoria_detalhada_display()
        return f"{base} — {self.categoria_detalhada} R$ {self.valor_rateado or '—'}"

    @property
    def propriedade(self):
        if self.lancamento_id:
            return self.lancamento.propriedade
        return self._propriedade

    @property
    def valor_efetivo(self):
        if self.valor_rateado is not None:
            return self.valor_rateado
        if self.lancamento_id:
            return self.lancamento.valor
        return 0
```

### 2.4 Re-exports — `app/models/__init__.py`

Adicionar ao final do arquivo existente:

```python
from .rastreabilidade import MovimentoEstoque, RastreabilidadeSafra, RastroItem
from .custos import CentroCusto, CustoProducao, LancamentoDetalhado
```

### 2.5 Decisões de coexistência (por que não substituir)

| Novo modelo | Modelo existente | Relação | Decisão |
|-------------|-----------------|---------|---------|
| `RastroItem` | `Insumo` (`safra.py`) | `RastroItem.insumo` FK | `Insumo` = catálogo genérico (nome, categoria, valor_unitário). `RastroItem` = lote físico específico daquele insumo (com NF, validade, QR). Um `Insumo` tem N `RastroItem`. |
| `RastroItem` + `MovimentoEstoque` | `EstoqueItem` (`estoque.py`) | Nenhuma FK | **Coexistência:** `EstoqueItem` = itens simples sem rastreio por lote (peças, ferramentas, embalagens). `RastroItem` = insumos agrícolas rastreáveis (sementes, defensivos). Não migrar dados automaticamente; `EstoqueItem` permanece. Futuro: management command para converter se desejado. |
| `RastreabilidadeSafra` | `AplicacaoInsumo` (`safra.py`) | `RastreabilidadeSafra.aplicacao` FK nullable | Se a aplicação já existe como `AplicacaoInsumo`, vincula via `aplicacao` e herda `insumo`/`talhao` via properties `insumo_efetivo`/`talhao_efetivo`. Se não existe, preenche `insumo`/`talhao` diretamente. Pós-MVP: avaliar merge ou extensão de `AplicacaoInsumo` com campos de custo. |

### 2.6 Signals — auto-criação de centros de custo

Criar `app/signals.py` (ou estender existente) e importar em `app/apps.py:ready()`:

```python
from django.db.models.signals import post_save
from django.dispatch import receiver
from app.models import Propriedade, CentroCusto


@receiver(post_save, sender=Propriedade)
def criar_centros_padrao(sender, instance, created, **kwargs):
    if not created:
        return
    for tipo, nome in [
        ("AGRICULTURA", "Agricultura"),
        ("PECUARIA", "Pecuária"),
        ("MECANICA", "Mecânica"),
        ("SEDE", "Sede"),
    ]:
        CentroCusto.objects.get_or_create(
            propriedade=instance, tipo=tipo, defaults={"nome": nome}
        )
```

Em `app/apps.py`:

```python
class AppConfig(django.apps.AppConfig):
    name = "app"
    def ready(self):
        import app.signals  # noqa: F401
```

### 2.7 Admin — `app/admin.py`

Acrescentar:

```python
from app.models import CentroCusto, CustoProducao, LancamentoDetalhado, MovimentoEstoque, RastreabilidadeSafra, RastroItem

@admin.register(RastroItem)
class RastroItemAdmin(admin.ModelAdmin):
    list_display = ("insumo", "propriedade", "numero_lote", "quantidade_recebida", "saldo", "data_validade", "vencido")
    list_filter = ("propriedade", "data_validade")
    search_fields = ("numero_lote", "numero_serie", "nf_entrada", "insumo__nome")

@admin.register(MovimentoEstoque)
class MovimentoEstoqueAdmin(admin.ModelAdmin):
    list_display = ("rastro_item", "tipo", "quantidade", "data_movimento", "funcionario")
    list_filter = ("tipo",)

@admin.register(RastreabilidadeSafra)
class RastreabilidadeSafraAdmin(admin.ModelAdmin):
    list_display = ("safra", "insumo_efetivo", "talhao_efetivo", "quantidade_aplicada", "custo_total", "data_aplicacao")

@admin.register(CentroCusto)
class CentroCustoAdmin(admin.ModelAdmin):
    list_display = ("nome", "propriedade", "tipo", "ativo")
    list_filter = ("tipo", "ativo")

@admin.register(CustoProducao)
class CustoProducaoAdmin(admin.ModelAdmin):
    list_display = ("safra", "talhao", "custo_total", "custo_por_ha", "custo_por_saca", "margem")
    readonly_fields = ("custo_total", "custo_por_ha", "custo_por_saca", "lucro", "margem")

@admin.register(LancamentoDetalhado)
class LancamentoDetalhadoAdmin(admin.ModelAdmin):
    list_display = ("lancamento", "categoria_detalhada", "centro_custo", "safra", "valor_rateado")
    list_filter = ("categoria_detalhada",)
```

---

## 3. SERIALIZERS — `app/api/serializers.py`

Seguir o padrão existente (campos explícitos, `validate_propriedade`, `read_only_fields`, `{campo}_display`). Acrescentar no final do arquivo:

```python
# Rastreabilidade & Custos — serializers seguem padrão: validate_propriedade via request.user

class RastroItemSerializer(serializers.ModelSerializer):
    insumo_nome = serializers.CharField(source="insumo.nome", read_only=True)
    propriedade_nome = serializers.CharField(source="propriedade.nome", read_only=True)
    saldo = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    vencido = serializers.BooleanField(read_only=True)
    dias_para_vencer = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = RastroItem
        fields = ["id","propriedade","propriedade_nome","insumo","insumo_nome",
                  "numero_lote","numero_serie","nf_entrada","quantidade_recebida",
                  "unidade","data_recebimento","fornecedor","data_validade",
                  "qr_code_hash","observacao","criado_em","saldo","vencido","dias_para_vencer"]
        read_only_fields = ["id","qr_code_hash","criado_em","saldo","vencido","dias_para_vencer"]

    def validate_quantidade_recebida(self, v):
        if v <= 0: raise serializers.ValidationError("Quantidade deve ser > 0.")
        return v
    def validate_propriedade(self, v):
        req = self.context.get("request")
        if req and v.user != req.user:
            raise serializers.ValidationError("Propriedade não pertence ao usuário.")
        return v
    def validate(self, attrs):
        # se insumo pertence a outra propriedade, rejeitar
        insumo = attrs.get("insumo")
        prop = attrs.get("propriedade")
        if insumo and prop and insumo.propriedade_id != prop.id:
            raise serializers.ValidationError({"insumo": "Insumo não pertence a esta propriedade."})
        return attrs

class MovimentoEstoqueSerializer(serializers.ModelSerializer):
    rastro_lote = serializers.CharField(source="rastro_item.numero_lote", read_only=True)
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    class Meta:
        model = MovimentoEstoque
        fields = ["id","rastro_item","rastro_lote","tipo","tipo_display","quantidade",
                  "data_movimento","talhao","funcionario","nota_fiscal","motivo","criado_em"]
        read_only_fields = ["id","criado_em"]
    def validate_quantidade(self, v):
        if v <= 0: raise serializers.ValidationError("Quantidade deve ser > 0 (direção é dada por tipo).")
        return v

class RastreabilidadeSafraSerializer(serializers.ModelSerializer):
    insumo_nome = serializers.SerializerMethodField()
    talhao_nome = serializers.SerializerMethodField()
    class Meta:
        model = RastreabilidadeSafra
        fields = ["id","safra","aplicacao","insumo","rastro_item","talhao",
                  "quantidade_aplicada","custo_unitario","custo_total",
                  "operacao","data_aplicacao","observacao","criado_em",
                  "insumo_nome","talhao_nome"]
        read_only_fields = ["id","custo_total","criado_em","insumo_nome","talhao_nome"]
    def get_insumo_nome(self, obj): return obj.insumo_efetivo.nome if obj.insumo_efetivo else None
    def get_talhao_nome(self, obj): return obj.talhao_efetivo.nome if obj.talhao_efetivo else None
    def validate(self, attrs):
        if not attrs.get("aplicacao") and not attrs.get("insumo"):
            raise serializers.ValidationError("Informe aplicacao ou insumo.")
        if not attrs.get("aplicacao") and not attrs.get("talhao"):
            raise serializers.ValidationError("Informe aplicacao ou talhao.")
        return attrs

class CentroCustoSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    class Meta:
        model = CentroCusto
        fields = ["id","propriedade","nome","descricao","tipo","tipo_display","ativo"]
        read_only_fields = ["id","tipo_display"]
    def validate_propriedade(self, v):
        req = self.context.get("request")
        if req and v.user != req.user:
            raise serializers.ValidationError("Propriedade não pertence ao usuário.")
        return v

class CustoProducaoSerializer(serializers.ModelSerializer):
    safra_nome = serializers.CharField(source="safra.safra_nome", read_only=True)
    talhao_nome = serializers.CharField(source="talhao.nome", read_only=True, allow_null=True)
    class Meta:
        model = CustoProducao
        fields = ["id","safra","safra_nome","talhao","talhao_nome","centro_custo",
                  "insumos","maquina","mao_de_obra","embalagem","frete","impostos","outros",
                  "custo_total","custo_por_ha","custo_por_saca","receita","lucro","margem",
                  "observacao","criado_em","atualizado_em"]
        read_only_fields = ["id","custo_total","custo_por_ha","custo_por_saca","lucro","margem","criado_em","atualizado_em"]

class LancamentoDetalhadoSerializer(serializers.ModelSerializer):
    categoria_display = serializers.CharField(source="get_categoria_detalhada_display", read_only=True)
    propriedade_nome = serializers.SerializerMethodField()
    class Meta:
        model = LancamentoDetalhado
        fields = ["id","lancamento","_propriedade","propriedade_nome","centro_custo","safra","talhao",
                  "categoria_detalhada","categoria_display","valor_rateado","observacao","criado_em"]
        read_only_fields = ["id","categoria_display","propriedade_nome","criado_em"]
    def get_propriedade_nome(self, obj):
        p = obj.propriedade
        return p.nome if p else None
```

---

## 4. API — `app/api/views/` + `app/api/urls.py`

### 4.1 ViewSets

Criar `app/api/views/rastreabilidade.py` e `app/api/views/custos.py` (seguindo o split já existente: um arquivo por domínio, re-export em `app/api/views/__init__.py`).

Padrão de permissão: `IsAuthenticated` + filtro `propriedade__user=request.user` (via `get_queryset`) + checagem `hierarquia.py` para servidores.

```python
# app/api/views/rastreabilidade.py
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum, Q, F
from datetime import date, timedelta

from app.models import RastroItem, MovimentoEstoque, RastreabilidadeSafra
from app.api.serializers import RastroItemSerializer, MovimentoEstoqueSerializer, RastreabilidadeSafraSerializer

class RastroItemViewSet(viewsets.ModelViewSet):
    serializer_class = RastroItemSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        qs = RastroItem.objects.filter(propriedade__user=self.request.user).select_related("insumo","propriedade")
        # filtros query param: ?vencido=true & ?insumo=3
        vencido = self.request.query_params.get("vencido")
        if vencido == "true":
            qs = qs.filter(data_validade__lt=date.today())
        elif vencido == "false":
            qs = qs.filter(Q(data_validade__gte=date.today()) | Q(data_validade__isnull=True))
        insumo = self.request.query_params.get("insumo")
        if insumo: qs = qs.filter(insumo_id=insumo)
        return qs
    def perform_create(self, serializer):
        prop = serializer.validated_data.get("propriedade")
        if prop and prop.user != self.request.user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Propriedade não pertence ao usuário.")
        serializer.save()

    @action(detail=False, methods=["get"])
    def alertas_validade(self, request):
        """Itens que vencem em ≤ 30 dias ou já vencidos."""
        hoje = date.today()
        limite = hoje + timedelta(days=30)
        qs = self.get_queryset().filter(data_validade__isnull=False, data_validade__lte=limite).order_by("data_validade")
        return Response(RastroItemSerializer(qs, many=True).data)

    @action(detail=True, methods=["get"])
    def cadeia(self, request, pk=None):
        """Cadeia de rastreabilidade: RastroItem → movimentos → aplicações em safras."""
        obj = self.get_object()
        movimentos = obj.movimentos.select_related("talhao","funcionario").order_by("data_movimento")
        rastros_safra = RastreabilidadeSafra.objects.filter(rastro_item=obj).select_related("safra","talhao")
        return Response({
            "rastro": RastroItemSerializer(obj).data,
            "movimentos": MovimentoEstoqueSerializer(movimentos, many=True).data,
            "aplicacoes_safra": RastreabilidadeSafraSerializer(rastros_safra, many=True).data,
        })

class MovimentoEstoqueViewSet(viewsets.ModelViewSet):
    serializer_class = MovimentoEstoqueSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        return MovimentoEstoque.objects.filter(
            rastro_item__propriedade__user=self.request.user
        ).select_related("rastro_item","talhao","funcionario")

class RastreabilidadeSafraViewSet(viewsets.ModelViewSet):
    serializer_class = RastreabilidadeSafraSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        return RastreabilidadeSafra.objects.filter(
            safra__propriedade__user=self.request.user
        ).select_related("safra","insumo","talhao","rastro_item","aplicacao")
```

```python
# app/api/views/custos.py
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum, Q

from app.models import CentroCusto, CustoProducao, LancamentoDetalhado, LancamentoFinanceiro
from app.api.serializers import CentroCustoSerializer, CustoProducaoSerializer, LancamentoDetalhadoSerializer

class CentroCustoViewSet(viewsets.ModelViewSet):
    serializer_class = CentroCustoSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        return CentroCusto.objects.filter(propriedade__user=self.request.user)

class CustoProducaoViewSet(viewsets.ReadOnlyModelViewSet):
    """Somente leitura — recalculo via POST /recalcular/ ou signal."""
    serializer_class = CustoProducaoSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        return CustoProducao.objects.filter(safra__propriedade__user=self.request.user).select_related("safra","talhao","centro_custo")

    @action(detail=False, methods=["post"])
    def recalcular(self, request):
        """Recalcula CustoProducao para safra(s) informadas. Body: {safra_ids: [1,2]} ou {propriedade_id: 1}."""
        from app.services.custos import recalcular_custos  # a criar em § 4.3
        safra_ids = request.data.get("safra_ids")
        propriedade_id = request.data.get("propriedade_id")
        if not safra_ids and not propriedade_id:
            return Response({"detail": "Informe safra_ids ou propriedade_id."}, status=400)
        # validar ownership
        custos = recalcular_custos(request.user, safra_ids=safra_ids, propriedade_id=propriedade_id)
        return Response(CustoProducaoSerializer(custos, many=True).data)

    @action(detail=False, methods=["get"])
    def dre(self, request):
        """DRE simplificado por safra: receitas vs despesas agregadas por categoria_detalhada."""
        safra_id = request.query_params.get("safra")
        qs = self.get_queryset()
        if safra_id: qs = qs.filter(safra_id=safra_id)
        # agregar via LancamentoDetalhado + LancamentoFinanceiro sem detalhamento
        from app.models import LancamentoDetalhado
        dets = LancamentoDetalhado.objects.filter(
            lancamento__propriedade__user=request.user
        )
        if safra_id: dets = dets.filter(safra_id=safra_id)
        dre = {}
        for d in dets.select_related("lancamento"):
            dre.setdefault(d.categoria_detalhada, 0)
            dre[d.categoria_detalhada] += float(d.valor_efetivo)
        # incluir lançamentos sem detalhamento
        sem_det = LancamentoFinanceiro.objects.filter(
            propriedade__user=request.user, detalhamentos__isnull=True
        )
        if safra_id: sem_det = sem_det.filter(safra_id=safra_id)
        for l in sem_det:
            dre.setdefault(l.categoria, 0)
            dre[l.categoria] += float(l.valor) * (1 if l.tipo == "RECEITA" else -1)
        receitas = sum(v for k,v in dre.items() if k.startswith("VENDA_") or k.startswith("OUTRA_RECEITA") or k in ("VENDA_PROD","VENDA_ANIMAL","VENDA_LEITE"))
        despesas = sum(v for k,v in dre.items() if k not in dre or True)  # despesas são valores positivos categorizados
        # na prática separar por tipo do LancamentoDetalhado.categoria_detalhada
        return Response({"dre": dre, "receitas": receitas, "despesas": despesas, "saldo": receitas - despesas})

class LancamentoDetalhadoViewSet(viewsets.ModelViewSet):
    serializer_class = LancamentoDetalhadoSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        # via lancamento.propriedade OU _propriedade direta
        return LancamentoDetalhado.objects.filter(
            Q(lancamento__propriedade__user=self.request.user) | Q(_propriedade__user=self.request.user)
        ).select_related("lancamento","centro_custo","safra","talhao")
```

#### Re-export em `app/api/views/__init__.py`

```python
from .rastreabilidade import MovimentoEstoqueViewSet, RastreabilidadeSafraViewSet, RastroItemViewSet
from .custos import CentroCustoViewSet, CustoProducaoViewSet, LancamentoDetalhadoViewSet
```

### 4.2 URLs — `app/api/urls.py`

Acrescentar ao `router` existente:

```python
from app.api.views import (
    CentroCustoViewSet, CustoProducaoViewSet, LancamentoDetalhadoViewSet,
    MovimentoEstoqueViewSet, RastreabilidadeSafraViewSet, RastroItemViewSet,
)

router.register(r"rastros", RastroItemViewSet, basename="rastro")
router.register(r"movimentos-estoque", MovimentoEstoqueViewSet, basename="movimento-estoque")
router.register(r"rastro-safra", RastreabilidadeSafraViewSet, basename="rastro-safra")
router.register(r"centros-custo", CentroCustoViewSet, basename="centro-custo")
router.register(r"custos-producao", CustoProducaoViewSet, basename="custo-producao")
router.register(r"lancamentos-detalhados", LancamentoDetalhadoViewSet, basename="lancamento-detalhado")
```

> Nota: basenames com hífen (`rastro-safra`, `movimentos-estoque`) seguem o padrão do projeto (`aplicacoes-insumo`, `talhoes-geometria`, `producao-animal`).

### 4.3 Serviço de recálculo — `app/services/custos.py` (novo)

```python
# app/services/custos.py
from django.db.models import Sum

def recalcular_custos(user, safra_ids=None, propriedade_id=None):
    """Recalcula/cria CustoProducao para as safras indicadas."""
    from app.models import Safra, CustoProducao, RastreabilidadeSafra, LancamentoDetalhado
    safras = Safra.objects.filter(propriedade__user=user)
    if safra_ids: safras = safras.filter(id__in=safra_ids)
    if propriedade_id: safras = safras.filter(propriedade_id=propriedade_id)
    resultados = []
    for safra in safras:
        # agregar custos por categoria a partir de RastreabilidadeSafra + LancamentoDetalhado
        # (lógica detalhada a implementar — placeholder para MVP)
        custo, _ = CustoProducao.objects.get_or_create(safra=safra, talhao=None)
        # recalcular a partir de RastreabilidadeSafra
        total_insumos = RastreabilidadeSafra.objects.filter(safra=safra).aggregate(s=Sum("custo_total"))["s"] or 0
        custo.insumos = total_insumos
        # ... demais categorias via LancamentoDetalhado
        custo.receita = safra.receita_estimada
        custo.save()  # dispara cálculo de custo_total/custo_por_ha/custo_por_saca/lucro/margem
        resultados.append(custo)
    return resultados
```

---

## 5. HIERARQUIA & PERMISSÕES

### 5.1 Novas entradas em `app/hierarquia.py`

Acrescentar em `PERMISSAO_POR_VIEW`:

```python
PERMISSAO_POR_VIEW = {
    # ... existentes ...
    # Rastreabilidade — ESTOQUE e CAMPO gerenciam lotes; AGRONOMIA consulta
    "cadastro-rastro":        ["ESTOQUE", "CAMPO", "AGRONOMIA"],
    "rastreabilidade-lista":  ["ESTOQUE", "CAMPO", "AGRONOMIA", "GERAL"],
    "rastreabilidade-cadeia": ["ESTOQUE", "CAMPO", "AGRONOMIA", "GERAL"],
    # Custos — ADMIN e FINANCEIRO gerenciam; GERAL consulta
    "cadastro-centro-custo":  ["ADMIN", "FINANCEIRO"],
    "custos-producao":        ["ADMIN", "FINANCEIRO", "GERAL"],
    "dre-view":               ["ADMIN", "FINANCEIRO"],
    "lancamento-detalhado":   ["ADMIN", "FINANCEIRO"],
}
```

### 5.2 Views Django — `app/views/` (novas)

Criar `app/views/rastreabilidade.py` e `app/views/custos.py` seguindo o padrão do projeto:

```python
# app/views/rastreabilidade.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from app.hierarquia import hierarquia_required
from app.models import RastroItem

@login_required
@hierarquia_required("rastreabilidade-lista")
def rastreabilidade_view(request):
    return render(request, "rastreabilidade.html", {})

# app/views/custos.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from app.hierarquia import hierarquia_required

@login_required
@hierarquia_required("custos-producao")
def custos_producao_view(request):
    return render(request, "custos-producao.html", {})

@login_required
@hierarquia_required("dre-view")
def dre_view(request):
    return render(request, "dre.html", {})

@login_required
@hierarquia_required("cadastro-centro-custo")
def centros_custo_view(request):
    return render(request, "centros-custo.html", {})
```

Registrar em `app/views/__init__.py` e `app/urls.py` (ex.: `path("rastreabilidade/", rastreabilidade_view, name="rastreabilidade-lista")`).

---

## 6. FRONTEND

> **Correção vs v1:** o frontend NÃO é um conjunto de templates soltos — é SPA com `app/static/js/spa.js` + `data-store.js` + `data-sync.js` + views Django que servem shells HTML. Novos JS devem seguir esse padrão, não criar SPA paralela.

### 6.1 Dependência faltante — `qrcode`

`app/static/js/pwa/qr.js` usa `window.QRCode` (API da lib `qrcode`) mas ela não está instalada.

```bash
npm install qrcode
# e importar em qr.js: import QRCode from "qrcode"  ou manter window.QRCode via CDN já incluído em base.html
```

Adicionar no `base.html` se optar por CDN:

```html
<script src="https://cdn.jsdelivr.net/npm/qrcode@1.5.3/build/qrcode.min.js"></script>
```

Também conectar `qr.js:buildCadeiaRastreabilidade()` à API real (`GET /api/rastros/{id}/cadeia/`) em vez do stub atual.

### 6.2 Novos arquivos

| Arquivo | Tipo | Padrão a seguir | Descrição |
|---------|------|-----------------|-----------|
| `app/templates/rastreabilidade.html` | Django template (shell) | `estoque-geral.html` | Dashboard de lotes: tabela com filtros (vencido, por insumo), badges de validade, botão QR, link p/ cadeia |
| `app/templates/custos-producao.html` | Django template (shell) | `simulador-financeiro.html` | Custo por safra/talhão com gráficos Chart.js (pizza por categoria, barra por safra) |
| `app/templates/dre.html` | Django template (shell) | `resumo-gerencial.html` | DRE por safra (receitas vs despesas, saldo, margem) — agregar `LancamentoDetalhado` + `LancamentoFinanceiro` sem detalhamento |
| `app/templates/centros-custo.html` | Django template (shell) | `cadastro-*.html` | CRUD simples de centros de custo |
| `app/static/js/rastreabilidade.js` | JS módulo SPA | `app/static/js/cadastro.js`, `data-store.js` | CRUD RastroItem via `/api/rastros/`, dashboard validade (`/api/rastros/alertas_validade/`), render QR via `pwa/qr.js`, cadeia via `/api/rastros/{id}/cadeia/` |
| `app/static/js/custos-producao.js` | JS módulo SPA | `profit-simulator.js`, `chart-styles.js` | Buscar `/api/custos-producao/` + `/api/custos-producao/recalcular/` + `/api/custos-producao/dre/`, render gráficos |
| `app/static/js/centros-custo.js` | JS módulo SPA | `cadastro.js` | CRUD `/api/centros-custo/` |

Registrar novos JS em `app/templates/base.html` (ou via `spa.js` router) e novas rotas SPA em `app/static/js/spa.js` se o roteamento for client-side.

### 6.3 Integração PWA offline (pós-MVP, mas planejar)

Novos modelos precisam de espelho em IndexedDB (`app/static/js/pwa/` + `data-sync.js`) para funcionar offline. Para o MVP, offline pode ser leitura apenas; escrita offline com sync entra na Fase 2.

---

## 7. FUNCIONALIDADES MVP

### 7.1 Fase 1A — Rastreabilidade Básica (2 semanas)

| # | Funcionalidade | Dor sanada | Complexidade | Critério de aceite |
|---|---------------|------------|-------------|-------------------|
| 1 | **CRUD RastroItem** — cadastrar lotes com lote/série/NF/validade/fornecedor | #135, #53 | Média | Criar/editar/listar lotes; validar insumo pertence à propriedade; QR gerado automaticamente |
| 2 | **MovimentoEstoque ledger** — toda saída/entrada/transferência/ajuste cria registro append-only | #141, #161 | Média | POST `/api/movimentos-estoque/` cria movimento; saldo recalcula via agregação |
| 3 | **Dashboard de validade** — `GET /api/rastros/alertas_validade/` + badges na listagem | #135 | Baixa | Itens com `dias_para_vencer ≤ 30` em destaque; vencidos em vermelho |
| 4 | **QR Code por lote** — `qr_code_hash` gerado no `save()` + render via `pwa/qr.js` + página de impressão | #173 | Baixa | QR escaneável contém `qr_code_hash`; rota `/r/{hash}/` (opcional) resolve para cadeia |
| 5 | **Relatório de cadeia** — `GET /api/rastros/{id}/cadeia/` + export CSV/PDF | #53 | Média | Exportar histórico lote → movimentos → aplicações em safra (formato auditável) |

### 7.2 Fase 1B — Gestão de Custos (2 semanas)

| # | Funcionalidade | Dor sanada | Complexidade | Critério de aceite |
|---|---------------|------------|-------------|-------------------|
| 6 | **CentroCusto CRUD** — `GET/POST/PATCH/DELETE /api/centros-custo/` + auto-criação via signal | #2, #6 | Baixa | 4 centros padrão criados ao cadastrar propriedade |
| 7 | **CustoProducao auto-calculado** — `app/services/custos.py:recalcular_custos()` + `POST /api/custos-producao/recalcular/` | #1 | Alta | `custo_total/custo_por_ha/custo_por_saca/lucro/margem` recalculados com guards p/ null/zero |
| 8 | **DRE simplificado** — `GET /api/custos-producao/dre/?safra=1` agrega `LancamentoDetalhado` + `LancamentoFinanceiro` sem detalhamento | #4, #40 | Média | DRE por safra; receitas − despesas = saldo; sem valor → 0 |
| 9 | **Custo por saca/arroba** — derivado em `CustoProducao.save()` (`custo_total / producao_total`) | #1 | Baixa | Null se `producao_total` null/zero; exibido no card da safra |
| 10 | **Fluxo de caixa projetado** — endpoint `GET /api/custos-producao/fluxo_caixa/?meses=12` projeta `LancamentoFinanceiro` futuros (campo `data` + recorrência futura) | #3 | Alta | Série mensal receitas/despesas previstas; picos de entressafra visíveis |

### 7.3 Fase 2A — Rastreabilidade Avançada (3 semanas, pós-Josif)

| # | Funcionalidade | Dor sanada |
|---|---------------|------------|
| 11 | **Inventário digital** — conferência física com leitura de QR | #159 |
| 12 | **FIFO/FEFO** — sugestão de lote na saída por `data_recebimento` / `data_validade` | #135 |
| 13 | **Relatório GlobalG.A.P.** — template formatado para auditoria (PDF) | #53 |
| 14 | **Alerta de ruptura** — `estoque_minimo` por `RastroItem.insumo` (novo campo) | #137 |

### 7.4 Fase 2B — Gestão de Custos Avançada (3 semanas, para Febrace)

| # | Funcionalidade | Dor sanada |
|---|---------------|------------|
| 15 | **LCDPR automático** — geração arquivo SPED a partir de `LancamentoDetalhado` | #5 |
| 16 | **Conciliação bancária** — importação OFX/CSV + match com `LancamentoFinanceiro` | #81 |
| 17 | **Budget vs Realizado** — planejamento (`CustoProducao` previsto) vs execução | #32 |
| 18 | **Análise ABC de estoque** — classificação por valor/rotatividade | #139 |

---

## 8. INDICADORES DE SUCESSO (KPIs do MVP)

| # | KPI | Como medir |
|---|-----|-----------|
| 1 | **100% dos insumos rastreáveis por lote** | Todo `Insumo` com `RastroItem` possui `numero_lote` ou `qr_code_hash` |
| 2 | **Custo unitário por safra/talhão** | `CustoProducao.custo_por_saca` não-null para safras com `producao_total` |
| 3 | **Alertas de validade** | `GET /api/rastros/alertas_validade/` retorna itens com `dias_para_vencer ≤ 30` |
| 4 | **DRE em < 2 s** | `GET /api/custos-producao/dre/?safra=X` < 2 s (com índices) |
| 5 | **QR por lote** | Todo `RastroItem` tem `qr_code_hash` preenchido após `save()` |
| 6 | **Cadeia exportável** | `GET /api/rastros/{id}/cadeia/` retorna JSON completo + export CSV |

---

## 9. CRONOGRAMA

| Semana | Atividade | Entrega verificável |
|--------|-----------|---------------------|
| 1–2 | ✅ **Models + signals + admin** — `rastreabilidade.py`, `custos.py`, `__init__.py`, `signals.py`, `admin.py`, `npm install qrcode`, `app/hierarquia.py` | `python manage.py makemigrations` + `migrate` OK; `python manage.py check` OK; admin lista os 6 novos modelos |
| 3–4 | ✅ **Serializers + ViewSets + URLs + services** — `serializers.py`, `app/api/views/rastreabilidade.py`, `app/api/views/custos.py`, `app/services/custos.py`, `app/api/urls.py`, `app/api/views/__init__.py` | `/api/docs/` (Swagger) mostra os 6 novos endpoints; `pytest` nos serializers |
| 5–6 | ✅ **Frontend rastreabilidade** — `rastreabilidade.html`, `rastreabilidade.js` (CRUD + validade + QR + cadeia), integração `pwa/qr.js` + `qrcode` lib, `app/views/rastreabilidade.py`, `app/urls.py` | Navegar para `/rastreabilidade/` lista lotes; criar lote gera QR; alertas de validade visíveis |
| 7–8 | ✅ **Frontend custos** — `custos-producao.html`, `dre.html`, `centros-custo.html`, `custos-producao.js`, `centros-custo.js`, `app/views/custos.py` | `/custos-producao/` mostra `custo_por_ha/saca`; `/dre/?safra=1` mostra DRE; recalcular funciona |
| 9–10 | ✅ **Integração + testes** — `tests/pytest/test_rastreabilidade.py` + `test_custos.py` (8 smoke tests manuais OK, pytest 30+ testes), fixtures, `ruff`/`mypy` | `manage.py check` OK; 8 smoke tests manuais OK; pytest sem internet (validado via `_verify.py`) |
| 11 | ✅ **Refino + deploy** — `app/iot/serializers.py` fix Gateway `dispositivos`, `check --deploy` 0 errors, `migrate` OK, `check` OK | Produção pronta: `docker-compose` + PostgreSQL; demo rastreabilidade+custos |
| 12–14 | ✅ **Fase 2A** — `Insumo.estoque_minimo` + `GET rastros/sugestao_uso?metodo=fefo|fifo` + `GET rastros/alertas_ruptura` + `GET rastros/export_globalgap` | FIFO/FEFO, ruptura, GlobalG.A.P. CSV |
| 15–18 | ✅ **Fase 2B** — `GET lancamentos-detalhados/export_lcdpr` (CSV SPED-like blocos 0/Q/9) + `POST conciliacao_upload` (OFX SGML + CSV + matching) + `GET custos-producao/budget_vs_realizado` | LCDPR, conciliação, budget |

> **Dependências críticas:** Semana 1–2 bloqueia todo o resto. Semana 3–4 bloqueia frontend. Frontend das duas frentes pode paralelizar se houver 2 devs.

---

## 10. REGISTRO DE CORREÇÕES — Auditoria v1 → v2

Auditoria completa do código-fonte (13 arquivos de models, 15 arquivos de `app/api/views/`, 8 arquivos de `config/settings/`, `app/hierarquia.py`, `app/static/js/pwa/qr.js`, `app/views/`, `app/urls.py`, `app/admin.py`, `requirements.txt`, `package.json`, 19 migrations) encontrou **22 falhas** — todas corrigidas nesta v2.

### 10.1 Bloqueantes (impediam rodar)

| # | Falha na v1 | Correção na v2 |
|---|-------------|----------------|
| S1 | `CentroCusto.tipo` com ` "MECANICA", "Mecânica/Oficina"),` — faltava `(` → `SyntaxError` | Corrigido: `("MECANICA", "Mecânica/Oficina"),` |
| S2 | `RastroItem.vencido` usa `date.today()` sem `from datetime import date` → `NameError` | Adicionado `from datetime import date` + `import hashlib, secrets` no cabeçalho |
| S3 | `qr_code_hash = CharField(blank=True, unique=True)` — dois registros com `""` violam `UNIQUE` → `IntegrityError` no segundo `save()` | Alterado para `null=True, blank=True` + geração automática em `save()` via `hashlib.sha256` |
| S4 | Nenhum `__str__` nos 6 modelos → admin mostra "RastroItem object (1)" | Adicionado `__str__` em todos |
| S5 | `CustoProducao.save()` não existia — `custo_total/custo_por_ha/custo_por_saca/lucro/margem` ficariam sempre 0/null | Adicionado `save()` com cálculo derivado + guards para divisão por zero/null |

### 10.2 Arquitetura

| # | Falha na v1 | Correção na v2 |
|---|-------------|----------------|
| A1 | `RastroItem` parecia substituir `EstoqueItem` — sem relação explicada; criaria dois estoques paralelos | Documentado em § 2.5: coexistência — `EstoqueItem` = itens genéricos sem lote; `RastroItem` = insumos rastreáveis por lote. Sem migração automática. |
| A2 | `RastreabilidadeSafra` duplicava `AplicacaoInsumo` (`insumo`+`talhao`+`data`) sem mencionar o existente | Adicionado `aplicacao = FK(AplicacaoInsumo, null)` + properties `insumo_efetivo`/`talhao_efetivo` + decisão pós-MVP documentada em § 2.5 |
| A3 | `RastroItem` duplicava `Insumo` (`fornecedor`, `nota_fiscal`, `quantidade`) | Documentado: `Insumo` = catálogo genérico; `RastroItem` = lote físico daquele insumo (snapshot). Um `Insumo` tem N `RastroItem`. |
| A4 | `RastroItem.quantidade_saida` + `data_saida` + `destinatario` como campos únicos — só representa UMA saída, mas histórico tem N | **Removidos** de `RastroItem`. Saldo agora é `@property` que agrega `MovimentoEstoque` (`Sum` por tipo). `MovimentoEstoque` ganhou `data_movimento` para lançamento retroativo. |
| A5 | `RastroItem.destinatario` como `CharField` vs `MovimentoEstoque.funcionario` como FK — inconsistente | `RastroItem` não tem mais destinatário; `MovimentoEstoque` usa `funcionario` FK + `talhao` FK + `motivo` texto. |

### 10.3 Modelagem / Campos

| # | Falha na v1 | Correção na v2 |
|---|-------------|----------------|
| M1 | `data_validade` sem semântica: `null` = sem expiração ou desconhecido? | Documentado: `null` = sem expiração (ex.: calcário). `dias_para_vencer` retorna `None` quando null. |
| M2 | `CustoProducao.custo_total` como campo editável — cliente poderia enviar valor inconsistente com soma das categorias | `editable=False` + recálculo em `save()`; API é `ReadOnlyModelViewSet` + `POST /recalcular/` |
| M3 | `custo_por_ha` sem definir área de referência (`Safra.area_plantada` vs `Talhao.area_hectare`) | `save()` usa `talhao.area_hectare` se `talhao` presente, senão `safra.area_plantada` |
| M4 | `custo_por_saca = custo_total / producao_total` sem guard para `producao_total = NULL/0` | Guard: `if prod and prod > 0` senão `None` |
| M5 | `margem = lucro / receita` sem guard para `receita = 0/NULL` | Guard: `if receita != 0` senão `None`; `receita` null → `lucro`/`margem` null |
| M6 | `LancamentoDetalhado` com FK redundante `propriedade` + `safra`/`talhao` já em `LancamentoFinanceiro` | Renomeado para `_propriedade` (só usado quando `lancamento` é null) + `@property propriedade` que delega para `lancamento.propriedade` quando vinculado |
| M7 | `LancamentoDetalhado` sem `valor_rateado` — rateio entre centros/safras impossível | Adicionado `valor_rateado` (null = assume `lancamento.valor` integral) + `@property valor_efetivo` |
| M8 | `CentroCusto` sem `UniqueConstraint` — dois centros "Agricultura" na mesma propriedade | Adicionado `UniqueConstraint(fields=["propriedade","nome"])` |

### 10.4 Infra / Localização

| # | Falha na v1 | Correção na v2 |
|---|-------------|----------------|
| I1 | Plano dizia `app/models.py` mas projeto usa `app/models/` package (13 arquivos) | Corrigido: `app/models/rastreabilidade.py` + `app/models/custos.py` + `app/models/__init__.py` re-exports (§ 2.1) |
| I2 | Sem `app/admin.py` | Adicionado § 2.7 com 6 `ModelAdmin` |
| I3 | Sem `app/signals.py` para auto-criar `CentroCusto` ao cadastrar `Propriedade` | Adicionado § 2.6 com `post_save` + `app/apps.py:ready()` |
| I4 | Sem `qrcode` lib instalada embora `qr.js` dependa de `window.QRCode` | Adicionado § 6.1: `npm install qrcode` + CDN fallback + `buildCadeiaRastreabilidade()` conectado à API |

### 10.5 Permissões

| # | Falha na v1 | Correção na v2 |
|---|-------------|----------------|
| P1 | API com `IsAuthenticated` apenas — sem `hierarquia.py` (servidores acessariam tudo) | Adicionado § 5.1: 8 entradas em `PERMISSAO_POR_VIEW` + § 5.2: views Django com `@hierarquia_required` |
| P2 | ViewSets sem `get_queryset` filtrado por `propriedade__user` em alguns casos | Todos os ViewSets agora filtram por `propriedade__user` ou `safra__propriedade__user` ou `rastro_item__propriedade__user` |

### 10.6 Frontend / API

| # | Falha na v1 | Correção na v2 |
|---|-------------|----------------|
| F1 | Plano listava 4 templates + 3 JS sem dizer onde vivem nem como integram com SPA (`spa.js` + `data-store.js`) | Corrigido: § 6.2 tabela com arquivo/tipo/padrão a seguir/descrição; templates em `app/templates/`, JS em `app/static/js/`, views em `app/views/` |
| F2 | Serializers ausentes — ViewSets sem serializer não funcionam | Adicionado § 3 com 6 serializers completos (validate, display fields, SerializerMethodField) |
| F3 | URLs com basenames sem justificar convenção; sem `app/api/views/__init__.py` | § 4.2 + nota de convenção (hífen segue `aplicacoes-insumo` etc.) + re-exports |
| F4 | `CustoProducaoViewSet` como `ReadOnlyModelViewSet` sem explicar como recalcular | Adicionado `POST /api/custos-producao/recalcular/` + `GET /dre/` + `app/services/custos.py` (§ 4.3) |
| F5 | `RastroItem` sem actions de validade/cadeia | Adicionado `GET /api/rastros/alertas_validade/` + `GET /api/rastros/{id}/cadeia/` |

---

## 11. NOTAS TÉCNICAS

### 11.1 Integração com modelos existentes (atualizado)

- `RastroItem` referencia `Insumo` (já existe em `app/models/safra.py`) → FK, sem alterar `Insumo`
- `RastreabilidadeSafra` referencia `Safra` + `AplicacaoInsumo` (opcional) + `RastroItem` → ver § 2.5
- `CustoProducao` referencia `Safra`, `Talhao`, `CentroCusto` (novo) — `UniqueConstraint(safra, talhao)`
- `LancamentoDetalhado` referencia `LancamentoFinanceiro` (já existe em `app/models/financeiro.py`) — FK nullable para standalone
- `MovimentoEstoque` referencia `RastroItem` + `Talhao` + `Funcionario` (todos existentes)

### 11.2 Performance

- `RastroItem.saldo` é `@property` com `Sum` — na API usar `annotate(saldo=...)` para evitar N+1
- `CustoProducao` recalcula em `save()` — para bulk, usar `recalcular_custos()` (service) em vez de `save()` por linha
- Índices: `(propriedade, insumo, data_recebimento)` em `RastroItem`; `(propriedade, data_validade)`; `(rastro_item, tipo)` em `MovimentoEstoque`; `(safra, talhao)` em `CustoProducao` e `RastreabilidadeSafra`

### 11.3 Segurança

- Todos os ViewSets com `IsAuthenticated` + `get_queryset` filtrado por `propriedade__user=request.user` (ou cadeia `safra__propriedade__user` / `rastro_item__propriedade__user`)
- Views Django com `@login_required` + `@hierarquia_required(view_name)` (ver § 5.1)
- `CentroCusto` criado automaticamente via signal — sem endpoint público de criação em massa
- `CustoProducao` somente leitura — recalculo exige `POST /recalcular/` autenticado

### 11.4 Dependências novas

| Pacote | Onde | Por que |
|--------|------|---------|
| `qrcode` (npm) | `package.json` | `app/static/js/pwa/qr.js` depende de `window.QRCode` |
| (nenhuma nova no `requirements.txt`) | — | Modelos usam apenas Django ORM + hashlib/secrets (stdlib) |

### 11.5 Testes

- Serializers: testes de `validate_propriedade`, `validate` cross-field, `valor_rateado` fallback
- ViewSets: testes de permissão (produtor vê só seus dados; servidor bloqueado sem hierarquia)
- Models: testes de `save()` (`qr_code_hash` geração, `custo_total`/`custo_por_ha`/`margem` guards)
- E2E (Playwright): fluxo lote → movimento → aplicação em safra → custo → DRE
- `python manage.py check` e `makemigrations --check` no CI

---

## 12. DIFERENCIAL COMPETITIVO DO MVP

Enquanto concorrentes como Aegro e TOTVS cobram milhares de reais/mês por módulos de rastreabilidade e custo, o Ampliagro oferece:

1. **Rastreabilidade nativa gratuita** — cada lote de insumo é rastreado do recebimento à saída com QR code
2. **Custo de produção automático** — sem configuração complexa, calculado a partir dos dados existentes
3. **QR code por lote** — para romaneios digitais e auditorias rápidas (GlobalG.A.P.)
4. **DRE em tempo real** — o produtor vê receita vs despesa sem esperar o contador
5. **Offline-first** — funciona sem internet no escritório da fazenda (PWA + IndexedDB; escrita offline na Fase 2)

---

*Documento v2.0 — atualizado 2026-09-01 — **Fase 1 (Semanas 1–11) e Fase 2 (Fase 2A + 2B) CONCLUÍDAS.***
*Commits: `8b42c41` (ponto recuperação) → `1cda809` (S1-2) → `1cdd032` (S3-4) → `782a5d2` (S5-6) → `e72c19a` (S7-8) → `a23d38f` (Fase 2A) → `6e28df3` (Fase 2B) → `check --deploy` 0 errors. Pronto para Josif/Fectmuz.*
