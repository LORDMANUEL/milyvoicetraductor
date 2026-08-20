!include "LogicLib.nsh"
!include "x64.nsh"

; El instalador debe mostrar el canal y la versión en la propia UI.
BrandingText "${PRODUCTNAME} ${VERSION} Beta"
Caption "${PRODUCTNAME} ${VERSION} Beta Setup"

!macro NSIS_HOOK_POSTINSTALL
  DetailPrint "MilyVoiceTraductor ${VERSION} Beta - preparando runtime, motor y sincronización local..."
  ; El instalador NSIS puede ejecutar hooks desde un proceso de 32 bits aunque
  ; el payload sea x64. Deshabilitamos la redirección WOW64 para ejecutar el
  ; Windows PowerShell 5.1 de 64 bits que ya valida el flujo previo al bundle.
  ${If} ${RunningX64}
    ${DisableX64FSRedirection}
  ${EndIf}
  nsExec::ExecToLog '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$INSTDIR\bootstrap\setup-installed.ps1" -InstallRoot "$INSTDIR" -AppRoot "$LOCALAPPDATA\MilyVoiceTraductor"'
  Pop $0
  ${If} ${RunningX64}
    ${EnableX64FSRedirection}
  ${EndIf}
  ${If} $0 == "0"
    DetailPrint "MilyVoiceTraductor ${VERSION} Beta - runtime, motor, extensión y Native Messaging preparados."
    ; En instalación silenciosa (CI/despliegue administrado) no se abre Desktop.
    IfSilent +2 0
    ExecShell "open" "$INSTDIR\MilyVoiceTraductor.exe"
  ${Else}
    DetailPrint "MilyVoiceTraductor ${VERSION} Beta - la preparación local devolvió código $0."
    SetErrorLevel 2
    ; No permitir que NSIS termine mostrando "Installation Complete" cuando el
    ; runtime/motor quedó roto. En /S se salta únicamente el MessageBox.
    IfSilent +2 0
    MessageBox MB_OK|MB_ICONSTOP "MilyVoiceTraductor ${VERSION} Beta no pudo completar la preparación local. La instalación se marcará como fallida. Revisa el diagnóstico de instalación antes de volver a intentar."
    Abort "MilyVoiceTraductor ${VERSION} Beta - instalación incompleta: falló la preparación local."
  ${EndIf}
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  DetailPrint "Retirando registro Native Messaging de MilyVoiceTraductor..."
  ${If} ${RunningX64}
    ${DisableX64FSRedirection}
  ${EndIf}
  nsExec::ExecToLog '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$INSTDIR\bootstrap\register-native-host.ps1" -BridgePath "$LOCALAPPDATA\MilyVoiceTraductor\bridge\milyvoice-bridge.exe" -ManifestTemplate "$INSTDIR\bootstrap\native-host-template.json" -ManifestOutput "$LOCALAPPDATA\MilyVoiceTraductor\bridge\com.milyvoice.traductor.json" -Unregister'
  Pop $0
  ${If} ${RunningX64}
    ${EnableX64FSRedirection}
  ${EndIf}
!macroend
