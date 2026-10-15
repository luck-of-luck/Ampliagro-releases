# Landing page — estado e links

**Página pública:** <https://luck-of-luck.github.io/Ampliagro-releases/>

## Download na prévia local

Execute `python scripts/servir_landing.py` e abra `http://127.0.0.1:8088/landing.html`.
Em localhost, a página usa `/downloads/local.json` e entrega exclusivamente
`ampliagro-app/desktop/dist/Ampliagro-x64.exe`, com nome de download
`Ampliagro-Instalador-Novo-x64.exe`, tamanho real, SHA-256 e cache desabilitado.
O servidor mantém uma lista explícita de rotas e não publica o diretório do projeto.
Se faltar o executável, o botão fica indisponível; não retorna ao instalador antigo.
macOS/Linux ficam identificados como não compilados nesta prévia.

Isso não atualiza o GitHub: a página pública continua consultando a release publicada.
O executável local continua sem assinatura confiável; mudar o link não elimina
avisos de publicador desconhecido ou falhas de conexão do SmartScreen.

### Verificação do download local em 15/10/2026

- Passaram 12 testes da landing e 2 testes HTTP (download, SHA-256, HEAD e bloqueio de caminhos privados).
- Download real pela porta 8088: 183.900.998 bytes, SHA-256 `b8789224509dbcd74a49f845121a092722680c053cc064ecc3caf38870cb89bf`; botão também conferido em Chromium.
- Typecheck, Ruff dos arquivos Python alterados e ESLint do teste JS passaram.
- `npm test`: 311 passaram, 10 ignorados; falharam as suítes `clima_render.test.js` (fixture ausente) e `ia_rail_dom.test.js` (elemento inexistente). A etapa CJS desse comando não executou porque Vitest falhou.
- Lint geral: 704 erros fora desta correção. Prettier do HTML bloqueado por um fragmento SVG residual já existente junto ao favicon na linha 14; não alterado nesta correção de downloads. O teste JS foi formatado.

## Por que dois repositórios

| | Repositório | Visibilidade | Conteúdo |
|---|---|---|---|
| Fonte | `luck-of-luck/Ampliagro` | **privado** | Todo o código Django + Electron |
| Releases | `luck-of-luck/Ampliagro-releases` | **público** | Landing page + binários |

O GitHub só serve ficheiros de release de repositórios **públicos** a quem não
tem conta. Com o código e os binários no mesmo repositório privado, qualquer
visitante recebia 404 no link de download — que foi exactamente o que
aconteceu antes desta separação (MEDIDO em 13/10/2026: `releases.atom` e o
`.exe` devolviam 404 sem autenticação).

A consequência que obriga a esta divisão é o **auto-update**: o
`electron-updater` lê `latest.yml` a cada arranque e, num cliente de
consumidor, não tem token nenhum. O `publish` em
`ampliagro-app/desktop/package.json` aponta para o repo de releases por
isso.

## Links (publicos, sem login)

| Recurso | URL |
|---|---|
| Instalador Windows | `https://github.com/luck-of-luck/Ampliagro-releases/releases/latest/download/Ampliagro-x64.exe` |
| Portátil Windows (zip) | `https://github.com/luck-of-luck/Ampliagro-releases/releases/latest/download/Ampliagro-win-unpacked.zip` |
| Metadados de update | `https://github.com/luck-of-luck/Ampliagro-releases/releases/latest/download/latest.yml` |
| Feed do updater | `https://github.com/luck-of-luck/Ampliagro-releases/releases.atom` |

**Sem versão no URL.** O `artifactName` em `package.json` é
`${productName}-${arch}.${ext}`, e não `${productName}-${version}-…`. Publicar
uma release nova não obriga a tocar na landing page nem em nenhum link. O
hash `sha512` de cada instalador está no `latest.yml` da release.

## Estado por plataforma

| Plataforma | Artefacto | Estado |
|---|---|---|
| Windows | `.exe` (NSIS) | **Pronto e verificado** — instala, arranca, `/healthz` responde |
| Windows | `.zip` (portátil) | Ausente na release v0.1.1 consultada em 14/10/2026 |
| Windows | `.exe` (portable SFX) | **Não funciona** — bug de extracção 7z do electron-builder |
| Linux | `.AppImage` x64 | Publicado na release v0.1.1; execução não validada nesta revisão |
| Linux | `.deb` amd64 | Publicado na release v0.1.1; execução não validada nesta revisão |
| macOS | `.dmg` arm64 | Publicado na release v0.1.1; execução não validada nesta revisão |

