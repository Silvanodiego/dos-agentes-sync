Option Explicit
Dim shell, fs, root, mode, command
Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
root = fs.GetParentFolderName(fs.GetParentFolderName(WScript.ScriptFullName))
mode = "periodic"
If WScript.Arguments.Count > 0 Then mode = WScript.Arguments(0)
If mode <> "periodic" And mode <> "startup" Then WScript.Quit 2
If mode = "startup" Then
    command = """" & shell.ExpandEnvironmentStrings("%ComSpec%") & """ /d /c " & Chr(34) & Chr(34) & root & "\sync_y_arrancar.bat" & Chr(34) & Chr(34)
Else
    command = "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File """ & root & "\scripts\sync_launcher.ps1"" -Mode " & mode
End If
WScript.Quit shell.Run(command, 0, True)
