# 2. Inventário do Ampliagro (base auditada em 07/10/2026)

Levantamento direto de `app/models/*.py` + serializers + views + templates.

## 2.1 Núcleo fundiário e produtivo

| Entidade (código) | Arquivo | Campos-chave |
|---|---|---|
| `Propriedade` | `core.py` | nome, area_total, uf, cidade, endereco, bioma, pais, moeda, culturas M2M, cadastro_fiscal JSON (LCDPR) |
| `Talhao` + `TalhaoGeometria` | `core.py` | nome, área; geojson Polygon/MultiPolygon, area_calculada_ha, centroide lat/lon |
| `AnaliseSolo` | `core.py` | data_coleta, pH, P, K, Ca, Mg, Al, MO, CTC, V%, laboratório |
| `AreaPreservacao` | `core.py` | tipo APP/RL/OUTRO, área, geojson |
| `Cultura` | `core.py` | nome, grupo (20), unidade_comercial, janela_plantio, chave_mercado, ibge_codigo, ciclo_dias |
| `Safra` + `SafraTalhao` | `safra.py` | cultura PROTECT, ano, áreas plantada/colhida, produção, produtividade, receita, datas; rateio multi-talhão |
| `PlanoSafra` + `AtividadePlanejada` | `safra.py` | orçamento, status; atividade: nome, data, custo, responsável, cargo_alvo, setor, funcionário |
| `RegistroProducao` + `EstagioCultura` + `TarefaEstagio` | `producao.py` | cultura, status, local, qtd, fields_json; estágio ordem/cor/ícone/datas; tarefa responsável/prioridade/limite |
| `NotaCampo` + `FotoNota` | `caderno.py` | tipo (9 fixos), conteúdo, fonte_dado=declarado, lat/lon 11,7, registada_em, offline_id, foto georreferenciada |

## 2.2 Insumos, estoque e rastreabilidade

| Entidade | Campos-chave |
|---|---|
| `Insumo` (`safra.py`) | categoria (9), nome, qtd, unidade, valor_unit, estoque_minimo |
| `AplicacaoInsumo` | insumo, talhão, data, dose |
| `ReceituarioAgronomico` | ART, diagnóstico, praga, foto, lat/lon, prescricao JSON |
| `EstoqueItem` + `MovimentacaoEstoque` (`estoque.py`) | categoria (7), qtd min/max, validade; mov tipo entrada/saída/transf/ajuste, lote, NF, responsável |
| `OrdemCompra` + `Inventario` | fornecedor, status (5), total; contagem física × sistema |
| `RastroItem` (`rastreabilidade.py`) | lote fabricante, NF, qtd, validade, fornecedor, qr_code_hash, saldo calculado, vencido |
| `MovimentoEstoque` | ledger append-only |
| `RastreabilidadeSafra` | safra + aplicação/insumo/lote + talhão + custo snapshot + operação + data |
| `MonitoramentoPraga` (`mip.py`) | talhão, data, praga, nível_infestação, nível_controle, ação, foto |
| `PrescricaoVRA` + `Experimento` + `MedicaoExperimental` | taxa variável; ensaio A/B com contexto clima/solo e fonte_dado |
| `ZARC` | janela por município/cultura |
