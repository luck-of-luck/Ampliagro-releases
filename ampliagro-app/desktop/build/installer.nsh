; The HTML assistant is the interactive installation experience.
; Keep /S installs and automatic updates non-interactive.
!macro customInit
  Var /GLOBAL ampliagroInteractiveInstall
  StrCpy $ampliagroInteractiveInstall "0"
  ${IfNot} ${Silent}
    StrCpy $ampliagroInteractiveInstall "1"
  ${EndIf}
  SetSilent silent
!macroend

!macro customInstall
  ${If} $ampliagroInteractiveInstall == "1"
    ${StdUtils.ExecShellAsUser} $0 "$appExe" "open" "--ampliagro-setup"
  ${EndIf}
!macroend
