$ErrorActionPreference='Stop'
# Only this overlay's own windows; never close Codex or unrelated shells.
$old=@(Get-Process powershell -ErrorAction SilentlyContinue | Where-Object {$_.MainWindowTitle -eq 'Башня агентов — Codex'})
foreach($process in $old){[void]$process.CloseMainWindow()}
foreach($process in $old){if(-not $process.WaitForExit(5000)){throw ('Old overlay did not stop: '+$process.Id)}}
$path=Join-Path $PSScriptRoot 'overlay.ps1'
$new=Start-Process powershell.exe -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-WindowStyle','Hidden','-STA','-File',('"'+$path+'"')) -WindowStyle Hidden -RedirectStandardError (Join-Path $PSScriptRoot 'runtime/canvas-overlay-error.log') -PassThru
Set-Content -LiteralPath (Join-Path $PSScriptRoot 'runtime/overlay.pid') -Value $new.Id
Write-Output ('Canvas overlay PID: '+$new.Id)
