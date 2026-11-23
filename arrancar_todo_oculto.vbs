Option Explicit
Dim shell, fs, root, command, browserResult, syncResult
Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
root = fs.GetParentFolderName(WScript.ScriptFullName)

' Esperar CDP antes del sincronizador evita dos lanzamientos simultaneos.
' Ambos BAT se ejecutan con ventana 0; el navegador usa headless=new.
command = """" & shell.ExpandEnvironmentStrings("%ComSpec%") & """ /d /c " & Chr(34) & Chr(34) & root & "\abrir_chrome_gemini_oculto.bat" & Chr(34) & Chr(34)
browserResult = shell.Run(command, 0, True)
command = """" & shell.ExpandEnvironmentStrings("%ComSpec%") & """ /d /c " & Chr(34) & Chr(34) & root & "\sync_y_arrancar.bat" & Chr(34) & Chr(34)
syncResult = shell.Run(command, 0, False)
WScript.Quit browserResult
