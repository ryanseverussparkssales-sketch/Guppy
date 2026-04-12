Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = "C:\Users\Ryan\Desktop\Open Interpreter.lnk"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = "C:\Users\Ryan\AI_Project\launch_interpreter.bat"
oLink.WorkingDirectory = "C:\Users\Ryan\AI_Project"
oLink.Description = "Launch Open Interpreter AI Assistant"
oLink.IconLocation = "C:\Windows\System32\shell32.dll,166"
oLink.Save
