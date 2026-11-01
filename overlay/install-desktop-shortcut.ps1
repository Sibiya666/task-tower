$ErrorActionPreference = 'Stop'
$desktop = [Environment]::GetFolderPath('Desktop')
$target = Join-Path $desktop 'Codex + Башня агентов.lnk'
if(Test-Path -LiteralPath $target){throw 'Shortcut already exists; refusing to replace an existing shortcut'}
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($target)
$shortcut.TargetPath = Join-Path $env:WINDIR 'System32/WindowsPowerShell/v1.0/powershell.exe'
$shortcut.Arguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -STA -File "' + (Join-Path $PSScriptRoot 'launch-codex-tower.ps1') + '"'
$shortcut.WorkingDirectory = $PSScriptRoot
$shortcut.IconLocation = (Join-Path $PSScriptRoot 'assets/tower-icon.ico') + ',0'
$shortcut.Description = 'Запустить Codex и пиксельную башню проектов и агентов'
$shortcut.WindowStyle = 7
$shortcut.Save()
$check = $shell.CreateShortcut($target)
if($check.TargetPath -ne $shortcut.TargetPath -or $check.IconLocation -ne $shortcut.IconLocation){throw 'Shortcut verification failed'}
Write-Output $target
Write-Output ('Target: '+$check.TargetPath)
Write-Output ('Arguments: '+$check.Arguments)
Write-Output ('Icon: '+$check.IconLocation)
