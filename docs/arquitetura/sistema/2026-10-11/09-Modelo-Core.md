# Modelo Core (Propriedade, Talhão, Cultura, Análise de Solo, Membros) — Estado 2026-10-11

> Fonte: `app/models/core.py` (495 linhas)

---

## 1. Cultura (`app/models/core.py:19-66`)

### Campos Principais
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `nome` | CharField(100) | Nome da cultura |
| `grupo` | CharField(20, choices=GRUPOS) | 39 grupos (grãos, frutas, forrageiras, etc.) |
| `unidade_comercial` | CharField(50) | Default "sacas" |
| `janela_plantio_inicio/fim` | IntegerField | Mês (1-12), nullable |
| `chave_mercado` | CharField(100) | Para integração cotações |
| `ibge_codigo` | IntegerField | Código IBGE SIDRA (classificação 782) |
| `ciclo_dias` | IntegerField | Ciclo médio em dias |
| `ativo` | BooleanField | Default True |

**GRUPOS (39):** graos, frutas, citricos, hortalicas, tuberculos, ervas, leguminosas, oleaginosas, frutas_bosque, especiarias, medicinais, panc, trepadeiras, cana, fibras, nativas, forrageiras, pastagem, florestal, outro

---

## 2. Propriedade (`app/models/core.py:83-275`)

### Identidade
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `user` | FK(User) | Dono (CASCADE) |
| `nome` | CharField(100) | Nome da fazenda |
| `area_total` | DecimalField(10,2) | Hectares totais |
| `uf/cidade/endereco` | Char/Text | Localização |
| `bioma` | CharField(20, choices=BIOMAS) | 6 biomas brasileiros |

### LCDPR - Campos Fiscais (críticos)
| Campo | Registros LCDPR | Obrigatório? | Nota |
|-------|----------------|--------------|------|
| `cpf_cnpj` | 0000 | Sim | 11 dígitos (CPF) |
| `caepf` | 0040 | Se tipo=1 | 14 dígitos |
| `inscricao_estadual` | 0040 | | |
| `tipo_exploracao` | 0040 | Sim | 1-6 (individual, condomínio, etc.) |
| `participacao` | 0040 | Sim | % (default 100%) |
| `forma_apuracao` | 0010 | Sim | "1"=Livro Caixa, "2"=20% receita bruta |

### Endereço Fiscal (OBRIGATÓRIO no LCDPR)
| Campo | Registros | Formato | Fonte |
|-------|-----------|---------|-------|
| `cod_municipio` | 0030, 0040 | 7 dígitos IBGE | Tabela Receita (sped.rfb.gov.br/pasta/show/1932) |
| `cep` | 0030, 0040 | 8 dígitos | Só números |
| `bairro` | 0030, 0040 | Char(100) | |
| `telefone` | 0030 | 15 dígitos (DDD+número) | Opcional |
| `cad_itr` | 0040 | 8 dígitos c/ DV | **Não é CAEPF** |

### Geolocalização
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `latitude/longitude` | FloatField | Graus decimais, nullable |
| `geometria` | JSONField | GeoJSON Polygon/MultiPolygon |

---

## 3. MembroPropriedade (`app/models/core.py:278-365`)

**Resolve:** Tecto de 3 propriedades por usuário (1 própria + 1 vinculada + 1 funcionário)

### Papéis
| Papel | Descrição |
|-------|-----------|
| `DONO` | Dono (único por propriedade, constraint) |
| `ADMIN` | Administrador |
| `AGRONOMO` | Agrônomo |
| `CONTADOR` | Contador |
| `OPERADOR` | Operador de campo |
| `CONSULTOR` | Leitura apenas |

### Constraints
- `unique_together (propriedade, user)` — um usuário uma vez por propriedade
- `unique_constraint (propriedade, papel=DONO)` — **um único dono**

