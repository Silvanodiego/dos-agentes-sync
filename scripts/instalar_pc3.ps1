param([switch]$Verificar, [string]$Destino = 'C:\dos_agentes_local')
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'Continue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$source = Split-Path $PSScriptRoot -Parent
$repo = 'https://github.com/Silvanodiego/dos-agentes-sync.git'
function Paso($n, $text) { Write-Host "`n[$n/6] $text" -ForegroundColor Cyan }
function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User') + ";$env:ProgramFiles\nodejs;$env:ProgramFiles\Git\cmd;$env:LOCALAPPDATA\Microsoft\WindowsApps"
    Get-ChildItem "$env:LOCALAPPDATA\Programs\Python" -Directory -ErrorAction SilentlyContinue | ForEach-Object { $env:Path = $_.FullName + ';' + (Join-Path $_.FullName 'Scripts') + ';' + $env:Path }
}
function Run {
    param($exe, [Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments)
    Write-Host ('> ' + $exe + ' ' + ($Arguments -join ' '))
    & $exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Fallo ($LASTEXITCODE): $exe $($Arguments -join ' ')" }
}
function Winget($id, [string[]]$Extra = @()) {
    if (!(Get-Command winget.exe -ErrorAction SilentlyContinue)) { throw 'Falta winget (App Installer de Microsoft). No se puede instalar requisitos sin el gestor del sistema.' }
    Run winget.exe (@('install','--id',$id,'--exact','--source','winget','--silent','--accept-package-agreements','--accept-source-agreements','--disable-interactivity') + $Extra)
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
    Write-Host "Integridad correcta: $($manifest.files.Count) archivos, paquete v5."
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
    if (!(Test-Path -LiteralPath $Destino)) {
        Run git.exe @('clone','--branch','main',$repo,$Destino)
    } elseif (!(Test-Path -LiteralPath (Join-Path $Destino '.git'))) {
        # Un clon temporal conserva los archivos locales preexistentes.
        $clone = Join-Path $env:TEMP ('dos-agentes-git-' + [guid]::NewGuid())
        Run git.exe @('clone','--branch','main',$repo,$clone)
        Copy-Item -LiteralPath (Join-Path $clone '.git') -Destination $Destino -Recurse
    }
    $remote = & git.exe -C $Destino remote get-url origin
    if ($LASTEXITCODE -ne 0 -or $remote.Trim() -ne $repo) { throw 'El destino tiene otro remoto Git. Se conserva sin sobrescribir.' }
    $branch = & git.exe -C $Destino branch --show-current
    if ($branch.Trim() -ne 'main') { throw 'El destino no esta en main. Se conserva la rama actual.' }
    if ([IO.Path]::GetFullPath($source).TrimEnd('\') -ne [IO.Path]::GetFullPath($Destino).TrimEnd('\')) {
        $manifest = Get-Content (Join-Path $source 'MANIFIESTO_SHA256.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        foreach ($entry in $manifest.files) {
            $target = Join-Path $Destino $entry.path
            if ((Test-Path -LiteralPath $target) -and $entry.path -match '(^|/)(bridge_server|consultar_gemini|bucle_autonomo)\.py$') {
                if ((Get-FileHash -LiteralPath $target).Hash -ne $entry.sha256) { throw "Script protegido distinto en destino: $($entry.path). No fue modificado." }
                continue
            }
            New-Item -ItemType Directory -Force -Path (Split-Path $target -Parent) | Out-Null
            Copy-Item -LiteralPath (Join-Path $source $entry.path) -Destination $target -Force
        }
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
    if (!(Test-Path -LiteralPath $py)) { Run $python.Source @('-m','venv',$venv) }
    Run $py @('-m','pip','install','--upgrade','pip')
    Run $py @('-m','pip','install','-r','requirements.txt','-r','requirements_chat_fijo.txt','-r','requirements_instalacion.txt')
    Paso 4 'Instalando Node.js y paquetes npm (salida en vivo)...'
    $nodeOk = $false
    if (Get-Command node.exe -ErrorAction SilentlyContinue) {
        $nodeVersion = (& node.exe --version)
        $nodeOk = $LASTEXITCODE -eq 0 -and $nodeVersion -match '^v24\.'
    }
    if (!$nodeOk) { Winget 'OpenJS.NodeJS.24' }
    $nodeVersion = & node.exe --version
    if ($nodeVersion -notmatch '^v24\.') { throw 'Se requiere Node.js LTS 24, compatible con la PC 1. winget no proporciono esa version.' }
    function Npm-Install {
        param([string[]]$NpmArguments)
        & npm.cmd @NpmArguments
        if ($LASTEXITCODE -eq 0) { return }
        Write-Warning 'npm fallo. Se instalaran C++ Build Tools y Windows SDK; se reintentara una vez.'
        Winget -id 'Microsoft.VisualStudio.2022.BuildTools' -Extra @('--override','--wait --quiet --norestart --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended')
        $env:npm_config_msvs_version = '2022'
        $env:npm_config_python = $py
        Run npm.cmd $NpmArguments
    }
    Npm-Install -NpmArguments @('ci','--no-audit','--no-fund')
    if (!(Get-Command codex.cmd -ErrorAction SilentlyContinue)) { Npm-Install -NpmArguments @('install','--global','@openai/codex') }
    Paso 5 'Configurando TOML, Cascada AG, Chat Fijo Gemini e inicio automatico...'
    Run $py @('scripts\configurar_pc3.py','--root',$Destino,'--home',$env:USERPROFILE)
    $globalScripts = Join-Path $env:USERPROFILE 'ScriptsGlobales'
    $userPath = [string][Environment]::GetEnvironmentVariable('Path','User')
    if (@($userPath -split ';') -notcontains $globalScripts) {
        [Environment]::SetEnvironmentVariable('Path', ($userPath.TrimEnd(';') + ';' + $globalScripts), 'User')
    }
    Refresh-Path
    $manager = Join-Path $Destino 'AntigravityManager\antigravity-manager.exe'
    if (!(Test-Path -LiteralPath $manager)) {
        Write-Host 'Consultando la release oficial de Antigravity Manager (sin URLs de version fija)...'
        $release = Invoke-RestMethod 'https://api.github.com/repos/Draculabo/AntigravityManager/releases/latest'
        $arch = if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { 'arm64' } else { 'x64' }
        $asset = @($release.assets | Where-Object { $_.name -like "*-windows-$arch-nsis.exe" })
        if ($asset.Count -ne 1) { throw 'No se encontro un instalador Windows oficial inequívoco de Antigravity Manager.' }
        $setup = Join-Path $env:TEMP ('AntigravityManager-' + [guid]::NewGuid() + '.exe')
        Write-Host "Descargando $($asset[0].name)..."
        # curl muestra bytes y velocidad durante toda la descarga.
        Run curl.exe @('--fail','--location','--retry','2','--output',$setup,$asset[0].browser_download_url)
        if (!$asset[0].digest -or $asset[0].digest -notmatch '^sha256:') { throw 'La release no publica SHA256; se detiene antes de ejecutar un binario sin verificar.' }
        if ((Get-FileHash -LiteralPath $setup).Hash -ne ($asset[0].digest -replace '^sha256:','')) { throw 'SHA256 incorrecto del instalador de Antigravity Manager.' }
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
    Run $py @('scripts\configurar_pc3.py','--root',$Destino,'--home',$env:USERPROFILE,'--iniciar')
    Start-Process -FilePath "$env:WINDIR\System32\wscript.exe" -ArgumentList ('//B //Nologo "' + (Join-Path $Destino 'abrir_chrome_gemini_oculto.bat') + '"') -WindowStyle Hidden | Out-Null
    Write-Host 'INSTALACION COMPLETA - v5' -ForegroundColor Green
    Write-Host 'Debe volver a autenticar las cuentas en Antigravity Manager y Gemini: no se migraron credenciales ni perfiles DPAPI.' -ForegroundColor Yellow
    Write-Host 'Codex usa la exportacion auth_c1.json si no existia auth.json. Si expiro su sesion, vuelva a iniciar sesion. Gemini: abrir_chrome_gemini.bat.'
    exit 0
} catch {
    Write-Host ("ERROR: " + $_.Exception.Message) -ForegroundColor Red
    Write-Host 'Instalacion incompleta: no se anuncia exito ni se ocultan los errores.'
    if (!$Verificar) { Read-Host 'Presione Enter para cerrar' | Out-Null }
    exit 1
}
