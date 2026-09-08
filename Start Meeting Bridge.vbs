' Meeting Bridge launcher — shows errors if window fails to start
Option Explicit
Dim sh, fso, root, pythonw, script, logFile, rc, cmd
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
If Right(root, 1) <> "\" Then root = root & "\"
logFile = root & "gui-launch.log"
script = root & "run_gui.pyw"

' Clear stale launch log so we don't show an old error
If fso.FileExists(logFile) Then
  On Error Resume Next
  fso.DeleteFile logFile, True
  On Error GoTo 0
End If

pythonw = ""
If fso.FileExists(root & ".venv\Scripts\pythonw.exe") Then
  pythonw = root & ".venv\Scripts\pythonw.exe"
ElseIf fso.FileExists(sh.ExpandEnvironmentStrings("%USERPROFILE%\miniconda3\pythonw.exe")) Then
  pythonw = sh.ExpandEnvironmentStrings("%USERPROFILE%\miniconda3\pythonw.exe")
End If

If pythonw = "" Then
  MsgBox "Не найден pythonw.exe." & vbCrLf & _
         "Сначала запустите install.ps1 в папке проекта." & vbCrLf & vbCrLf & _
         "Путь: " & root, 16, "Meeting Bridge"
  WScript.Quit 1
End If

If Not fso.FileExists(root & "config.yaml") Then
  MsgBox "Не найден config.yaml." & vbCrLf & _
         "Сначала запустите install.ps1 в папке проекта.", 16, "Meeting Bridge"
  WScript.Quit 1
End If

sh.CurrentDirectory = root
cmd = """" & pythonw & """ """ & script & """"
On Error Resume Next
rc = sh.Run(cmd, 1, False)
If Err.Number <> 0 Then
  MsgBox "Не удалось запустить:" & vbCrLf & Err.Description & vbCrLf & vbCrLf & cmd, 16, "Meeting Bridge"
  WScript.Quit 1
End If

' Give the process a moment; if it dies instantly, show a short tip.
WScript.Sleep 2000
If fso.FileExists(logFile) Then
  If fso.GetFile(logFile).Size > 0 Then
    If fso.GetFile(logFile).DateLastModified > Now - (2 / 24 / 60) Then
      MsgBox "Meeting Bridge не запустился." & vbCrLf & vbCrLf & _
             "Откройте файл с подробностями:" & vbCrLf & logFile, 16, "Meeting Bridge"
      On Error Resume Next
      sh.Run "notepad.exe """ & logFile & """", 1, False
      On Error GoTo 0
      WScript.Quit 1
    End If
  End If
End If
