# G-03 — EnsaioCultivar (repetição + testemunha + ranking)

## Por que existe (e por que não reusar Experimento)

`Experimento` (`producao.py:453-551`) é A/B genérico com `tratamento_a/b` JSON e `uid` cliente. Ensaio de cultivar exige N tratamentos × R repetições + testemunha identificada + ranking por produtividade — forçar isso em 2 JSONs seria esconder estrutura em blob (a mesma crítica que `dinamico.py` faz a schema-em-blob). Novo model normalizado, ligando `Cultivar` (G-01).

## Cirurgia

1. `EnsaioCultivar` em `app/models/producao.py` (ao lado de `Experimento`):
   - `uid` unique default uuid4 (convenção `producao.py:459`, `financeiro.py:209` — idempotência offline)
   - `user` FK, `propriedade` FK SET_NULL null (padrão `Experimento`), `safra` FK SET_NULL null, `talhao` FK SET_NULL null
   - `cultura` FK PROTECT (sexto PROTECT da família `tests_cascata_cultura.py:21-29` — estender a lista e o teste)
   - `testemunha` FK `Cultivar` PROTECT related `ensaios_testemunha`
   - `data_plantio` Date, `status` choices [ativo, concluido, arquivado] default ativo
   - `fonte_dado` default `declarado`
2. `FaixaEnsaio`:
   - `ensaio` FK CASCADE related `faixas`
   - `cultivar` FK PROTECT, `repeticao` PositiveInteger, `area_m2` Decimal(null)
   - `produtividade_sc_ha` Decimal(null — null, não 0), `umidade_pct` Decimal(null)
   - unique_together (ensaio, cultivar, repeticao)
   - `registada_em` DateTime (relógio do produtor, convenção `producao.py:618`) + `sincronizado_em` auto_now_add
3. Função pura `ranking_ensaio(faixas, testemunha_id)` em `app/services/` (pura = testável sem BD): média por cultivar, delta_pct vs testemunha; testemunha sem medição → delta None (não 0).
4. Serializer + ViewSet com escopo `propriedade__user` + action `ranking` read_only (GET detail) que chama a função pura.
5. Teste: ensaio sem faixas passa (sem_dado honesto); ranking com testemunha nula não inventa delta; duplicar POST com mesmo `uid` faz update_or_create (convenção `producao.py:435-438`).

## O que NÃO entra

- Sem `significance_level`/p-valor (número sem protocolo estatístico semeado = meta; comentário `producao.py:453-457` avisa do p-hacking).
- Sem análise automática de vencedor (recomendar cultivar sem repetição mínima é a "mesa invisível" de `chamado_intents.py`).

## Critério de saída

- N cultivares × R repetições gravam; ranking ordena por média; testemunha ausente → delta None em todas; `uid` repetido não duplica.
