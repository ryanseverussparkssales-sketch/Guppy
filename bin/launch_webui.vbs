Dim shell, dir, ps1
Set shell = CreateObject("WScript.Shell")
dir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
ps1 = dir & "\launch_webui.ps1"
shell.Run "powershell -ExecutionPolicy Bypass -NonInteractive -File """ & ps1 & """", 0, False
