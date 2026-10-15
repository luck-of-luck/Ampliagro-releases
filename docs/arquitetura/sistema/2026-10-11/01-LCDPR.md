# LCDPR (Livro Caixa Digital do Produtor Rural) — Estado 2026-10-11

> Fonte: `docs/sistema/HANDOVER-LCDPR.md`, `app/services/lcdpr_export.py`, `app/services/lcdpr_layout.py`, `PLANO-EXECUCAO.md` §2.1

---

## 1. O que está implementado

### Registos exportados (9/9 conforme Manual RFB 1.3)
| Registo | Nome | Campos | Status |
|---------|------|--------|--------|
| `0000` | Identificação do contribuinte | 10 | ✅ Completo |
| `0010` | Parâmetros de tributação | 2 | ✅ Completo |
| `0030` | Endereço do contribuinte | 10 | ✅ Completo |
| `0040` | Imóveis rurais | 17 | ✅ Completo (corrigido de 13) |
| `0045` | Contrapartes da exploração | 6 | ✅ Completo (corrigido de 4) |
| `0050` | Contas bancárias | 6 | ✅ Completo |
| `Q100` | Movimentações | 13 | ✅ Completo |
| `Q200` | Resumo mensal | 5 | ✅ Completo |
| `9999` | Encerramento | 2 | ✅ Completo |

### Correções aplicadas
- **`0040`**: era 13 campos com posições erradas → agora 17 na ordem oficial
- **`0045`**: faltavam `COD_IMOVEL`, `TIPO_CONTRAPARTE`, `PERC_CONTRAPARTE` → agora 6 campos
- **`0030`**: `COD_MUN` e `CEP` eram vazios → escrevem o que o produtor cadastrou

### Arquitetura
- `lcdpr_layout.linha(registo, *valores)` — **única** montadora, valida contagem contra `CAMPOS_POR_REGISTRO`
- `LCDPRExporter` — delega em `_formatar_valor` (duas casas implícitas, sem sinal/separador)
- `diagnosticar_lcdpr()` — valida antes de exportar, levanta `LCDPRDadosIncompletos`

---

## 2. O que NÃO tocar (decisões registradas)

| Item | Decisão | Razão |
|------|---------|-------|
| `PERC_CONTRAPARTE` | Fica vazio | Não existe campo no modelo para % de cada contraparte. `participacao` é do declarante. Deduzir "dividem o resto" seria inventar estrutura. |
| `cad_itr` na anonimização LGPD | Não apagar | Conflito real LGPD vs obrigação fiscal. Decisão não é técnica. |
| `exigir_talhoes` / `exigir_campos_fiscais` | Opcionais | Produtor no 1º ano pode não ter código. Recusar exportação não ajuda; ajuda ver o que falta. |

---

## 3. Limitações honestas (não verificadas)

| Lacuna | Status |
|--------|--------|
| Validador oficial da Receita | **Nunca rodou** — não há Java/JDK na máquina. Qualquer afirmação de "conforme" é falsa até alguém correr. |
| Regras de consistência entre registos | Enunciado dá estrutura; regras de validação cruzada são conjunto separado não transcrito. |
| `PERC_CONTRAPARTE` na prática | Sem caso real de parceria com % — só o enunciado. |

---

## 4. Guardas implementadas

| Ficheiro | O que impede |
|----------|--------------|
| `test_lcdpr_campos_fiscais.py` | Cadeia modelo → guarda → gerador → ficheiro, elo por elo |
| `test_lcdpr_conformidade.py` | Contagens dos 9 registos contra manual |
| `test_manifesto_confere_com_codigo.py` | Promessas do manifesto com `xfail(strict=True)` |

---

## 5. Como estender (padrão obrigatório)

```python
# SEMPRE use linha() — nunca monte string manual
from app.services.lcdpr_layout import linha

linha('0045', '001', '3', '12345678901', 'Maria Parceira', '')
# |0045|001|3|12345678901|Maria Parceira||
```

**Regra:** Um ficheiro com nomes divergentes para o mesmo campo é pior que um sem acento. Use nomes do manual sem acento (`COD_IMOVEL`, não `COD_IMÓVEL`).