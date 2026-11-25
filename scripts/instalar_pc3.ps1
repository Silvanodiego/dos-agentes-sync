param([switch]$Verificar, [string]$Destino = 'C:\dos_agentes_local')
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'Continue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$source = Split-Path $PSScriptRoot -Parent
$repo = 'https://github.com/Silvanodiego/dos-agentes-sync.git'
. (Join-Path $PSScriptRoot 'node_pc3.ps1')
. (Join-Path $PSScriptRoot 'copiar_paquete_pc.ps1')
function Paso($n, $text) { Write-Host "`n[$n/6] $text" -ForegroundColor Cyan }
function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User') + ";$env:ProgramFiles\nodejs;$env:ProgramFiles\Git\cmd;$env:LOCALAPPDATA\Microsoft\WindowsApps"
    Get-ChildItem "$env:LOCALAPPDATA\Programs\Python" -Directory -ErrorAction SilentlyContinue | ForEach-Object { $env:Path = $_.FullName + ';' + (Join-Path $_.FullName 'Scripts') + ';' + $env:Path }
    $localNode = Join-Path $Destino 'runtime\node-v24.22.3-win-x64'
    if (Test-Path -LiteralPath (Join-Path $localNode 'node.exe')) { Enable-NodePath -Directory $localNode }
}
function Run {
    param([Parameter(Mandatory=$true)][string]$exe, [string[]]$Arguments)
    Write-Host ('> ' + $exe + ' ' + ($Arguments -join ' '))
    & $exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Fallo ($LASTEXITCODE): $exe $($Arguments -join ' ')" }
}
function Winget($id, [string[]]$Extra = @()) {
    if (!(Get-Command winget.exe -ErrorAction SilentlyContinue)) { throw 'Falta winget (App Installer de Microsoft). No se puede instalar requisitos sin el gestor del sistema.' }
    Run -exe winget.exe -Arguments (@('install','--id',$id,'--exact','--source','winget','--silent','--accept-package-agreements','--accept-source-agreements','--disable-interactivity') + $Extra)
    Refresh-Path
}
function Check-Package {
    $manifestFile = Join-Path $source 'MANIFIESTO_SHA256.json'
    if (!(Test-Path -LiteralPath $manifestFile)) { throw 'Falta MANIFIESTO_SHA256.json. Extraiga el ZIP completo antes de instalar.' }
    $manifest = Get-Content -LiteralPath $manifestFile -Raw -Encoding UTF8 | ConvertFrom-Json
    $prefix = [IO.Path]::GetFullPath($source).TrimEnd('\') + '\'
    foreach ($item in $manifest.files) {
        $path = [IO.Path]::GetFullPath((Join-Path $source $item.path))
        if (!$path.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Ruta invalida en manifiesto.' }
        if (!(Test-Path -LiteralPath $path -PathType Leaf)) { throw "Falta archivo: $($item.path)" }
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $item.sha256) { throw "Integridad incorrecta: $($item.path)" }
    }
    foreach ($required in @('arrancar_todo_oculto.vbs','chat_fijo_gemini.py','piloto_gemini.py','abrir_chrome_gemini.bat','abrir_chrome_gemini_oculto.bat','config_compartida\AGENTS.md','config_compartida\config.toml','scripts\configurar_pc3.py','package-lock.json')) {
        if (!(Test-Path -LiteralPath (Join-Path $source $required))) { throw "Falta componente: $required" }
    }
    foreach ($group in @('codex\skills','codex\plugins','codex\marketplaces','repos_referencia\token-saver','ScriptsGlobales\modulos_enjambre','runtime\agy','runtime\installers','git_bundles')) {
        if (!(Test-Path -LiteralPath (Join-Path $source $group) -PathType Container)) { throw "Falta grupo del ecosistema: $group" }
    }
    Write-Host "Integridad correcta: $($manifest.files.Count) archivos, paquete v8."
}
try {
    Paso 1 'Verificando integridad...'
    Check-Package
    if ($Verificar) { Write-Host 'VERIFICACION COMPLETA (sin instalar ni reiniciar servicios).'; exit 0 }
    $admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (!$admin) {
        Write-Host 'Solicitando permisos de Administrador para instalar requisitos...'
        $argsElevated = '-NoProfile -ExecutionPolicy Bypass -File "' + $PSCommandPath + '" -Destino "' + $Destino + '"'
        $child = Start-Process powershell.exe -Verb RunAs -ArgumentList $argsElevated -PassThru -Wait
        exit $child.ExitCode
    }
    Refresh-Path
    Paso 2 'Preparando Git y repositorio main...'
    if (!(Get-Command git.exe -ErrorAction SilentlyContinue)) { Winget 'Git.Git' }
    $cloneSource = Join-Path $source 'git_bundles\dos-agentes-sync.bundle'
    if (!(Test-Path -LiteralPath $cloneSource)) { throw 'Falta el bundle Git principal.' }
    if (!(Test-Path -LiteralPath $Destino)) {
        Run -exe git.exe -Arguments @('clone','--branch','main',$cloneSource,$Destino)
        Run -exe git.exe -Arguments @('-C',$Destino,'remote','set-url','origin',$repo)
    } elseif (!(Test-Path -LiteralPath (Join-Path $Destino '.git'))) {
        # Un clon temporal conserva los archivos locales preexistentes.
        $clone = Join-Path $env:TEMP ('dos-agentes-git-' + [guid]::NewGuid())
        Run -exe git.exe -Arguments @('clone','--branch','main',$cloneSource,$clone)
        Run -exe git.exe -Arguments @('-C',$clone,'remote','set-url','origin',$repo)
        Copy-Item -LiteralPath (Join-Path $clone '.git') -Destination $Destino -Recurse
    }
    $remote = & git.exe -C $Destino remote get-url origin
    if ($LASTEXITCODE -ne 0 -or $remote.Trim() -ne $repo) { throw 'El destino tiene otro remoto Git. Se conserva sin sobrescribir.' }
    $branch = & git.exe -C $Destino branch --show-current
    if ($branch.Trim() -ne 'main') { throw 'El destino no esta en main. Se conserva la rama actual.' }
    if ([IO.Path]::GetFullPath($source).TrimEnd('\') -ne [IO.Path]::GetFullPath($Destino).TrimEnd('\')) {
        $manifest = Get-Content (Join-Path $source 'MANIFIESTO_SHA256.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        Copy-PackageFiles -SourceRoot $source -DestinationRoot $Destino -Manifest $manifest
    }
    Set-Location $Destino
    Paso 3 'Instalando Python/pip y dependencias...'
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    $pythonOk = $false
    if ($python -and $python.Source -notlike '*WindowsApps*') {
        & $python.Source -c 'import sys; raise SystemExit(not ((3,11) <= sys.version_info[:2] < (3,15)))'
        $pythonOk = $LASTEXITCODE -eq 0
    }
    if (!$pythonOk) { Winget 'Python.Python.3.14'; $python = Get-Command python.exe -ErrorAction Stop }
    $venv = Join-Path $Destino '.venv'
    $py = Join-Path $venv 'Scripts\python.exe'
    if (!(Test-Path -LiteralPath $py)) { Run -exe $python.Source -Arguments @('-m','venv',$venv) }
    Run -exe $py -Arguments @('-m','pip','install','--upgrade','pip')
    Run -exe $py -Arguments @('-m','pip','install','-r','requirements.txt','-r','requirements_chat_fijo.txt','-r','requirements_instalacion.txt')
    Run -exe $py -Arguments @('-m','pip','install','.\repos_referencia\token-saver')
    if (Test-Path 'repos_referencia\Agentic-SEO-Skill\requirements.txt') {
        Run -exe $py -Arguments @('-m','pip','install','-r','repos_referencia\Agentic-SEO-Skill\requirements.txt')
    }
    Run -exe $py -Arguments @((Join-Path $Destino 'scripts\validar_scripts_protegidos.py'), $Destino)
    Paso 4 'Instalando Node.js y paquetes npm (salida en vivo)...'
    Install-Node24 -Root $Destino -Persist
    function Npm-Install {
        param([string[]]$NpmArguments)
        & npm.cmd @NpmArguments
        if ($LASTEXITCODE -eq 0) { return }
        Write-Warning 'npm fallo. Se instalaran C++ Build Tools y Windows SDK; se reintentara una vez.'
        $vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
        if (!(Test-Path -LiteralPath $vswhere)) {
            Winget -id 'Microsoft.VisualStudio.2022.BuildTools' -Extra @('--override','--wait --quiet --norestart --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended')
        }
        if (!(Test-Path -LiteralPath $vswhere)) { throw 'Build Tools no publico vswhere.exe.' }
        $vs = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
        if (!$vs) {
            $vs = & $vswhere -latest -products '*' -property installationPath
            if (!$vs) { throw 'No se encontro Visual Studio Build Tools.' }
            Run -exe "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\setup.exe" -Arguments @('modify','--installPath',$vs,'--add','Microsoft.VisualStudio.Workload.VCTools','--includeRecommended','--quiet','--norestart')
        }
        $devcmd = Join-Path $vs 'Common7\Tools\VsDevCmd.bat'
        $environment = & cmd.exe /d /s /c ('""' + $devcmd + '" -no_logo -arch=x64 && set"')
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo cargar el entorno C++.' }
        foreach ($line in $environment) {
            if ($line -match '^([^=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process') }
        }
        $env:npm_config_msvs_version = '2022'
        # node-gyp requiere un Python con soporte de su version; 3.12 es estable.
        $gypPython = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
        if (!(Test-Path $gypPython)) { $gypPython = Join-Path $env:ProgramFiles 'Python312\python.exe' }
        if (!(Test-Path $gypPython)) {
            Winget 'Python.Python.3.12'
            $gypPython = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
            if (!(Test-Path $gypPython)) { $gypPython = Join-Path $env:ProgramFiles 'Python312\python.exe' }
        }
        if (!(Test-Path $gypPython)) { throw 'No se encontro Python 3.12 para node-gyp.' }
        $env:npm_config_python = $gypPython
        $env:PYTHON = $gypPython
        Run -exe npm.cmd -Arguments $NpmArguments
    }
    Npm-Install -NpmArguments @('ci','--no-audit','--no-fund')
    $globals = Get-Content 'dependencias\npm_globales.json' -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($package in $globals.PSObject.Properties) {
        Write-Host "Instalando paquete global $($package.Name)@$($package.Value.version)..."
        Npm-Install -NpmArguments @('install','--global',($package.Name + '@' + $package.Value.version),'--no-audit','--no-fund')
    }
    $npmRoot = (& npm.cmd root --global).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo consultar npm root global.' }
    Run -exe node.exe -Arguments @('scripts\verificar_sqlite_pc3.mjs',(Join-Path $npmRoot 'context-mode\package.json'))
    Run -exe $py -Arguments @('-m','pip','check')
    # Codex CLI no incluye el runtime Desktop requerido por node_repl/monitor.
    $desktop = Get-AppxPackage -Name OpenAI.Codex
    if (!$desktop) {
        Run -exe winget.exe -Arguments @('install','--id','9PLM9XGG6VKS','--exact','--source','msstore','--silent','--accept-package-agreements','--accept-source-agreements','--disable-interactivity')
        if (!(Get-AppxPackage -Name OpenAI.Codex)) { throw 'Codex Desktop no quedo instalado.' }
    }
    Paso 5 'Configurando TOML, Cascada AG, Chat Fijo Gemini e inicio automatico...'
    Run -exe $py -Arguments @('scripts\configurar_pc3.py','--root',$Destino,'--home',$env:USERPROFILE)
    $globalScripts = Join-Path $env:USERPROFILE 'ScriptsGlobales'
    $userPath = [string][Environment]::GetEnvironmentVariable('Path','User')
    foreach ($directory in @($globalScripts,(Join-Path $Destino '.bin'),(Join-Path $Destino '.venv\Scripts'),(Join-Path $env:LOCALAPPDATA 'agy\bin'),(Join-Path $env:APPDATA 'npm'))) {
        if (@($userPath -split ';') -notcontains $directory) { $userPath = $userPath.TrimEnd(';') + ';' + $directory }
    }
    [Environment]::SetEnvironmentVariable('Path', $userPath, 'User')
    Refresh-Path
    $manager = Join-Path $Destino 'AntigravityManager\antigravity-manager.exe'
    if (!(Test-Path -LiteralPath $manager)) {
        Write-Host 'Instalando Antigravity Manager 0.30.0 incluido y verificado (sin descarga 404)...'
        if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { throw 'Este paquete reproduce PC1 x64; no es un instalador ARM64.' }
        $setup = Join-Path $Destino 'runtime\installers\Antigravity.Manager-0.30.0-windows-x64-nsis.exe'
        if ((Get-FileHash -LiteralPath $setup).Hash -ne '702ff72d50ff00412bb6b16822131cc5ea6f56e6b28da9edc527c6beb6181762') { throw 'SHA256 incorrecto del instalador de Manager.' }
        $install = Start-Process -FilePath $setup -ArgumentList @('/S',('/D=' + (Split-Path $manager -Parent))) -PassThru -Wait
        if ($install.ExitCode -ne 0 -or !(Test-Path -LiteralPath $manager)) { throw 'Antigravity Manager no quedo instalado en el destino esperado.' }
    }
    $runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
    New-Item -Path $runKey -Force | Out-Null
    New-ItemProperty -Path $runKey -Name 'AntigravityManagerProxy' -Value ('"' + $manager + '"') -PropertyType String -Force | Out-Null
    $shell = New-Object -ComObject WScript.Shell
    $startup = [Environment]::GetFolderPath('Startup')
    $lnk = $shell.CreateShortcut((Join-Path $startup 'DosAgentesInicioOculto.lnk'))
    $lnk.TargetPath = "$env:WINDIR\System32\wscript.exe"
    $lnk.Arguments = '//B //Nologo "' + (Join-Path $Destino 'arrancar_todo_oculto.vbs') + '"'
    $lnk.WorkingDirectory = $Destino
    $lnk.WindowStyle = 7
    $lnk.Save()
    $action = New-ScheduledTaskAction -Execute "$env:WINDIR\System32\wscript.exe" -Argument ('//B //Nologo "' + (Join-Path $Destino 'scripts\sync_silencioso.vbs') + '" periodic') -WorkingDirectory $Destino
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(10) -RepetitionInterval (New-TimeSpan -Minutes 10)
    $principal = New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -Hidden -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 8)
    Register-ScheduledTask -TaskName 'DosAgentesGitSync' -Description 'auto_sync_git silencioso cada 10 minutos' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
    Paso 6 'Iniciando servicios...'
    Start-Process -FilePath $manager -WorkingDirectory (Split-Path $manager -Parent) -WindowStyle Hidden | Out-Null
    # Inicio local inmediato; la sincronizacion Git queda en la tarea periodica.
    Run -exe $py -Arguments @('scripts\configurar_pc3.py','--root',$Destino,'--home',$env:USERPROFILE,'--iniciar')
    Start-Process -FilePath "$env:WINDIR\System32\cmd.exe" -ArgumentList ('/d /s /c ""' + (Join-Path $Destino 'abrir_chrome_gemini_oculto.bat') + '""') -WorkingDirectory $Destino -WindowStyle Hidden | Out-Null
    if ($script:PreservedDifferences.Count) { Write-Warning 'Instalacion terminada conservando scripts locales diferentes: revise logs\instalacion_archivos_protegidos.json. Compatibilidad funcional pendiente de comprobar en esta PC.' }
    Write-Host 'INSTALACION COMPLETA - v8' -ForegroundColor Green
    Write-Host 'Debe volver a autenticar las cuentas en Antigravity Manager y Gemini: no se migraron credenciales ni perfiles DPAPI.' -ForegroundColor Yellow
    Write-Host 'Codex usa la exportacion auth_c1.json si no existia auth.json. Si expiro su sesion, vuelva a iniciar sesion. Gemini: abrir_chrome_gemini.bat.'
    exit 0
} catch {
    Write-Host ("ERROR: " + $_.Exception.Message) -ForegroundColor Red
    Write-Host 'Instalacion incompleta: no se anuncia exito ni se ocultan los errores.'
    if (!$Verificar) { Read-Host 'Presione Enter para cerrar' | Out-Null }
    exit 1
}
