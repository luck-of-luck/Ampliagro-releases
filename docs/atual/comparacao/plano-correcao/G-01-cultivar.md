# G-01 — Cultivar (ficha evento/ciclo/densidade)

## Por que existe (sem inventar)

`Cultura` (`core.py:19-65`) é espécie (Soja), não cultivar (TMG 7362 RR). `Safra.cultura` é PROTECT (`safra.py:51`) e o catálogo é partilhado sem dono (`perms.py:1-50`). Sem `Cultivar`, a safra não distingue material plantado — e a distinção produtor-afirmou vs sensor-mediu (VISAO §0.1) nem começa.

## Cirurgia (só backend)

1. Novo model `Cultivar` em `app/models/core.py` (ao lado de `Cultura`):
   - `cultura` FK PROTECT related `cultivares` (mesma razão de `safra.py:46-51`)
   - `nome_comercial` CharField(100), `obtentor` CharField(100, blank)
   - `evento` CharField(60, blank) — texto que o produtor leu no saco (RR2 PRO, Intacta, Convencional). Texto, não FK: sem tabela oficial semeada seria meta inventada.
   - `tecnica` choices [convencional, transgenia, edicao_genica, hibridacao], default convencional
   - `grupo_maturacao` Decimal(3,1, null), `ciclo_min`/`ciclo_max` Integer(null) — par min/max, nunca um número só (número só é meta)
   - `habito` choices [determinado, indeterminado, semideterminado, null]
   - `densidade_mil_plantas_ha` Decimal(6,1, null) — null, não 0 (0 plantas é mentira; sem_dado é ausência)
   - `tol_seca`/`tol_sal` choices [alta, media, baixa, null]
   - `resistencias` JSONField default list + `validate_json_safe`
   - `fonte_dado` CharField default `declarado` (regra VISAO §5.1-5)
   - Meta indexes: `[cultura, nome_comercial]`; ordering nome
2. `Safra.cultivar` FK `Cultivar` SET_NULL null/blank (`safra.py:36-51`): talhão sobrevive à cultivar como sobrevive à cultura (`tests_cascata_cultura.py:176-183` fixam SET_NULL p/ talhão). Não tocar em `Safra.cultura`.
3. Migration única. Semear: zero linhas. Catálogo começa vazio e honesto (VISAO §0.2: painel honesto começa vazio).
4. `CultivarSerializer` campos explícitos (padrão `CulturaSerializer`, `serializers.py:89-105`).
5. `CultivarViewSet` + permissão `LeituraGlobalEscritaStaff` (`perms.py:55`) — catálogo partilhado, mesma razão do `Cultura`.
6. Rota router em `app/api/urls.py` (padrão demais ViewSets). URL longa e sem colisão (lição `urls.py:346-354`).
7. `SafraSerializer`: expor `cultivar` + `cultivar_nome` read_only (padrão `cultura_nome`, `serializers.py:200-203`).

## O que NÃO entra

- Sem janela_plantio por UF na cultivar (ZARC é por cultura/município, `producao.py:379-400`; janela por cultivar sem fonte Embrapa seria número inventado — proibição VISAO §5.2-1).
- Sem tela, sem seed de cultivares, sem import de lista obtentora.

## Critério de saída (escrever no console.md ANTES de codar)

- POST cultivar com só `cultura`+`nome_comercial` passa; GET lista; PATCH não-staff dá 403; DELETE com safra vinculada dá ProtectedError e a safra continua existindo (espelho `tests_cascata_cultura.py:72-76`).
- `Safra` sem cultivar continua válida (campo null); `__str__` não mente cultivar ausente.
