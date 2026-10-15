DONA: IA-6
# IA-6 — Predador

**Slot:** `s6` · **Ramo:** `chore/snapshot-sistema-atual-20261004`
**Relatorio completo:** `console.md:831-1118` · **Fator:** correcao

## OS 5 ACHADOS CONFIRMADOS

| # | grav | onde | o que e' |
|---|---|---|---|
| 1 | **grave** | `servidor.py:196/239/275`, `operario.py:21` | `ativo_servidor` so e' verificado no dashboard (L76). As outras 4 rotas nao. Revogacao nao se propaga. |
| 2 | **grave** | `operario.py:68-112` | Renderizar a pagina grava 6 tarefas demo + `RegistroProducao` "Demo" na fazenda real. Sem gate de DEBUG. |
| 3 | medio | `operario.py:38-41` | `except Exception` concede `is_servidor=True, pode_criar=True`. |
| 4 | baixo | `cadastro.py:324` + `cadastro-funcionario.html:30` | Card "COM LOGIN" mostra `[]` — lista renderizada como escalar. |
| 5 | baixo | `_backups/` | Arvore recursiva de 250+ niveis. **Dormente** desde 26/07. |

**Conserto de 1:** mover o bloco `ativo_servidor` para dentro de
`_perfil_e_propriedade` (`servidor.py:22-36`) e para `kanban_allowed`
(`utils.py:65-90`). Fecha a causa raiz, nao o sintoma. O teste de
`tests_servidor.py:286` so cobre o dashboard — passa verde com a brecha.

## OS 3 RETRATOS (a parte que fica bem na nota)

1. **`.env` fora do `.gitignore`** — falso alarme meu. O teste combinava
   `[regex]::Escape()` com `-SimpleMatch`. Esta CORRETO (L17, L23, L172).
2. **Allowlist faltando** — nao e gap. `TIPO_USUARIO_CHOICES` tem 6 valores.
3. **`dashboard.py:153-154` usa `or 0`** — **eu estava errado**. Soma zero e'
   correto; `roi` e' razao e precisa de `None`.

## SINTOMA 1 — FECHADO COMO CORRETO

Contrato `sem_dado` vs `medido` existe ponta a ponta: `user.py:210/227/242/311`
e `index.html:4751/4974/4990/5012`. Os `0` do video sao KPIs de **soma**.
Confirma o que a IA-1 construiu por outro caminho.

## VERIFICADO E CORRETO (11)

`_next_seguro` · `_gerar_codigo` (`secrets`) · backdoor demo portado ·
`SECRET_KEY` levanta `ValueError` em prod · gunicorn no prod ·
`${VAR:?}` fail-fast · 4 validadores `min_length=8` · `validate_password`
explicito · `transaction.atomic` · `kanban_allowed` falha fechada ·
`.gitignore` coberto.

## O QUE NAO VERIFIQUEI

- **Nenhum scanner rodou** (astgrep: timeout). IDOR, CSRF, XSS: nao olhados.
- **Comite de 46 lentes offline.**
- Li 5 de ~30 views. **Nao afirmo nada sobre as outras ~25.**

## A SEGUIR

A maior lacuna: **as ~25 views de `app/views/` e `app/api/` que ninguem leu.**

## COLISAO

O achado 1 e' seguranca de tenant e o ramo `ia-b/tenant-seguranca` existe.
Coordinar antes de voltar a reportar.
