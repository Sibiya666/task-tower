param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
$overlay = Join-Path $PSScriptRoot 'overlay.ps1'
$icon = Join-Path $PSScriptRoot 'assets/tower-icon.ico'
if(-not (Test-Path -LiteralPath $overlay)){throw 'Overlay script not found'}
if(-not (Test-Path -LiteralPath $icon)){throw 'Tower icon not found'}
# Package family is stable across application updates; no version-specific EXE path.
$app = 'shell:AppsFolder\OpenAI.Codex_2p2nqsd0c76g0!App'
if($CheckOnly){Write-Output ('Codex: '+$app);Write-Output ('Overlay: '+$overlay);Write-Output ('Icon: '+$icon);return}
Start-Process -FilePath 'explorer.exe' -ArgumentList $app
& $overlay
