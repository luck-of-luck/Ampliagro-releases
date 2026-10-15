# Ampliagro Mobile (React Native)

## Visão geral

App móvel **Android** (React Native 0.87.1) que consome a API Django existente
em `/api/*` e expõe 5 abas mais a tela de login:

| Aba        | Endpoints do backend                                       |
| ---------- | ---------------------------------------------------------- |
| Painel     | `/api/dashboard/`                                          |
| Talhões    | `/api/talhoes/`                                            |
| Safras     | `/api/safras/`                                             |
| Estoque    | `/api/estoque/`                                            |
| Clima      | `/api/previsao-clima/`                                     |

## Requisitos

- Node.js LTS (v22+)
- JDK 17 (Temurin) — este projeto inclui um atalho `build-apk.ps1` que usa o JDK
  instalado em `C:\Users\lucas\AppData\Local\AmpliagroTools\jdk17`.
- Android SDK em `%LOCALAPPDATA%\Android\Sdk` (build-tools 36.0.0 e
  `platforms;android-36` já estão instalados).
- Emulador Android (API 33+, ex.: Pixel 5) ou dispositivo físico com acesso ao
  servidor Django.

## Instalação / execução

```powershell
cd Ampliagro_app_cell
npm install
# sem dispositivo conectado, inicia um emulador automaticamente:
npx react-native run-android
```

## APK debug (entrega pronta)

- Caminho: `Ampliagro_app_cell\android\app\build\outputs\apk\debug\app-debug.apk`
- Package: `com.ampliagrocell` · version `1.0` · ~117 MB (4 ABIs)

Instalar em dispositivo físico:

```powershell
adb install android\app\build\outputs\apk\debug\app-debug.apk
```

## Login / Autenticação

O backend usa **Django SessionAuthentication** (não token). O cliente faz o
`csrf cookie dance`:

1. `GET /login/` → captura cookie `csrftoken` do header `set-cookie`.
2. `POST /login/` (form‑urlencoded) com `X-CSRFToken` + `X-Requested-With` e
   `credentials: 'include'` → mantém cookie de sessão `sessionid`.

**Demo** — o app traz um botão “Entrar como demonstração” que chama `GET /demo/`
e abre a sessão demo do próprio Django (`app.views.auth.py::demo_login_view`),
útil para testes sem credenciais.

> Para produção, troque `android.usesCleartextTraffic=true` em
> `android/gradle.properties` para `false` e sirva o Django sobre HTTPS.

## APK release (assinado)

Na máquina onde foi feito o build debug (`newArchEnabled=false`):

1. O keystore já foi gerado: `ampliagro_app_cell/android/ampliagro-release.keystore`
   (CN=Ampliagro, alias `ampliagro`, RSA 2048, válido 10 000 dias).
2. Está configurado em `android/app/build.gradle` → `signingConfigs.release`.
3. Build:

```powershell
# ATENÇÃO: o build release falha com erro de CMake (>260 chars de caminho) se
# o projeto estiver em um caminho grande como este. Copie para um caminho curto:
#   C:\src\AmpliagroApp
cd C:\src\AmpliagroApp\android
.\gradlew.bat :app:assembleRelease --no-daemon
```

APK de release → `android/app/build/outputs/apk/release/app-release.apk`.

## iOS — não é possível buildar a partir do Windows

Gerar um `.ipa` exige **Xcode + macOS** (Swift/Xcode não roda no Windows).
O código React Native é compatível; basta abrir o projeto iOS gerado por
`npx react-native init` num Mac e publicar via App Store Connect.

## Estrutura de arquivos novos

```
src/
  api.ts            # cliente HTTP: CSRF, sessão, login/logout, fetchers
  tipos.ts          # tipos das respostas da API Django
  tema.ts           # cores, formatadores (número, moeda, data, nível de alerta)
  componentes.tsx   # Cartão, Indicador, Linha, Carregando, Aviso, Vazio
  useRecurso.ts     # hook de carregamento com retry
  telas/
    Login.tsx
    Painel.tsx
    Talhoes.tsx
    Safras.tsx
    Estoque.tsx
    Clima.tsx
App.tsx             # navegaçāo por abas + estado de sessão
build-apk.ps1       # atalho para build debug com JDK/SDK configurados
```

## Debug de build

Se o Gradle não achar o JDK/SDK, rode `build-apk.ps1` que exporta
`JAVA_HOME` e `ANDROID_HOME` corretamente.