### O que NÃO faz
- ❌ Não concede acesso (ver `app/hierarquia.py:propriedades_visiveis`)
- ❌ Não substitui o dono (`Propriedade.user` continua sendo o dono)
- ❌ Não copia permissão (papel = escopo ver/editar; permissão fina = `pode_ver_financeiro`)

---

## 4. Talhão & Geometria (`app/models/core.py:367-413`)

### Talhão
| Campo | Tipo |
|-------|------|
| `propriedade` | FK(Propriedade) |
| `nome` | CharField(100) |
| `area_hectare` | DecimalField(8,2) |
| `cultura_atual` | FK(Cultura, SET_NULL) |
| `tipo_solo` | CharField(50) |
| `coordenadas` | JSONField (legacy) |
| `ativo` | BooleanField |

### TalhaoGeometria (OneToOne)
| Campo | Tipo |
|-------|------|
| `geojson` | JSONField (Feature Polygon/MultiPolygon) |
| `area_calculada_ha` | DecimalField(10,3) |
| `centroide_lat/lon` | DecimalField(9,6) |

---

## 5. AnaliseSolo (`app/models/core.py:416-477`)

| Campo | Unidade | Descrição |
|-------|---------|-----------|
| `ph` | | pH em água |
| `fosforo_p` | mg/dm³ | P (Mehlich-1) |
| `potassio_k` | cmolc/dm³ | K |
| `calcio_ca` | cmolc/dm³ | Ca |
| `magnesio_mg` | cmolc/dm³ | Mg |
| `aluminio_al` | cmolc/dm³ | Al |
| `materia_organica_mo` | % | MO |
| `ctc` | cmolc/dm³ | Capacidade Troca Catiônica |
| `saturacao_bases_v` | % | V% (Saturação por bases) |

---

## 6. AreaPreservacao (`app/models/core.py:479-495`)

| Tipo | Descrição |
|------|-----------|
| `APP` | Área de Preservação Permanente |
| `RL` | Reserva Legal |
| `OUTRO` | Outra Proteção |

---

## 7. Decisões de Projeto (do docstring)

### MembroPropriedade — Removeu tecto de 3
- Antes: `app/hierarquia.py:207` limitava a 3 (1 própria + 1 vinculada + 1 funcionário)
- Agora: ilimitado via `MembroPropriedade`
- **Maior retorno de produto** do `docs/sistema/7.md`

### LCDPR — Modelo cresceu para o gerador
- Gerador (`lcdpr_export.py`) já escrevia campos
- Guarda (`pode_exportar`) já exigia
- **Sem campos no modelo, guarda nunca tinha o que ler** — regra que dispara sempre sobre campos inexistentes
- Padrão inverso: noutros sítios modelo cresce e gerador atrasa; aqui gerador crescia e modelo faltava

### `cod_municipio` ≠ `cidade`
- `cidade` = **nome** do município
- `cod_municipio` = **código IBGE** (7 dígitos)
- Tabela Receita: `sped.rfb.gov.br/pasta/show/1932`

### `cad_itr` ≠ `caepf`
- `CAEPF` = atividade econômica da pessoa física (IN RFB 1.828/2018)
- `CAD_ITR` = imóvel no Cadastro Imobiliário Nacional
- **Dois registos diferentes para não se trocarem**

---

## 8. Constraints & Indexes

| Modelo | Constraint/Index |
|--------|------------------|
| `Cultura` | ordering `["nome"]` |
| `Propriedade` | ordering `["nome"]` |
| `MembroPropriedade` | `unique_together (propriedade, user)`, `unique_constraint (propriedade, papel=DONO)`, index `["user", "ativo"]` |
| `Talhao` | index `["propriedade", "nome"]` |
| `AnaliseSolo` | ordering `["-data_coleta"]` |

---

## 9. Testes Relacionados

```bash
python -m pytest tests/test_cascata_cultura.py -v
python -m pytest tests/test_lcdpr_campos_fiscais.py -v
python -m pytest tests/test_multi_propriedade.py -v
```