; Custom NSIS Installer Script for Ampliagro
; Extends the default electron-builder NSIS installer with custom pages

!include "LogicLib.nsh"
!include "nsDialogs.nsh"
!include "MUI2.nsh"
!include "WinMessages.nsh"
!include "FileFunc.nsh"

;--------------------------------
; Variables for custom pages
Var Dialog
Var ExportChoice ; 0 = Local, 1 = Cloud
Var CropSection
Var CropItems
Var AcceptTerms
Var LogoHandle

;--------------------------------
; Custom pages configuration
!define MUI_CUSTOMFUNCTION_PRE un.onInit
!define MUI_FINISHPAGE_NOAUTOCLOSE

; Add custom pages after license page, before install page
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "${NSISDIR}\Contrib\License.rtf"
Page Custom pageBancoDadosCreate pageBancoDadosLeave
Page Custom pageCulturasCreate pageCulturasLeave
Page Custom pageDownloadCreate pageDownloadLeave
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

;--------------------------------
; Banco de Dados Page - Database export choice
Function pageBancoDadosCreate
  nsDialogs::Create 1018
  Pop $Dialog

  ${If} $Dialog == error
    Abort
  ${EndIf}

  ; Header label
  ${NSD_CreateLabel} 20 15 100% 25u "Banco de Dados"
  Pop $0
  ${NSD_SetFont} $0 ${FONT_BOLD} 14

  ; Export choice group box
  ${NSD_CreateGroupBox} 20 50 460 200u "Como deseja exportar seus dados?"
  Pop $0

  ; Radio: Local storage
  ${NSD_CreateRadioButton} 40 75 420 18u "Salvar localmente na sua máquina (~2 GB de armazenamento necessário)"
  Pop $ExportChoice
  ${NSD_SetState} $ExportChoice ${BST_CHECKED}

  ; Radio: Cloud export
  ${NSD_CreateRadioButton} 40 100 420 18u "Exportar para o servidor na nuvem (servidor sempre ligado para atualizações em tempo real pelos funcionários e IoT na propriedade)"
  Pop $1

  ; Info text for local option
  ${NSD_CreateLabel} 40 125 420 55u "Aviso de Segurança: Dados locais ficam protegidos pelo sistema operacional da sua máquina. Este é um ambiente de uso interno - os dados devem ser tratados com responsabilidade. O servidor Python deve estar sempre ativo para servir os funcionários e dispositivos IoT na propriedade."
  Pop $0
  ${NSD_SetFont} $0 ${FONT_NORMAL} 9

  ; Info text for cloud option
  ${NSD_CreateLabel} 40 185 420 35u "Nuvem: Dados criptografados enviados para servidor seguro. Requer conectividade constante. O servidor deve estar SEMPRE LIGADO para atualizações em tempo real."
  Pop $0
  ${NSD_SetFont} $0 ${FONT_NORMAL} 9
FunctionEnd

Function pageBancoDadosLeave
  ; Read export choice
  ${NSD_GetState} $ExportChoice $0
  ${If} $0 == ${BST_CHECKED}
    StrCpy $ExportChoice 0 ; Local
  ${Else}
    StrCpy $ExportChoice 1 ; Cloud
  ${EndIf}
FunctionEnd

