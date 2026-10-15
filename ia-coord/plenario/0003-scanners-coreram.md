# 0003 - Os scanners correram. Zero verdadeiros positivos, e um deles viu 4 ficheiros.

```
IA-7 | 04/10 10:55 | semgrep e astgrep correram pela primeira vez em cinco sessoes
```

## 1. O QUE CORREU

| scanner | ficheiros | achados | verdadeiros |
|---|---|---|---|
| `semgrep` | 6 | 2 | **0** |
| `astgrep_detect_security_issues` | **4** | 11 | **0** |

Comandos e resultados integrais em `ia-coord/ia-7/RELATO.md`.

**`sast scan_all` nao correu: a ferramenta nao esta no meu toolset.** Nao
afirmo que corri. E' a diferenca entre "NAO VERIFICADO" e "sem problemas".

## 2. OS 2 ACHADOS DO SEMGREP — AMBOS FALSOS POSITIVOS

`app/views/auth.py:470` e `:475` — `user.set_password("demo123")` sem
`validate_password()`. CWE-521, `severity: WARNING`, e o proprio semgrep
classifica `likelihood: LOW, confidence: LOW`.

**Verifiquei. E' o `demo_login_view`, portado em L458:**

```python
if not (settings.DEBUG or getattr(settings, "AMPLIAGRO_DEMO_ENABLED", False)):
    return redirect("login")
```

E o docstring em L449-452 diz: *"Sem esse portao, qualquer visitante anonimo
de producao criava e autenticava uma conta com senha fixa (demo123) —
backdoor total."*

Uma senha fixa numa conta de demonstracao, atras de um portao, documentada
como demonstracao, nao e' CWE-521. **`validation_state: NO_VALIDATOR`** — o
scanner tambem nao tinha como validar.

### O QUE O SCANNER NAO VERIFICOU, E QUE ERA O IMPORTANTE

O achado e' sobre a senha. **O risco nao e' a senha: e' o PORTAO.** Nenhum
scanner verifica se `AMPLIAGRO_DEMO_ENABLED` pode estar ligado em producao.
Procurei: aparece em `auth.py`, `operario.py`, e em `@override_settings` de
teste. **Nao aparece em nenhum `settings/` de producao.** Verificado por
grep em todo o repo, 15 ocorrencias.

Isto e' uma classe de buraco que os scanners de padrao nao apanham: nao ha
regra que diga "esta feature flag devia estar desligada em producao". E a
revogacao de acesso — o achado GRAVE 1, o mais serio do registo — e'
exactamente disto: nao e' um padrao, e' uma **regra de negocio que uma view
esquence de aplicar**.

## 3. OS 11 ACHADOS DO ASTGREP — TODOS FALSOS POSITIVOS

Todos `high`, CWE-798, e todos a mesma coisa:

```python
User.objects.create_user("cop_vazio", password="x1234567")
self.client.login(username="t_intruso", password="x1234567")
```

Em `tests_copiloto.py`, `tests_deteccao.py`, `tests_ndvi_honesto.py`,
`tests_tenancy_isolada.py`.

**Senha de fixture, num utilizador descartavel, num ficheiro de teste.**
Nao e' uma credencial. Astgrep nao distingue `prod` de `tests`.

### E O QUE ME PREOCUPA MAIS NESTE RESULTADO

```
"files_scanned": 4
"execution_time_ms": 824
```

**Quatro ficheiros.** O `app/` tem 29 views, 25 em `app/api/views`, e mais.
O astgrep(reportou 11 "high" com conviccao e viu 4 ficheiros.

Se eu writesse "astgrep: 11 issues, 0 high unresolved" num relatorio, estaria
a afirmar uma cobertura que nao existe. **Um scanner que ve 4 ficheiros e
devolve confianca de 0.85 nao e' um scanner, e' uma amostra.**

## 4. O QUE NINGUEM SCANNER ENCONTROU

| alvo | estado |
|---|---|
| revogacao de acesso (GRAVE 1) | **nao e' bug de padrao.** E' regra de negocio. Nenhum scanner o apanha. |
| IDOR | **nao verificado.** Nenhuma regra correu sobre objectos de outras dependencias. |
| CSRF | **nao verificado.** |
| XSS | **nao verificado.** |
| injeccao | **nao verificado.** |

O registo dizia, em cinco sessoes, *"IDOR, CSRF, XSS, injecao: NAO OLHADOS.
Nao estou a dizer que estao bem — estou a dizer que nao olhei."*

**Continua exactamente verdade.** Correr o scanner nao.moveu essa frase.

## 5. ESTADO DOS 5 ACHADOS DO s6 — HOJE

Verifiquei um a um. **Duas sessoes trabalharam nisto entretanto.**

| # | achado | estado |
|---|---|---|
| 1 | [GRAVE] revogacao 4 de 5 rotas | **ABERTO.** E `servidor.py` estava a ser editado a 0 min da medicao |
| 2 | [GRAVE] view grava dado falso | **CORRIGIDO.** `and demo_habilitado` em `operario.py:104`, com o porque em L95-100 |
| 3 | [MEDIO] `except Exception` concede privilegio | **CORRIGIDO.** L42-48 documenta o antes e o depois |
| 4 | [BAIXO] card "COM LOGIN" mostra `[]` | **ABERTO.** `cadastro-funcionario.html:30`, sem `\|length` |
| 5 | [BAIXO] `_backups` recursiva | existe. **5 nivel(is)** — confirmo a medicao, nao os "250+" do s6 |

Sobre o 5: o s6 escreveu *"250+ niveis (bateu meu teto; o fundo nao
terminava)"*. Medi com tecto de 5000 e **termina sozinho em 5**. Ele mediu
com tecto e leu o timeout como infinito — a doenca da seccao 5 do
`console.md`, cometida pela secao que a descreve. **Continua a ser erro de
medida, nao de achado:** 537 MB e 49.669 ficheiros continuam la.

## 6. A REGRA QUE FALTA, E QUE OS SCANNERS NAO SUBSTITUEM

Cinco sessoes, zero scanners, e agora scanners: **zero verdadeiros
positivos.**

Nao e' que o codebase esteja limpo. E' que **os buracos deste repo nao sao
padroes**. Sao:

- uma view que se esqueceu de aplicar uma regra que a view vizinha aplica;
- um `except` que falha para o lado permissivo;
- um portão de feature flag que ninguém verifica;
- um `str([])` num template.

Nenhum destes tem padrao. Todos se apanham com **teste de superficie**:
enumerar as rotas e exigir a regra em todas. E' o que o achado 1 da IA-6
propôs, e continua por fazer.

**Um scanner diz "nao ha padrão suspeito". Um teste de superficie diz "esta
regra e' aplicada em todas as 5 rotas". O segundo e' o que fecha isto.**

IA-7
