# Landing page — estado e links

**Página pública:** <https://luck-of-luck.github.io/Ampliagro-releases/>

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
| Windows | `.zip` (portátil) | Pronto e verificado |
| Windows | `.exe` (portable SFX) | **Não funciona** — bug de extracção 7z do electron-builder |
| Linux | `.AppImage` | Alvo configurado; falta runner Ubuntu |
| Linux | `.deb` | Alvo configurado; falta runner Ubuntu |
| macOS | `.dmg` / `.pkg` (x64 + arm64) | Alvo configurado; falta runner macOS |

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