## Publicar uma release nova

```powershell
cd ampliagro-app/desktop
npm run dist:win
gh release create v0.1.1 --repo luck-of-luck/Ampliagro-releases `
  --title "Ampliagro Desktop v0.1.1" --notes "..." `
  dist/Ampliagro-x64.exe dist/Ampliagro-x64.exe.blockmap dist/latest.yml
```

`latest.yml` **tem** de ser publicado. Sem ele o auto-update recebe 404 — e,
até ao commit que apanhou a rejeição não tratada, isso ainda produzia um
`UnhandledPromiseRejectionWarning` no arranque.

## Landing reformulada — 14/10/2026

A fonte da página pública é `landing.html`, um arquivo independente, sem build
ou dependências externas de imagem, fonte ou biblioteca. Para visualizar,
abra o arquivo no navegador ou execute `python -m http.server 8080` e acesse
`http://localhost:8080/landing.html`.

O conteúdo foi alinhado ao README, à visão de origem dos dados em
`docs/contexto-out-2026/VISAO.md`, ao inventário funcional em
`docs/atual/comparacao/01-inventario-ampliagro.md` e ao runbook do desktop.
Os exemplos são explicitamente ilustrativos e as limitações de recursos
locais, assistência e conectividade estão descritas nas perguntas frequentes.

A página consulta a API pública de releases do GitHub com limite de oito
segundos. Mostra apenas formatos reconhecidos publicados na última release
estável, com os tamanhos fornecidos pela API. Sem JavaScript, sem rede ou
sob limitação da API, os links para a release continuam disponíveis. Não há
instalação ou download iniciado automaticamente.

A consulta de 14/10/2026 confirmou os arquivos `.exe`, `.dmg`, `.AppImage`
e `.deb` em v0.1.1; não foi executado nenhum desses instaladores nesta revisão.
A publicação da página é separada: copiar `landing.html` como `index.html`
no repositório público de releases, seguindo seu processo de publicação.
Alterar este repositório privado não atualiza o GitHub Pages automaticamente.

## Identidade visual

A marca vetorial reutilizável está em `app/static/img/ampliagro-logo.svg`,
reconstruída a partir da referência fornecida pelo usuário. O SVG tem fundo
externo transparente, gradiente esmeralda e o monograma branco em paths.
A landing inclui o mesmo vetor no cabeçalho e rodapé.

A página segue os tokens de `app/static/css/ampliagro-global.css`: Sora para
os títulos, Inter no corpo, esmeralda e superfícies claras/carbono. Os
arquivos WOFF2 locais estão embutidos no HTML para manter a publicação em
arquivo único. O modo claro/escuro acompanha a preferência do navegador.
Os gradientes usam a paleta do dashboard e do login.

## Apresentação visual da rotina

A abertura contém uma demonstração esquemática navegável em três etapas:
planejar, registrar e acompanhar. Os exemplos não são capturas do aplicativo,
não gravam dados e não exibem números de desempenho. Um diagrama mostra os
vínculos entre propriedade, talhão, safra, atividades, insumos e custos.

O início de uso é apresentado em três passos, com chamada para baixar e
orientação de preservar os registros anteriores. A página não promete
importação ou migração automática, economia, aumento de produtividade nem
resultados garantidos. Os detalhes de requisitos permanecem nas perguntas
frequentes e nos cartões de download.

O vídeo indicado pelo usuário (YouTube, `EFmnPEtx04g`) teve o título acessível,
mas a obtenção das legendas retornou HTTP 429. Não houve análise do conteúdo
integral nem atribuição de técnicas específicas ao vídeo. A implementação
se baseia no produto documentado e no pedido de comunicação visual.

## Narrativa de insumos, atividades e planejamento

A landing foi reformulada para apresentar o Ampliagro no centro da operação,
com foco em acompanhar insumos, atividades e planejamento para apoiar o uso
consciente de recursos. Controle e custos completam a narrativa.

A demonstração contém três cenas: antes de comprar, antes de executar e
depois de registrar. Os links nos cartões de benefícios abrem a cena
correspondente. A representação é explicitamente esquemática e não envia
registros ao backend. Não contém recomendação de dose, economia projetada
ou garantia de aumento de produção.

Os gráficos de aprovações técnicas, a comparação genérica de concorrentes e
a faixa de testes foram retirados após a mudança de direção solicitada.
O teste da faixa foi substituído pela verificação de navegação entre as
cenas através dos cartões. Downloads, temas e perguntas frequentes continuam.
