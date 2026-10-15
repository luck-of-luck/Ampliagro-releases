# Modelo Pecuária (Animal, Produção, Sanidade, Piquete, Mix Pastagem, Ração) — Estado 2026-10-11

> Fonte: `app/models/pecuaria.py` (377 linhas)

---

## 1. Animal (Rebanho por Lote) (`app/models/pecuaria.py:34-60`)

### Espécies
| Código | Descrição |
|-------|-----------|
| `BOVINO` | Bovino |
| `SUINO` | Suíno |
| `OVINO` | Ovino |
| `CAPRINO` | Caprino |
| `EQUINO` | Equino |
| `BUFALO` | Búfalo |
| `AVES` | Aves |
| `COELHO` | Coelho |
| `PEIXE` | Peixe |

### Tipos de Produção
| Código | Descrição |
|-------|-----------|
| `CORTE` | Corte |
| `LEITE` | Leite |
| `OVOS` | Ovos |
| `MISTO` | Misto |
| `MEL` | Mel |
| `OUTRO` | Outro |

### Campos
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `propriedade` | FK(Propriedade) | CASCADE |
| `especie` | CharField(10) | Choices ESPECIES_ANIMAL |
| `tipo_producao` | CharField(10) | Choices TIPOS_PRODUCAO_ANIMAL |
| `raca` | CharField(100) | |
| `quantidade` | IntegerField | Cabeças no lote |
| `peso_medio` | DecimalField(6,2) | kg |
| `data_entrada` | DateField | |
| `observacao` | TextField | |

**Indexes:** `["propriedade", "especie"]`

---

## 2. ProducaoAnimal (`app/models/pecuaria.py:62-83`)

Registro de produção por lote animal.

| Campo | Tipo |
|-------|------|
| `animal` | FK(Animal) |
| `data` | DateField |
| `quantidade_produzida` | DecimalField(8,2) |
| `unidade` | CharField(20) |
| `valor_estimado` | DecimalField(8,2) |

**Ordering:** `["-data"]`

---

## 3. AnimalIndividual (`app/models/pecuaria.py:85-136`)

Rastreamento individual (brinco, genealogia, pesagens, sanidade).

### Identificação
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `brinco` | CharField(20) | **Não unique global** — validado por fazenda na aplicação |
| `brinco_eletronico` | CharField(30) | RFID/EID |
| `nome` | CharField(50) | Apelido |
| `especie/raca/sexo` | Choices | |
| `data_nascimento` | DateField | |

### Genealogia
| Campo | Tipo |
|-------|------|
| `pai` | FK(self, SET_NULL) |
| `mae` | FK(self, SET_NULL) |

### Status
| Código | Descrição |
|--------|-----------|
| `ativo` | Padrão |
| `vendido` | |
| `morto` | |
| `descartado` | |

### Relacionamentos
| Relacionamento | Modelo | Via |
|----------------|--------|-----|
| `pesagens` | `Pesagem` | FK(AnimalIndividual) |
| `eventos_sanitarios` | `EventoSanitario` | FK(AnimalIndividual) |
| `piquetes_atuais` | `Piquete` | M2M |

---

## 4. Pesagem (`app/models/pecuaria.py:138-152`)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `animal` | FK(AnimalIndividual) | |
| `data` | DateField | Default now |
| `peso` | DecimalField(6,2) | kg |
| `tipo` | CharField(20) | `entrada`, `rotina`, `saida` |

---

## 5. ProtocoloSanitario & EventoSanitario (`app/models/pecuaria.py:154-190`)

### ProtocoloSanitario
| Campo | Descrição |
|-------|-----------|
| `nome` | Nome do protocolo |
| `especie` | Choices ESPECIES_ANIMAL |
| `dias_para_repeticao` | IntegerField (próxima dose) |

### EventoSanitario (execução)
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `animal` | FK(AnimalIndividual) | |
| `protocolo` | FK(ProtocoloSanitario) | SET_NULL |
| `data` | DateField | Default now |
| `tipo` | CharField(30) | `vacina`, `vermifugo`, `tratamento` |
| `produto` | CharField(100) | Nome comercial |
| `dose` | CharField(50) | |
| `responsavel` | CharField(100) | |
| `proxima_dose` | DateField | Calculada via `dias_para_repeticao` |

