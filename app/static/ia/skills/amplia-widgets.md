# AmplIA SKI - Widgets e presets
name: amplia-widgets
description: Consultar e organizar widgets persistidos do produtor, preservando configurações e confirmando alterações.
version: 1.0.0
triggers: ["widget", "preset", "dashboard", "painel", "mover", "configuração"]
handlers: ["preset_listar", "preset_editar", "preset_apagar", "widget_ler", "widget_alterar"]
performance: {cache: 0, flags: ["palco.read", "palco.write"]}

## Fluxo

- Consulte `preset_listar` para identificar os presets reais da conta.
- Consulte `widget_ler` com `preset` e, opcionalmente, `widget` (tipo real).
- Use `widget_alterar` com `operacao` igual a `editar`, `mover` ou `excluir`.
- Para editar, informe `titulo` e/ou `config`. Config mescla os parâmetros fornecidos com os atuais; não invente valores medidos.
- Para mover, informe `posicao` começando em 1 e, opcionalmente, `destino` para outro preset existente.
- Apresente a alteração solicitada e aguarde a confirmação do produtor. Nunca fabrique `confirm`.
- Não afirme sucesso se a ferramenta recusar a operação.

## Comandos locais no painel

- `liste widgets do preset "Custos"`
- `edite widget kpi-caixa do preset "Custos" título "Saldo disponível"`
- `mova widget kpi-caixa do preset "Custos" para preset "Financeiro" posição 1`
- `exclua widget kpi-caixa do preset "Custos"`

Os comandos explícitos são interpretados localmente sem baixar um modelo. As operações passam pelo sandbox e pelo catálogo MCP do sistema.
