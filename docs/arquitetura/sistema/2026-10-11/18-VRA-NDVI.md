# VRA (Taxa Variável) & NDVI — Estado 2026-10-11

> Fontes: `app/models/producao.py` (PrescricaoVRA), `app/api/views/vra.py`, `app/api/views/agronomia.py`, `app/services/vra.py`

---

## 1. PrescricaoVRA (`app/models/producao.py:170-377`)

### Campos Principais
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `safra` | FK(Safra) | |
| `talhao` | FK(Talhao) | |
| `cultura` | FK(Cultura, PROTECT) | |
| `tipo_insumo` | CharField(20) | FERTILIZANTE, CORRETIVO, DEFENSIVO, SEMENTE |
| `insumo` | FK(Insumo, SET_NULL) | |
| `dose_ha` | DecimalField(8,2) | Dose por hectare |
| `unidade` | CharField(20) | |
| `grade_geojson` | JSONField | FeatureCollection c/ células + dose_ha |
| `iso_xml` | TextField | ISOXML para controlador |
| `arquivo_iso` | FileField | .iso/.xml/.bin |

### Proveniência (A2) — O que a prescrição PREVIU
| Campo | Descrição |
|-------|-----------|
| `produtividade_esperada` | O que a recomendação previa que a dose produziria (mesma unidade de `Safra.produtividade`). NULL = previsão não registrada. |
| `contexto_recomendacao` | JSONField — evidência que produziu a recomendação: clima/solo medidos no momento, com carimbo `fonte_dado` (medido/sem_dado/suspect). |
| `versao_analise` | Versão do conhecimento agronômico que produziu a dose. |

### Erro Medido Contra Desfecho (Properties)
```python
@property
def produtividade_realizada(self):
    return self.safra.produtividade if self.safra_id else None

@property
def erro_percentual(self):
    realizada = self.produtividade_realizada
    esperada = self.produtividade_esperada
    if realizada is None or esperada is None: return None
    r = float(realizada)
    if r == 0.0: return None
    return round((float(esperada) - r) / r * 100.0, 2)

@property
def fonte_dado_erro(self):
    if self.produtividade_esperada is None or self.produtividade_realizada is None:
        return "sem_dado"
    if self.erro_percentual is None:
        return "medido_sem_erro"  # realizada = 0
    return "medido"

@property
def proveniencia(self):
    return {
        "prescricao_id": self.pk,
        "talhao_id": self.talhao_id,
        "safra_id": self.safra_id,
        "dose_ha": float(self.dose_ha),
        "unidade": self.unidade,
        "produtividade_esperada": float(self.produtividade_esperada) if self.produtividade_esperada else None,
        "produtividade_realizada": float(self.produtividade_realizada) if self.produtividade_realizada else None,
        "erro_percentual": self.erro_percentual,
        "fonte_dado_erro": self.fonte_dado_erro,
        "versao_analise": self.versao_analise or None,
        "contexto_recomendacao": self.contexto_recomendacao or {},
        "criado_em": self.criado_em.isoformat() if self.criado_em else None,
    }
```

**Estados de `fonte_dado_erro`:**
| Estado | Significado |
|--------|-------------|
| `medido` | Duas pontas existem e erro calcula-se |
| `medido_sem_erro` | Duas pontas existem, mas erro não definível (realizada = 0) |
| `sem_dado` | Falta uma das pontas |

---

## 2. ZARC (`app/models/producao.py:379-401`)

Zoneamento Agrícola de Risco Climático.

| Campo | Descrição |
|-------|-----------|
| `cultura` | FK(Cultura, PROTECT) |
| `uf/municipio` | UF (2 chars) + município |
| `data_inicio_plantio/data_fim_plantio` | Janela |
| `ciclo_dias` | Dias |
| `risco_climatico` | Decimal (default 0.2) |

**Constraint:** `unique_together = ("cultura", "uf", "municipio")`

---

## 3. Experimento & MedicaoExperimental (A2b — Laço de Medição)

### Experimento (`app/models/producao.py:453-552`)
| Campo | Descrição |
|-------|-----------|
| `uid` | CharField(64, unique, default=uuid4) — **idempotência** |
| `user/propriedade/safra/cultura` | FKs (nullable) |
| `nome/hypothesis/variavel` | Texto |
| `tratamento_a/tratamento_b` | JSONField |
| `talhao_a/talhao_b` | FK(Talhao, SET_NULL) |
| `metricas` | JSONField (lista) |
| `significance_level` | FloatField (default 0.05) — **barra decidida ANTES de ver resultados** |
| `status` | `ativo`/`concluido`/`arquivado` |
| `contexto_inicial/versao_analise` | JSON/Char — evidência inicial |