---

## 6. Piquete & MixPastagem (`app/models/pecuaria.py:192-316`)

### Piquete (`app/models/pecuaria.py:192-223`)
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `propriedade` | FK(Propriedade) | |
| `talhao` | FK(Talhao, SET_NULL) | Opcional |
| `nome` | CharField(100) | |
| `area_hectare` | DecimalField(8,2) | |
| `capacidade_ua_ha` | DecimalField(6,2) | UA/ha estimada |
| `status` | CharField(20) | `descanso`, `pastejo`, `manutencao` |
| `animais` | M2M(AnimalIndividual) | Atuais no piquete |

### MixPastagem (`app/models/pecuaria.py:259-316`) — **G-06**

**O que resolve:** `Piquete.capacidade_ua_ha` era número sem lastro — capacidade depende do que está no piquete, e o piquete não dizia o que tinha nele.

### Modelo
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `piquete` | FK(Piquete) | |
| `cultura` | FK(Cultura, PROTECT) | Espécie forrageira |
| `pct` | DecimalField(5,2) | % (0-100) |
| `taxa_semeadura_kg_ha` | DecimalField(8,2) | Null até declarar |
| `data_semeadura` | DateField | |
| `fonte_dado` | CharField(20) | Default `declarado` |

### Validação de Soma (`checar_soma_mix`)
```python
def checar_soma_mix(piquete_id, pct, exclude_pk=None):
    outras = MixPastagem.objects.filter(piquete_id=piquete_id)
              .exclude(pk=exclude_pk).aggregate(s=Sum("pct"))["s"] or 0
    soma = outras + pct
    if soma > 100:
        return soma, f"Soma do mix ({soma}%) passa de 100%."
    return soma, None  # < 100 = aceiro/cocho/área não semeada (passa)
```

**Regra:** Soma > 100 → erro físico impossível. Soma < 100 → passa (aceiro/cocho).

**Constraints:** `unique_together (piquete, cultura)` — uma cultura uma vez por piquete.

### Property: `pct_nao_atribuido`
```python
@property
def pct_nao_atribuido(self):
    return max(Decimal("100") - (soma_real or 0), Decimal("0.00"))
```

---

## 7. Racao (`app/models/pecuaria.py:318-377`)

**Duas faces:** Estoque (nutrição) + Formulação (cadastro animal).

### Estoque/Nutrição
| Campo | Descrição |
|-------|-----------|
| `tipo` | `CONCENTRADO`, `VOLUMOSO`, `MINERAL` |
| `quantidade` | DecimalField(10,2) kg |
| `fornecedor/data_validade` | Controle de estoque |

### Formulação (aba rações do cadastro animal)
| Campo | Descrição |
|-------|-----------|
| `especie_alvo` | BOVINO, SUINO, OVINO, CAPRINO, AVES, PEIXE |
| `fase` | CRESCIMENTO, TERMINACAO, LACTACAO, REPRODUCAO, MANUTENCAO |
| `composicao` | TextField (texto/JSON percentual) |
| `custo_kg` | DecimalField(10,2) |

---

## 8. Guardas de Regressão

| Teste | O que impede |
|-------|--------------|
| `tests/test_mix_pastagem_g06.py` | Soma do mix ≤ 100%, constraint unique piquete+cultura |
| `tests/test_lote_semente_g02.py` | Semente rastreável |
| `tests/test_ensaio_cultivar_g03.py` | Ensaios cultivares |

---

## 9. Fluxos Principais

### Sanidade Animal
1. `ProtocoloSanitario` define calendário (`dias_para_repeticao`)
2. `EventoSanitario` registra execução → calcula `proxima_dose`
3. `calendario_sanitario` (intent) mostra próximas doses

### Pastejo Rotacionado
1. `Piquete.status` = `pastejo`/`descanso`/`manutencao`
2. `MixPastagem` define o que tem no piquete → lastreia `capacidade_ua_ha`
3. `AnimalIndividual.piquetes_atuais` mostra onde cada animal está

### Nutrição
1. `Racao` (estoque) → `quantidade` kg em estoque
2. `Racao` (formulação) → `composicao` + `custo_kg` para cálculo dieta
3. `ProducaoAnimal` → leite/ovos/corte por lote ou individual