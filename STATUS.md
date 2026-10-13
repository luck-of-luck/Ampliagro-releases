# Landing Page — Artefatos por Plataforma

## ✅ Windows — **PRONTO PARA PUBLICAR**

| Artefato | Tamanho | Localização | Tipo |
|---|---|---|---|
| `Ampliagro.exe` | 246 MB | `ampliagro-app/desktop/dist/win-unpacked/Ampliagro.exe` | Portable (standalone) |
| `ampliagro-desktop-0.1.0-x64.nsis.7z` | 28 MB | `ampliagro-app/desktop/dist/ampliagro-desktop-0.1.0-x64.nsis.7z` | NSIS archive (para installer futuro) |

**Status**: ✅ Funcionando — testado localmente, auto-atualizador configurado (canal stable/beta).

---

## ⏳ Linux — **REQUER RUNNER LINUX**

| Alvo | Status | Requisitos |
|---|---|---|
| AppImage (x64) | ❌ Não buildado | Ubuntu 22.04+ runner + `npm run dist:linux` |
| .deb (x64) | ❌ Não buildado | Ubuntu 22.04+ runner + `npm run dist:linux` |

**Comando**: `npm run dist:linux` (precisa `libwebkit2gtk-4.1-dev`, `libayatana-appindicator3-dev`, `patchelf`)

**Artefatos esperados**:
- `Ampliagro-0.1.0-x86_64.AppImage` (~300 MB)
- `ampliagro-desktop_0.1.0_amd64.deb` (~120 MB)

---

## ⏳ macOS — **REQUER RUNNER MACOS + XCODE**

| Alvo | Status | Requisitos |
|---|---|---|
| .dmg (Intel + ARM) | ❌ Não buildado | macOS 13+ runner + Xcode 15+ + certificado Developer ID |
| .pkg (Intel + ARM) | ❌ Não buildado | macOS 13+ runner + Xcode 15+ + certificado Developer ID Installer |

**Comando**: `npm run dist:mac` (precisa `CSC_IDENTITY_AUTO_DISCOVERY=true` + certificado válido)

**Artefatos esperados**:
- `Ampliagro-0.1.0-x64.dmg` / `Ampliagro-0.1.0-arm64.dmg` (~280 MB cada)
- `Ampliagro-0.1.0-x64.pkg` / `Ampliagro-0.1.0-arm64.pkg` (~150 MB cada)

**Notas**: Requer certificado Apple Developer ID (US$ 99/ano) para notarização e Gatekeeper. Sem certificado, o app não abrirá no macOS 13+ sem `--disable-gatekeeper`.

---

## 📦 Estrutura do Release no GitHub

Quando a tag `v0.1.0` for pushed, o workflow `.github/workflows/build-release.yml` gerará:

```
Releases/tag/v0.1.0/
├── Ampliagro-0.1.0-x64.exe              # Windows portable (246 MB)
├── ampliagro-desktop-0.1.0-x64.nsis.7z  # NSIS archive (para installer futuro)
├── Ampliagro-0.1.0-x86_64.AppImage      # Linux AppImage
├── ampliagro-desktop_0.1.0_amd64.deb    # Linux .deb
├── Ampliagro-0.1.0-x64.dmg              # macOS Intel
├── Ampliagro-0.1.0-arm64.dmg            # macOS Apple Silicon
├── Ampliagro-0.1.0-x64.pkg              # macOS Intel installer
├── Ampliagro-0.1.0-arm64.pkg            # macOS ARM installer
└── SHA256SUMS.txt                       # Checksums de todos arquivos
```

---

## 🚀 Próximos Passos para Landing Page Completa

1. **Windows** — ✅ Pronto. Subir `Ampliagro.exe` para `https://github.com/ampliagro/ampliagro-desktop/releases/latest/download/Ampliagro-0.1.0-x64.exe`

2. **Linux** — Rodar CI em runner Ubuntu:
   ```yaml
   runs-on: ubuntu-latest
   steps:
     - uses: actions/checkout@v4
     - run: cd ampliagro-app/desktop && npm ci && npm run build:all && npm run dist:linux
   ```

3. **macOS** — Rodar CI em runner macOS com certificado:
   ```yaml
   runs-on: macos-latest
   env:
     CSC_IDENTITY_AUTO_DISCOVERY: true
   steps:
     - uses: actions/checkout@v4
     - run: cd ampliagro-app/desktop && npm ci && npm run build:all && npm run dist:mac
   ```

4. **Deploy Landing Page** — Hospedar `landing.html` em:
   - GitHub Pages: `https://ampliagro.github.io/ampliagro-desktop/`
   - Ou Netlify/Vercel apontando para o repo

---

## 🔗 Links para o Landing Page (atualizar quando releases existirem)

| Plataforma | Link (placeholder) |
|---|---|
| Windows | `https://github.com/ampliagro/ampliagro-desktop/releases/latest/download/Ampliagro-0.1.0-x64.exe` |
| Linux AppImage | `https://github.com/ampliagro/ampliagro-desktop/releases/latest/download/Ampliagro-0.1.0-x86_64.AppImage` |
| Linux .deb | `https://github.com/ampliagro/ampliagro-desktop/releases/latest/download/ampliagro-desktop_0.1.0_amd64.deb` |
| macOS Intel .dmg | `https://github.com/ampliagro/ampliagro-desktop/releases/latest/download/Ampliagro-0.1.0-x64.dmg` |
| macOS ARM .dmg | `https://github.com/ampliagro/ampliagro-desktop/releases/latest/download/Ampliagro-0.1.0-arm64.dmg` |
| macOS Intel .pkg | `https://github.com/ampliagro/ampliagro-desktop/releases/latest/download/Ampliagro-0.1.0-x64.pkg` |
| macOS ARM .pkg | `https://github.com/ampliagro/ampliagro-desktop/releases/latest/download/Ampliagro-0.1.0-arm64.pkg` |

---

## ✅ Checklist para Go-Live

- [x] Windows portable buildado e testado
- [x] Landing page criada (`landing.html`)
- [x] Auto-atualizador configurado (stable/beta)
- [x] SHA256 checksums no release
- [ ] Linux build no CI (Ubuntu runner)
- [ ] macOS build no CI (macOS runner + certificado)
- [ ] Certificado Apple Developer ID renovado
- [ ] Landing page deployada (GitHub Pages / Netlify / Vercel)
- [ ] DNS `download.ampliagro.com` → landing page