**Idempotência:** `uid` gerado **no cliente** + constraint `unique` → servidor faz `update_or_create` por `uid`. Mesmo push 2x = mesmo registo.

**Dois relógios:**
- `registado_em` — relógio do **produtor** (quando mediu no talhão)
- `sincronizado_em` — relógio do **servidor** (quando chegou)
- Diferença = informação (condição climática da medição)

### MedicaoExperimental (`app/models/producao.py:554-635`)
| Campo | Descrição |
|-------|-----------|
| `uid` | CharField(64, unique, default=uuid4) |
| `experimento` | FK(Experimento) |
| `prescricao` | FK(PrescricaoVRA, SET_NULL) — **fecha laço §4.3** |
| `tratamento` | `A` / `B` |
| `talhao` | FK(Talhao, SET_NULL) |
| `dados` | JSONField — `{produtividade: 65, custo: 1200, ...}` |
| `contexto` | JSONField — clima/solo no momento, **CADA campo com `fonte_dado`** |
| `fonte_dado` | CharField — `medido`, `medido_com_ressalva`, `suspect`, `declarado`, `sem_dado` |
| `registado_em/sincronizado_em` | Dois relógios |

**`declarado`:** Produtor AFIRMOU; afirmar NÃO é medir. Planilha importada continua `declarado` — importar não transforma declaração em medição.

---

## 4. API Views VRA (`app/api/views/vra.py`)

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/api/prescricoes-vra/` | CRUD | `PrescricaoVRAViewSet` |
| `/api/zarc/` | CRUD | `ZARCViewSet` |
| `/api/experimentos/` | CRUD | `ExperimentoViewSet` |
| `/api/experimentos/{id}/medicoes/` | POST | Adiciona medição (idempotente por `uid`) |

---

## 5. NDVI (`app/api/views/agronomia.py`)

### Endpoints
| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/api/agronomia/ndvi/` | GET | NDVI médio por talhão |
| `/api/agronomia/ndvi/historico/` | GET | Série temporal NDVI |
| `/api/agronomia/ndvi/alerta/` | GET | Alertas NDVI (queda brusca) |

### Validação de Talhão
```python
talhao = get_object_or_404(Talhao, pk=talhao_id, propriedade__user=request.user)
```
**Tenancy:** `propriedade__user=request.user` — talhão só do usuário.

---

## 6. NDVI Tool (IA Intent)

### `app/amplia_mcp/ferramentas_aceitas.py` → `ndvi`
```python
"ndvi": {
    "descricao": "NDVI médio por talhão + histórico + alertas",
    "parametros": ["talhao_id", "data_inicio", "data_fim"],
    "retorno": {"ndvi_medio", "historico", "alertas"}
}
```

**Fonte de dados:** Sentinel-2 / Landsat via API externa (configurável).

---

## 7. Integração Proveniência (A2)

### Laço Fechado
```
PrescricaoVRA (dose_ha + contexto_recomendacao + versao_analise)
    ↓ aplicação
MedicaoExperimental (dados + contexto + fonte_dado)
    ↓ colheita
Safra.produtividade (realizada)
    ↓
erro_percentual = (esperada - realizada) / realizada * 100
fonte_dado_erro = "medido" | "medido_sem_erro" | "sem_dado"
```

### Auditoria (`proveniencia` property)
```json
{
  "prescricao_id": 123,
  "talhao_id": 45,
  "safra_id": 78,
  "dose_ha": 120.5,
  "unidade": "kg/ha",
  "produtividade_esperada": 65.0,
  "produtividade_realizada": 62.3,
  "erro_percentual": 4.1,
  "fonte_dado_erro": "medido",
  "versao_analise": "v2.1-soja-MT",
  "contexto_recomendacao": {"clima": "medido", "solo": "medido"},
  "criado_em": "2026-03-15T10:30:00Z"
}
```

---

## 8. Guardas de Regressão

| Teste | O que impede |
|-------|--------------|
| `tests/test_lcdpr_campos_fiscais.py` | Campos VRA no LCDPR |
| `tests/test_lcdpr_leiaute.py` | Leiaute ISOXML válido |
| `app/tests_proativo.py` | Experimento idempotente por `uid` |
| `tests/test_lcdpr_campos_fiscais.py` | `versao_analise` não vazia |

---

## 9. Checklist de Operação

- [ ] `PrescricaoVRA` com `versao_analise` preenchida
- [ ] `contexto_recomendacao` com `fonte_dado` por campo
- [ ] `Experimento` com `uid` gerado no cliente (idempotente)
- [ ] `MedicaoExperimental` com `fonte_dado` por campo
- [ ] `Safra.produtividade` preenchida na colheita
- [ ] `proveniencia` exportável para auditoria/MRV