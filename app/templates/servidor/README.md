# Servidor — dashboards por área (hierarquia 30-80)

Cada servidor tem `PerfilUsuario.area_servidor`
(`MECANICA`/`CAMPO`/`PECUARIA`/`ESTOQUE`/`AGRONOMIA`/`ADMIN`/`FINANCEIRO`/`GERAL`)
e `permissoes` (JSONField) que o produtor controla. O produtor define o que o
servidor vê; o servidor nunca amplia a própria permissão.

## Páginas

| URL | View | Bloqueio |
|---|---|---|
| `/servidor/` | `servidor_dashboard_view` | `servidor-dashboard` |
| `/servidor/estoque/` | `servidor_estoque_view` | `servidor-estoque` |
| `/servidor/agenda/` | `servidor_agenda_view` | `servidor-agenda` |
| `/servidor/alertas/` | `servidor_alertas_view` | `servidor-alertas` |
| `/servidor/kanban/` | `operario_kanban_view` (compartilhada) | hierarquia filtra |
| `/api/servidor/config/` | `servidor_config_api` | JSON de permissões |

`dashboard.html` é estático; `servidor.js` lê `/api/servidor/config/` e mostra
só as seções cujo `data-pagina` está em `cfg.paginas`. Navbar própria em
`partials/navbars/navbar_servidor.html`.

## Como "de qual fazenda eu sou" é resolvido

Único ponto de verdade: `_perfil_e_propriedade()` em `app/views/servidor.py`.
Ordem de resolução:

1. `perfil.propriedade_vinculada` (o produtor vincula explicitamente)
2. `perfil.funcionario.propriedade` (herdado do cadastro de funcionário)
3. `None` → páginas renderizam vazias, sem quebrar (há teste para isso)

Não replicar essa lógica em view nova — use o helper. Cada cópia já divergiu
uma vez: o dashboard e a agenda filtravam tarefas por caminhos diferentes.

## Regras por tela

- **estoque** — só `MECANICA`/`ESTOQUE`/`ADMIN`/`GERAL`; `MECANICA` vê apenas
  `categoria` em `PECA`/`FERRAMENTA`. others caem em `assert_hierarquia` (403).
- **agenda** — fora de `GERAL`, filtra por `cargo_alvo`/`setor` da área + as
  tarefas atribuídas ao próprio usuário.
- **alertas** — `MECANICA` vê `temp_motor`/`combustivel`/`bateria`/`nivel`/
  `offline`; `CAMPO` vê `umidade_solo`/`chuva`/`temperatura`/`chuva_acum`.
- **desativado** — `ativo_servidor=False` faz logout e mostra a tela de login
  com "Servidor desativado pelo produtor".

## armadilhas conhecidas

- **Nunca emita `permissoes` com `|safe` dentro de `<script>`.** É JSONField
  editável pelo produtor: um `"</script>` no `titulo` fecha a tag e executa JS
  na sessão do servidor. Use `{{ config|json_script:"id" }}` e
  `JSON.parse(el.textContent)`. Há teste em `app/tests_servidor.py`.
- **Comentário `{# ... #}` de várias linhas vaza como texto na página.** O lexer
  do Django não aplica `re.DOTALL`. Use `<!-- -->` ou comentário de linha
  única. Guarda em `app/tests_templates.py`.
- **Nomes de arquivo dentro de `templates/` não são servidos** — este README é
  documentação para quem maintainar, não conteúdo de página.

## Testes

```bash
manage.py test app.tests_servidor app.tests_templates
```

Cobertura: lincagem de propriedade, bloqueio por área, navbar por área,
servidor sem vínculo, servidor desativado, XSS em `permissoes`, paridade
dashboard↔agenda e não-vazamento entre fazendas.