;--------------------------------
; Culturas Page - Crop selection with categories
Function pageCulturasCreate
  nsDialogs::Create 1018
  Pop $Dialog

  ${If} $Dialog == error
    Abort
  ${EndIf}

  ; Header label
  ${NSD_CreateLabel} 20 15 100% 25u "Culturas"
  Pop $0
  ${NSD_SetFont} $0 ${FONT_BOLD} 14

  ; Instruction text
  ${NSD_CreateLabel} 20 45 460 20u "Selecione as culturas (organizadas por categoria). Você pode digitar ou usar áudio para selecionar:"
  Pop $0

  ; Group box for crop selection
  ${NSD_CreateGroupBox} 20 70 460 240u "Culturas Disponíveis"
  Pop $0

  ; Category: VEGETAL > GRAOS
  ${NSD_CreateLabel} 40 90 420 18u "VEGETAL > GRAOS"
  Pop $0
  ${NSD_SetFont} $0 ${FONT_BOLD} 9

  ${NSD_CreateCheckBox} 40 110 120 18u "Café"
  Pop $1
  ${NSD_CreateCheckBox} 160 110 120 18u "Arroz"
  Pop $2
  ${NSD_CreateCheckBox} 280 110 120 18u "Soja"
  Pop $3
  ${NSD_CreateCheckBox} 400 110 100 18u "Milho"
  Pop $4

  ; Category: VEGETAL > LEGUMINOSAS
  ${NSD_CreateLabel} 40 135 420 18u "VEGETAL > LEGUMINOSAS"
  Pop $0
  ${NSD_SetFont} $0 ${FONT_BOLD} 9

  ${NSD_CreateCheckBox} 40 155 120 18u "Feijão"
  Pop $5
  ${NSD_CreateCheckBox} 160 155 120 18u "Ervão"
  Pop $6
  ${NSD_CreateCheckBox} 280 155 120 18u "Soja"
  Pop $7
  ${NSD_CreateCheckBox} 400 155 100 18u "Grão-de-bico"
  Pop $8

  ; Category: HORTALIÇAS
  ${NSD_CreateLabel} 40 180 420 18u "HORTALIÇAS"
  Pop $0
  ${NSD_SetFont} $0 ${FONT_BOLD} 9

  ${NSD_CreateCheckBox} 40 200 120 18u "Alface"
  Pop $9
  ${NSD_CreateCheckBox} 160 200 120 18u "Tomate"
  Pop $10
  ${NSD_CreateCheckBox} 280 200 120 18u "Cenoura"
  Pop $11
  ${NSD_CreateCheckBox} 400 200 100 18u "Pepino"
  Pop $12

  ; Category: FRUTAS
  ${NSD_CreateLabel} 40 225 420 18u "FRUTAS"
  Pop $0
  ${NSD_SetFont} $0 ${FONT_BOLD} 9

  ${NSD_CreateCheckBox} 40 245 120 18u "Laranja"
  Pop $13
  ${NSD_CreateCheckBox} 160 245 120 18u "Maçã"
  Pop $14
  ${NSD_CreateCheckBox} 280 245 120 18u "Uva"
  Pop $15
  ${NSD_CreateCheckBox} 400 245 100 18u "Morango"
  Pop $16

  ; Selected crops output field
  ${NSD_CreateLabel} 20 320 460 18u "Culturas Selecionadas:"
  Pop $0

  ${NSD_CreateText} 20 345 460 100u ""
  Pop $CropSection
  ${NSD_SetStyle} $CropSection ${ES_READONLY} ${ES_READONLY}
FunctionEnd

Function pageCulturasLeave
  ; Build selected crops string
  StrCpy $CropSection ""
  ${NSD_GetState} $1 $0
  ${If} $0 == ${BST_CHECKED}
    StrCpy $CropSection "Café, "
  ${EndIf}
  ; (Additional crops can be added here similarly)
  ${NSD_SetText} $CropSection $CropSection
FunctionEnd

;--------------------------------
; Download Page - Terms and Security
Function pageDownloadCreate
  nsDialogs::Create 1018
  Pop $Dialog

  ${If} $Dialog == error
    Abort
  ${EndIf}

  ; Header label
  ${NSD_CreateLabel} 20 15 100% 25u "Download"
  Pop $0
  ${NSD_SetFont} $0 ${FONT_BOLD} 14

  ; Terms of Use group box
  ${NSD_CreateGroupBox} 20 50 460 280u "Termos de Uso e Compromisso de Segurança"
  Pop $0

  ${NSD_CreateLabel} 40 75 420 18u "Termos de Uso:"
  Pop $0
  ${NSD_SetFont} $0 ${FONT_BOLD} 9

  ${NSD_CreateLabel} 40 95 420 60u "Ao baixar e usar o Ampliagro, você concorda com os termos de uso, incluindo a proteção de dados pessoais e agronômicos. Os dados são processados conforme as políticas de privacidade do sistema e em conformidade com a LGPD (Lei Geral de Proteção de Dados)."
  Pop $0

  ${NSD_CreateLabel} 40 160 420 18u "Compromisso de Segurança:"
  Pop $0
  ${NSD_SetFont} $0 ${FONT_BOLD} 9

  ${NSD_CreateLabel} 40 180 420 60u "Todos os downloads são criptografados durante transferência (TLS 1.3) e armazenamento (AES-256). Os dados são tratados com conformidade às regulamentações de proteção de dados. O sistema implementa medidas de segurança técnicas e organizacionais apropriadas. Nenhum dado é compartilhado com terceiros sem consentimento explícito."
  Pop $0

  ${NSD_CreateLabel} 40 245 420 35u "Ao prosseguir, você confirma que leu e concorda com os termos acima."
  Pop $0
  ${NSD_SetFont} $0 ${FONT_NORMAL} 9

  ; Accept checkbox
  ${NSD_CreateCheckBox} 40 290 420 18u "Aceito os termos de uso e o compromisso de segurança do Ampliagro"
  Pop $AcceptTerms

  ; Disable Next button initially (NSIS handles this via leave callback)
FunctionEnd

Function pageDownloadLeave
  ${NSD_GetState} $AcceptTerms $0
  ${If} $0 != ${BST_CHECKED}
    MessageBox MB_OK|MB_ICONWARNING "Você deve aceitar os termos de uso e o compromisso de segurança para continuar a instalação."
    Abort
  ${EndIf}
FunctionEnd