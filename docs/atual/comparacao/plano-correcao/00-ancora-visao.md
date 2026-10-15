# Plano-correção backend — G-01 a G-06 (sementes)

> Analogia VISAO.md §5: critério de saída antes de codar; uma fase por vez; toda escrita declara `fonte_dado`; sem número inventado; scanner antes de cada fase.
> Escopo deste plano: **só backend** (model + migration + serializer + viewset + permissão + teste). Sem template, sem mapa novo, sem widget (Fase 1 proíbe superfície nova).

## FASE 0 — pré-requisito (não pular)

| Item | Âncora | Critério de saída |
|---|---|---|
| `operario.py:68-112` sem escrita fantasma | VISAO §1 grave | GET sem tarefas cria 0 linhas (teste conta antes/depois) |
| Revogação propaga em `/servidor/` | `tests_servidor.py:286` | itera todas as rotas, não só dashboard |
| Scanner | VISAO §5.1-4 | `sast`+`semgrep`+`astgrep` colados no console.md |

## Regra de escrita (vale p/ G-01..G-06)

- Todo model novo com escrita do produtor ganha `fonte_dado` com `ESTADOS_FONTE` de `app/validators.py:17-23`. Default `declarado` (produtor afirmou, não mediu).
- `null` onde é razão, `0` onde é soma (contrato s1/s2, `user.py:297`).
- Catálogo partilhado sem dono (`Cultura`, futuro `Cultivar`) usa `LeituraGlobalEscritaStaff` (`app/api/perms.py:55`): GET+POST autenticado, PUT/PATCH/DELETE staff.
- Dado por-propriedade usa filtro `propriedade__user=request.user` (padrão `RastroItemViewSet`, `rastreabilidade.py:62-65`) e `get_queryset_optimizado` (`hierarquia.py:439`).
- `on_delete=PROTECT` em toda FK para catálogo que sustenta safra (`safra.py:46-51`, `tests_cascata_cultura.py`).
