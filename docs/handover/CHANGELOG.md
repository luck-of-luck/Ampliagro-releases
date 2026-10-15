# Changelog

Todas as mudanças notáveis neste projecto serão documentadas neste ficheiro.

O formato baseia-se em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projecto adere a [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [Não publicado]

### Alterado

- Motor proativo cruza sensores recentes fora dos limites configurados com a previsão da propriedade. Leituras antigas ou de qualidade inadequada não geram propostas; pH gera um plano de verificação com dados faltantes, sem inventar dose ou acionar equipamentos.

- Landing local oferece o instalador Windows gerado no computador, com nome distinto e sem voltar automaticamente ao arquivo antigo do GitHub. O download informa a ausência de assinatura confiável; plataformas ainda não recompiladas ficam indisponíveis na prévia.

- Instalador Windows abre o assistente visual do Ampliagro após copiar os arquivos em segundo plano, substituindo as telas padrão do NSIS. Reinstalações manuais voltam ao aceite e preservam as culturas selecionadas; instalações silenciosas continuam sem interação.

- Desktop com assistente de primeira abertura na identidade visual do Ampliagro: aceite da licença, escolha do modo e culturas do catálogo real. A seleção local é reutilizada no cadastro; o modo web permanece indisponível sem URL configurada. Perfis selecionados são preparados localmente, sem download remoto de packs nesta etapa.

- Ícone das abas unificado com a logo vetorial do Ampliagro nos templates do sistema, administração, contas, landing e instalador.

- Landing centrada no uso de insumos, planejamento de atividades e acompanhamento de custos, com demonstração interativa e identidade visual do Ampliagro.

- Landing com demonstração visual interativa da rotina, diagrama dos vínculos e passos de adoção; exemplos identificados como ilustrativos.

- Landing pública reformulada com apresentação da gestão rural, exemplos de origem dos dados, orientação de início e perguntas frequentes acessíveis.
- Downloads exibem formatos e tamanhos consultados na release pública, com links alternativos em caso de falha de conexão; o `.exe` Windows é identificado como instalador.

## [0.1.0] - 2026-10-12

### Adicionado
- **Fase 0** — Fundações: Electron + Django embed, runtime congelado (PyInstaller onedir), Job Object / `PR_SET_PDEATHSIG`, health-check `/healthz`, WebSocket 101.
- **Fase 1** — Runtime offline real: `bootstrap.py`, `congelar.py`, `entrypoint.py`, `electron/main.js`/`preload.js`, testes de janela/encerramento/congelado.
- **Fase 2** — Vendorizar 47 URLs: `inventario_cdn.py`, `vendorizar.py` (SHA256 + verificação CSS `url()`), `reescrever_cdn.py` (15 templates + `login.css`, Chart.js 4.4.7 unificado), CSP `local-only`, gate offline (`gate-offline.cjs` com Chromium), 4 fundos Unsplash descobertos e vendorizados.
- **Fase 3** — Sistema de Planos: `PlanoSafraNovo`, `AtividadePlanejadaNova`, `CustoOperacao` (MAO_DE_OBRA, COMBUSTIVEL, INSUMO, DEPRECIACAO, SERVICO_TERCEIRO, OUTRO + roll-up por mês/zona/categoria), `ZonaManejo`, `CustoAtividade`, `CenarioPlano` (margem/ponto de equilíbrio), `ComparativoOrcadoRealizado`. Migração de dados `0086_fase3_migra_dados_planos`.
- **Fase 4** — Sistema de Máquinas: `Maquina` (OneToOne `Maquinario` + `Device` nullable, propriedades telemetria), `Manutencao` (PREVENTIVA/CORRETIVA/PREDITIVA + gatilho), `CustoMaquina` (gerado da telemetria real: litros/horas/custo-hora). Migração `0089_fase4_migra_maquinario`.
- **Fase 5** — Packs por cultura: `manifest.json` (488 culturas, 25 subgrupos, 4 grupos), 25 packs `.js` em `static/packs/`, `core.js` (registry + API), `pack-loader.js` (download sob demanda, cache localStorage), `pack-wizard.js` (modal 1º arranque), `pack-updater.js` (check periódico, fallback cloud), `pack-wizard.css`.
- **Fase 6** — Empacotamento Windows portable: `electron-builder` target `portable` (evita bug NSIS), `Ampliagro.exe` 246 MB, runtime PyInstaller onedir 127 MB, `staticfiles/` + `packs/` incluídos, `electron-updater` com canal `stable`/`beta`, CI GitHub Actions 3 runners (Win/mac/Linux).
- **Fase 7** — Handover: docs reorganizadas (`docs/arquitetura`, `docs/guias`, `docs/handover`, `docs/legacy`), `CHANGELOG.md`, `RUNBOOK.md` (crash-report, voltar ao modo web, backup SQLite).

### Corrigido
- CSP desktop `local-only` bloqueia pedidos externos (incl. Open-Meteo, OSM, Hugging Face, esm.run).
- SRI falso-positivo: comparação hex vs base64 corrigida; atributos estavam correctos.
- `$n$nUse` em NSIS corrigido para `$\n$\nUse`.
- `device` nullable em `Maquina` (nem todo maquinário tem rastreador).
- `preconnect` Google Fonts mantido (inofensivo, não descarrega nada).
- `staticfiles` path corrigido para `../../staticfiles` no `extraResources`.
- Ícones placeholder removidos (electron-builder usa padrão).

### Segurança
- CSP `desktop` apenas `self` + `ws://127.0.0.1` + `http://127.0.0.1`.
- `CLIMA_CACHE_DIR` fora de `MEDIA_ROOT` (não servido publicamente).
- `electron-updater` com `autoDownload: false` (pergunta antes de baixar).

## [0.0.1] - 2026-10-01

### Adicionado
- Estrutura inicial do projecto Ampliagro 2.0.
- Django app `app/` com modelos core, safra, financeiro, IoT, IA.
- Configuração base Django (`config/settings/base.py`).
- Electron `main.js`/`preload.js` base.
- Documentação inicial em `docs/`.
