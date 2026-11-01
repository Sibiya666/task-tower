param([switch]$SmokeTest)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName PresentationFramework,PresentationCore,WindowsBase,System.Web.Extensions
$sdk=Join-Path $PSScriptRoot 'vendor/webview2/sdk'
$core=Join-Path $sdk 'lib/net462/Microsoft.Web.WebView2.Core.dll'
$wpf=Join-Path $sdk 'lib/net462/Microsoft.Web.WebView2.Wpf.dll'
$loader=Join-Path $sdk 'runtimes/win-x64/native'
Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;public class TowerDllPath{[DllImport("kernel32.dll",CharSet=CharSet.Unicode)]public static extern bool SetDllDirectory(string path);}'
if(-not [TowerDllPath]::SetDllDirectory($loader)){throw 'Cannot configure WebView2 loader'}
[void][Reflection.Assembly]::LoadFrom($core)
[void][Reflection.Assembly]::LoadFrom($wpf)
$references=@('System.dll','System.Core.dll','System.Drawing.dll','System.Xaml.dll','System.Web.Extensions.dll',([Windows.Window].Assembly.Location),([Windows.Media.Brush].Assembly.Location),([Windows.Threading.Dispatcher].Assembly.Location),$core,$wpf)
Add-Type -Path (Join-Path $PSScriptRoot 'TowerHost.cs') -ReferencedAssemblies $references
$python=Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$result=[TowerHost]::Run($PSScriptRoot,$python,$SmokeTest.IsPresent)
if($result -ne 0){throw ('HTML overlay failed; see runtime/html-host-error.log (code '+$result+')')}
