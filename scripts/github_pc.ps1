function Ensure-GitHubAccess {
    if (!(Get-Command gh.exe -ErrorAction SilentlyContinue)) { Winget 'GitHub.cli' }
    if (!(Get-Command gh.exe -ErrorAction SilentlyContinue)) { throw 'Falta GitHub CLI despues de instalarlo.' }
    & gh.exe auth status --hostname github.com
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Debe autorizar GitHub en el navegador para poder sincronizar. Complete el inicio de sesion que se abre.' -ForegroundColor Yellow
        Run -exe gh.exe -Arguments @('auth','login','--hostname','github.com','--git-protocol','https','--web')
    }
    Run -exe gh.exe -Arguments @('auth','status','--hostname','github.com')
    $permission = & gh.exe api --hostname github.com repos/Silvanodiego/dos-agentes-sync --jq '.permissions.push'
    if ($LASTEXITCODE -ne 0 -or ([string]$permission).Trim() -ne 'true') {
        throw 'GitHub no autorizo escritura en Silvanodiego/dos-agentes-sync. Use una cuenta con acceso; no se anuncia exito.'
    }
    Run -exe gh.exe -Arguments @('auth','setup-git','--hostname','github.com')
    Write-Host 'GitHub: sesion verificada y permiso de escritura confirmado en dos-agentes-sync.' -ForegroundColor Green
}
