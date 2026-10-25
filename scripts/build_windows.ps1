[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$VcVars
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path -LiteralPath $VcVars -PathType Leaf)) {
    throw "vcvars64.bat not found: $VcVars"
}
$source = Join-Path $root 'src\dds_decode.c'
$include = Join-Path $root 'src'
$output = Join-Path $root 'bin\herta_dds_windows_x64.dll'
$temp = Join-Path ([System.IO.Path]::GetTempPath()) ("herta-bc7-build-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $temp | Out-Null
$batch = Join-Path $temp 'build.cmd'
$object = Join-Path $temp 'dds_decode.obj'
$import = Join-Path $temp 'dds_decode.lib'
$contents = @"
@echo off
call "$VcVars" >nul
if errorlevel 1 exit /b 1
cl /nologo /O2 /LD /W4 /Zl /GS- /DHERTA_FREESTANDING_WINDOWS /I"$include" "$source" /Fo"$object" /Fe"$output" /link /NODEFAULTLIB /NOENTRY /IMPLIB:"$import"
exit /b %errorlevel%
"@
[System.IO.File]::WriteAllText($batch, $contents, [System.Text.Encoding]::ASCII)
try {
    & cmd.exe /d /c $batch
    if ($LASTEXITCODE -ne 0) { throw "MSVC build failed with exit code $LASTEXITCODE" }
} finally {
    Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
}
Write-Host "Built $output"
