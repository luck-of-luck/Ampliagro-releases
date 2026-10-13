# Ampliagro — Downloads

Repositório **público de releases**. Não contém código-fonte.

| O que é | Onde |
|---|---|
| Código-fonte (privado) | [luck-of-luck/Ampliagro](https://github.com/luck-of-luck/Ampliagro) |
| Downloads e instaladores (aqui) | [luck-of-luck/Ampliagro-releases](https://github.com/luck-of-luck/Ampliagro-releases) |
| Página de apresentação | <https://luck-of-luck.github.io/Ampliagro-releases/> |

## Por que dois repositórios

O código do Ampliagro é proprietário e fica privado. O que o utilizador
precisa — o instalador — é público, e o GitHub só serve ficheiros de release
de repositórios públicos a quem não tem conta. Daí a separação: o
auto-update do Electron lê `latest.yml` sem qualquer token, e o `.exe`
descarrega sem login.

O link de download aponta sempre para `releases/latest/download/…`, que o
GitHub redirecciona para a release mais recente. Não há versão no URL, por
que actualizar a release não obriga a mudar a landing page.

## Instalar

**Windows** — `Ampliagro-<versão>-x64.exe`. Instalador NSIS: instala em
`Program Files`, cria atalho no ambiente de trabalho e no menu Iniciar, e
regista a desinstalação em "Aplicações e funcionalidades".

**Windows (portátil)** — `Ampliagro-win-unpacked.zip`. Descompacta e corre
`Ampliagro.exe`. Não instala nada.

**macOS / Linux** — ainda em construção. Os alvos já estão configurados
(`.dmg`/`.pkg`, `AppImage`/`.deb`) e são construídos em runners CI dedicados.
A landing page mostra-os como "em breve" até existirem.

## Verificar a download

Cada release traz um `latest.yml` com o `sha512` do instalador. Para
confirmar que o ficheiro não foi trocado no caminho:

```powershell
Get-FileHash .\Ampliagro-0.1.0-x64.exe -Algorithm SHA512
```

O valor tem de bater com o `sha512` do `latest.yml` da mesma release.

## Problemas

Bugs e crashes: `suporte@ampliagro.com` (ver `RUNBOOK` no repositório
privado).
