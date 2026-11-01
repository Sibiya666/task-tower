$ErrorActionPreference='Stop'
$link=Join-Path ([Environment]::GetFolderPath('Desktop')) 'Codex + Башня агентов.lnk'
$shell=New-Object -ComObject WScript.Shell
$shortcut=$shell.CreateShortcut($link)
$shortcut.TargetPath=Join-Path $env:WINDIR 'System32/WindowsPowerShell/v1.0/powershell.exe'
$shortcut.Arguments='-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -STA -File "'+(Join-Path $PSScriptRoot 'launch-codex-tower.ps1')+'"'
$shortcut.WorkingDirectory=$PSScriptRoot
$shortcut.IconLocation=(Join-Path $PSScriptRoot 'assets/tower-icon.ico')+',0'
$shortcut.WindowStyle=7
$shortcut.Description='Codex and Task Tower desktop overlay'
$shortcut.Save()
$check=$shell.CreateShortcut($link)
if($check.Arguments -ne $shortcut.Arguments -or $check.IconLocation -ne $shortcut.IconLocation){throw 'Shortcut verification failed'}
Write-Output ('Shortcut updated: '+$check.Arguments)
