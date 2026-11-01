param([switch]$SmokeTest)
$ErrorActionPreference='Stop'
& (Join-Path $PSScriptRoot 'run-html-overlay.ps1') -SmokeTest:$SmokeTest
