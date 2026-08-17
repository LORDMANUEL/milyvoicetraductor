!include "LogicLib.nsh"

!macro NSIS_HOOK_POSTINSTALL
  DetailPrint "Preparando motor local de MilyVoiceTraductor..."
  nsExec::ExecToLog '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$INSTDIR\resources\bootstrap\setup-installed.ps1" -InstallRoot "$INSTDIR" -ModelPack business-qwen'
  Pop $0
  ${If} $0 == "0"
    DetailPrint "Motor local, extensión y modelo recomendados preparados."
  ${ElseIf} $0 == "2"
    MessageBox MB_OK|MB_ICONEXCLAMATION "MilyVoiceTraductor se instaló y el motor local quedó preparado, pero el modelo no terminó de descargarse. Abra la aplicación y use Modelos para reintentar la descarga."
  ${Else}
    MessageBox MB_OK|MB_ICONEXCLAMATION "MilyVoiceTraductor se instaló, pero la preparación automática del motor local no terminó. Revise %LOCALAPPDATA%\MilyVoiceTraductor\bootstrap\status.json. Puede instalar Python 3.13 x64 y ejecutar nuevamente el instalador."
  ${EndIf}
!macroend
