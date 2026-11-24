# Regresion nativa PowerShell 5.1; no instala paquetes ni ejecuta el instalador.
$ErrorActionPreference = 'Stop'
$tokens = $null; $errors = $null
$installer = Join-Path $PSScriptRoot 'instalar_pc3.ps1'
$ast = [System.Management.Automation.Language.Parser]::ParseFile($installer, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw ($errors | Out-String) }
foreach ($name in @('Run','Winget')) {
    $definition = $ast.FindAll({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst]}, $true) | Where-Object Name -eq $name
    if (@($definition).Count -ne 1) { throw "Funcion ausente o duplicada: $name" }
    Invoke-Expression $definition.Extent.Text
}
function Refresh-Path {}
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ('argv pc3 ' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $testRoot | Out-Null
$oldPath = $env:Path
try {
    $exe = Join-Path $testRoot 'winget.exe'
    Add-Type -TypeDefinition @"
using System;
using System.IO;
using System.Text;
public class ArgvProbe {
    public static int Main(string[] args) {
        string[] encoded = Array.ConvertAll(args, s => Convert.ToBase64String(Encoding.UTF8.GetBytes(s)));
        File.WriteAllLines(Environment.GetEnvironmentVariable("PC3_ARGV_OUTPUT"), encoded);
        int code; return int.TryParse(Environment.GetEnvironmentVariable("PC3_ARGV_EXIT"), out code) ? code : 0;
    }
}
"@ -OutputAssembly $exe -OutputType ConsoleApplication
    $env:Path = $testRoot + ';' + $env:Path
    $env:PC3_ARGV_OUTPUT = Join-Path $testRoot 'argv.txt'
    $env:PC3_ARGV_EXIT = '0'
    function Assert-Argv([string[]]$Expected) {
        $actual = @(Get-Content -LiteralPath $env:PC3_ARGV_OUTPUT | ForEach-Object { [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($_)) })
        if ($actual.Count -ne $Expected.Count) { throw "Cantidad argv: $($actual.Count), esperada $($Expected.Count). Recibido: $($actual -join ' | ')" }
        for ($i = 0; $i -lt $Expected.Count; $i++) {
            if ($actual[$i] -cne $Expected[$i]) { throw "Argumento $i distinto: $($actual[$i])" }
        }
    }
    $base = @('install','--id','Git.Git','--exact','--source','winget','--silent','--accept-package-agreements','--accept-source-agreements','--disable-interactivity')
    Winget -id 'Git.Git'
    Assert-Argv -Expected $base
    $override = '--wait --quiet --norestart --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended'
    Winget -id 'Git.Git' -Extra @('--override',$override)
    Assert-Argv -Expected ($base + @('--override',$override))
    $spaced = @('clone','--branch','main','C:\Mi unidad\repo.bundle','C:\Carpeta con espacios\destino')
    Run -exe $exe -Arguments $spaced
    Assert-Argv -Expected $spaced
    $env:PC3_ARGV_EXIT = '23'
    $failed = $false
    try { Run -exe $exe -Arguments @('error') } catch {
        if ($_.Exception.Message -notlike 'Fallo (23):*') { throw }
        $failed = $true
    }
    if (!$failed) { throw 'Se oculto el codigo de error nativo.' }
    Write-Host 'OK: argv winget, override indivisible, rutas con espacios y propagacion de errores.'
} finally {
    $env:Path = $oldPath
    Remove-Item Env:PC3_ARGV_OUTPUT,Env:PC3_ARGV_EXIT -ErrorAction SilentlyContinue
    foreach ($name in @('winget.exe','argv.txt')) {
        $file = Join-Path $testRoot $name
        if (Test-Path -LiteralPath $file) { Remove-Item -LiteralPath $file -Force }
    }
    Remove-Item -LiteralPath $testRoot
}
