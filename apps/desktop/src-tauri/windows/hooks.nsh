!include "LogicLib.nsh"

!macro NSIS_HOOK_POSTINSTALL
  DetailPrint "Preparando runtime, motor y sincronización local de MilyVoiceTraductor..."
  nsExec::ExecToLog '\"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe\" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File \"$INSTDIR\bootstrap\setup-installed.ps1\" -InstallRoot \"$INSTDIR\" -AppRoot \"$LOCALAPPDATA\MilyVoiceTraductor\"'
  Pop $0
  ${If} $0 == "0"
    DetailPrint "Runtime, motor, extensión y Native Messaging preparados."
    ; En instalación silenciosa (CI/despliegue administrado) no se abre Desktop.
    ; Esto garantiza que /S finalice como un proceso totalmente no interactivo.
    IfSilent +2 0
    ExecShell "open" "$INSTDIR\MilyVoiceTraductor.exe"
  ${Else}
    DetailPrint "La preparación local devolvió código $0."
    ; Un MessageBox durante /S deja el instalador esperando entrada humana para siempre.
    IfSilent +2 0
    MessageBox MB_OK|MB_ICONEXCLAMATION "MilyVoiceTraductor se instaló, pero un componente local no terminó de prepararse. Abre la aplicación para ver el diagnóstico y usar Reparar instalación."
  ${EndIf}
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  DetailPrint "Retirando registro Native Messaging de MilyVoiceTraductor..."
  nsExec::ExecToLog '\"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe\" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File \"$INSTDIR\bootstrap\register-native-host.ps1\" -BridgePath \"$LOCALAPPDATA\MilyVoiceTraductor\bridge\milyvoice-bridge.exe\" -ManifestTemplate \"$INSTDIR\bootstrap\native-host-template.json\" -ManifestOutput \"$LOCALAPPDATA\MilyVoiceTraductor\bridge\com.milyvoice.traductor.json\" -Unregister'
  Pop $0
!macroend
