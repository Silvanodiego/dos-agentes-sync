#requires -Version 5.1
<#
Install the audited codexSync core without pip, GUI, scheduled tasks or sync.
Existing user history and cloud folders are never written by this setup.
Example: .\setup_chats.ps1 -SourceCheckout C:\audited\codexSync
#>
[CmdletBinding()]
param(
    [string]$SourceCheckout = '',
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'CodexSync'),
    [string]$CloudRoot = 'I:\Mi unidad\CodexSync',
    [string]$CodexHome = (Join-Path $env:USERPROFILE '.codex'),
    [string]$PythonExecutable = 'C:\dos_agentes_local\.venv\Scripts\python.exe',
    [string]$MachineId = ''
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if (-not (Test-Path -LiteralPath $PythonExecutable -PathType Leaf)) {
    $PythonExecutable = (Get-Command python.exe -ErrorAction Stop).Source
}
if (-not $MachineId) {
    $MachineId = (($env:COMPUTERNAME + '-' + $env:USERNAME).ToLowerInvariant() -replace '[^a-z0-9_-]', '-')
}
$installer = @'
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import tomllib
import zipfile

sys.dont_write_bytecode = True
PIN = '05084c7f67141105883df7c61a9b3eb9faa19661'
UPSTREAM = 'https://github.com/kroxiksut/codexSync.git'

def command(*args):
    result = subprocess.run(args, check=False, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=180)
    if result.returncode:
        raise RuntimeError(f'{args[0]} failed ({result.returncode}): {result.stderr.strip()}')
    return result.stdout.strip()

def inside(child, parent):
    return child == parent or parent in child.parents

def no_reparse(path):
    for entry in (path, *path.parents):
        if entry.is_symlink() or (hasattr(entry, 'is_junction') and entry.is_junction()):
            raise RuntimeError(f'Refusing linked setup path: {entry}')

def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def tree(path):
    result = {}
    for entry in path.rglob('*'):
        no_reparse(entry)
        if entry.is_file():
            result[entry.relative_to(path).as_posix()] = digest(entry)
    return result

def save_once(path, content):
    encoded = content.encode('utf-8')
    if path.exists():
        if path.read_bytes() != encoded:
            raise RuntimeError(f'Existing file differs; retained without overwrite: {path}')
        return
    with path.open('xb') as stream:
        stream.write(encoded)

def toml_value(value):
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return '[' + ', '.join(toml_value(item) for item in value) + ']'
    return json.dumps(str(value), ensure_ascii=True)

def main():
    if sys.version_info < (3, 14):
        raise RuntimeError('Python 3.14 or newer is required for existing zstd chat history; no packages were installed.')
    source_arg, install_arg, cloud_arg, codex_arg, machine = sys.argv[1:]
    install = Path(install_arg).absolute()
    codex = Path(codex_arg).absolute()
    cloud = Path(cloud_arg).absolute()
    no_reparse(install)
    no_reparse(codex)
    no_reparse(cloud)
    if inside(install, codex) or inside(codex, install) or inside(install, cloud) or inside(cloud, install):
        raise RuntimeError('InstallRoot must be outside CodexHome and CloudRoot.')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', machine):
        raise RuntimeError('MachineId must contain 1-80 ASCII letters, digits, underscore or dash.')
    install.mkdir(parents=True, exist_ok=True)
    if source_arg != '--clone':
        source = Path(source_arg).absolute()
    else:
        source = install / 'sources' / PIN
        no_reparse(source)
        if not source.exists():
            source.parent.mkdir(parents=True, exist_ok=True)
            command('git', 'clone', '--no-checkout', UPSTREAM, str(source))
            command('git', '-C', str(source), 'checkout', '--detach', PIN)
    no_reparse(source)
    head = command('git', '-C', str(source), 'rev-parse', 'HEAD')
    if head != PIN:
        raise RuntimeError(f'Unexpected upstream commit: {head}; expected {PIN}.')
    if command('git', '-C', str(source), 'status', '--porcelain', '--untracked-files=all'):
        raise RuntimeError('Source checkout is dirty; no vendor code was copied.')
    vendor = install / 'vendor'
    with tempfile.TemporaryDirectory(prefix='.setup-', dir=install) as staging:
        stage = Path(staging)
        if stage.parent != install or not stage.name.startswith('.setup-'):
            raise RuntimeError('Unsafe staging path.')
        archive = stage / 'source.zip'
        command('git', '-C', str(source), 'archive', '--format=zip', '--output', str(archive),
                PIN, 'src', 'LICENSE', 'README.md', 'pyproject.toml', 'config.example.toml')
        extracted = stage / 'vendor'
        extracted.mkdir()
        with zipfile.ZipFile(archive) as zipped:
            for member in zipped.infolist():
                target = (extracted / member.filename).resolve()
                if not inside(target, extracted.resolve()):
                    raise RuntimeError('Archive entry escapes staging directory.')
                if (member.external_attr >> 16) & 0o170000 == 0o120000:
                    raise RuntimeError('Archive contains symbolic link.')
            zipped.extractall(extracted)
        expected_tree = tree(extracted)
        if vendor.exists():
            no_reparse(vendor)
            if tree(vendor) != expected_tree:
                raise RuntimeError('Existing vendor tree differs from audited archive; no overwrite performed.')
        else:
            # Both absolute paths were checked inside the newly created staging/install roots.
            if extracted.parent != stage or vendor.parent != install:
                raise RuntimeError('Unsafe vendor move.')
            extracted.rename(vendor)
    save_once(install / 'vendor_commit.txt', PIN + '\n')
    save_once(install / 'vendor_manifest.json', json.dumps(expected_tree, indent=2, sort_keys=True) + '\n')
    wrapper = '''import runpy
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent / "vendor" / "src"))
sys.argv[0] = "codexsync"
runpy.run_module("codexsync", run_name="__main__")
'''
    save_once(install / 'codexsync.py', wrapper)
    python_exe = str(Path(sys.executable).resolve())
    bat = '@echo off\r\n"' + python_exe + '" "%~dp0codexsync.py" -c "%~dp0codexsync.toml" %*\r\nexit /b %errorlevel%\r\n'
    save_once(install / 'codexsync.bat', bat)
    config = install / 'codexsync.toml'
    windows_background = ['codex-windows-sandbox', 'codex-windows-sandbox-setup',
                          'codex-command-runner', '/OpenAI.Codex_*/app/ChatGPT.exe']
    sections = {
        'identity': {'machine_id': machine},
        'sync': {'mode': 'cold', 'direction': 'bidirectional', 'scope': 'full',
                 'session_mode': 'all', 'delete_policy': 'never', 'dry_run_default': True,
                 'close_codex': False},
        'paths': {'workspace_root_dir': cloud.as_posix(), 'local_state_dir': codex.as_posix(),
                  'cloud_root_dir': '${workspace_root}/sync',
                  'backup_dir': (install / 'overwrite-backups').as_posix(),
                  'temp_dir': (install / 'tmp').as_posix()},
        'guardian': {'root_dir': (install / 'guardian').as_posix()},
        'semantic': {'root_dir': '${workspace_root}/semantic', 'new_chats': 'same_path',
                     'mirror_compression': 'xz'},
        'targets': {'include_roots': ['sessions', 'archived_sessions', 'session_index.jsonl']},
        'filters': {'exclude_globs': ['**/auth.json', '**/*credential*', '**/*.lock',
                    '**/*.tmp', '**/*.temp', '**/cache/**', '**/__pycache__/**', '**/*.log']},
        'conflict': {'policy': 'prefer_newer_mtime', 'report_conflicts': True},
        'backup': {'backup_before_overwrite': True, 'retention_days': 30, 'max_backups': 0,
                   'compression': 'none'},
        'safety': {'require_codex_stopped': True, 'fail_on_unknown': True},
        'process_detection': {'process_names': ['codex.exe', 'codex', 'codex-app-server'],
                              'allow_terminate_if_running': False,
                              'manual_terminate_confirmation': True},
        'process_detection.background_process_names': {'windows': windows_background},
        'state': {'manifest_file': '${workspace_root}/state/manifest.json', 'data_version': 1},
        'scheduler': {'enabled': False, 'run_at_login': False, 'sync_at_login': False},
        'logging': {'file': (install / 'logs' / 'codexsync.log').as_posix()},
        'state_backup': {'root_dir': '', 'at_login': False, 'interval_hours': 0, 'keep': 5},
        'handoff': {'enabled': False, 'notify': True},
        'project_files': {'secret_files': 'no_hash', 'secret_patterns': []},
    }
    content = '# codexSync audited core; no automation enabled.\n\n' + '\n\n'.join(
        '[' + name + ']\n' + '\n'.join(key + ' = ' + toml_value(value)
                                      for key, value in values.items())
        for name, values in sections.items()) + '\n'
    sys.path.insert(0, str(vendor / 'src'))
    from codexsync.config import load_config
    if not config.exists():
        tomllib.loads(content)
        with tempfile.TemporaryDirectory(prefix='.setup-config-', dir=install) as temporary:
            candidate = Path(temporary) / 'candidate.toml'
            candidate.write_text(content, encoding='utf-8')
            load_config(candidate)
        save_once(config, content)
    raw = tomllib.loads(config.read_text(encoding='utf-8'))
    actual = load_config(config)
    required = [('sync', 'scope', 'full'), ('sync', 'direction', 'bidirectional'),
                ('sync', 'session_mode', 'all'),
                ('sync', 'delete_policy', 'never'), ('sync', 'dry_run_default', True),
                ('sync', 'close_codex', False), ('handoff', 'enabled', False),
                ('scheduler', 'enabled', False), ('scheduler', 'sync_at_login', False),
                ('scheduler', 'run_at_login', False), ('state_backup', 'at_login', False),
                ('state_backup', 'interval_hours', 0),
                ('safety', 'require_codex_stopped', True), ('safety', 'fail_on_unknown', True),
                ('targets', 'include_roots', ['sessions', 'archived_sessions', 'session_index.jsonl'])]
    for section, key, expected in required:
        if raw.get(section, {}).get(key) != expected:
            raise RuntimeError(f'Existing config retained, but {section}.{key} differs from safe setup profile.')
    if actual.paths.local_state_dir != codex.resolve() or actual.paths.workspace_root_dir != cloud.resolve():
        raise RuntimeError('Existing config paths differ from requested CodexHome/CloudRoot; retained without overwrite.')
    for actual_path, expected_path in (
        (actual.paths.backup_dir, install / 'overwrite-backups'),
        (actual.paths.temp_dir, install / 'tmp'),
        (actual.guardian.root_dir, install / 'guardian'),
        (actual.logging.file, install / 'logs' / 'codexsync.log'),
    ):
        if actual_path is None or actual_path.resolve() != expected_path.resolve():
            raise RuntimeError('Existing config local paths differ from safe setup profile; retained without overwrite.')
    for folder in ('backups', 'overwrite-backups', 'tmp', 'guardian', 'logs'):
        (install / folder).mkdir(exist_ok=True)
    output = command(python_exe, str(install / 'codexsync.py'), '-c', str(config), 'validate')
    print(output)
    print(json.dumps({'installed': str(install), 'config': str(config), 'vendor_commit': PIN,
                      'python': python_exe, 'machine_id': raw['identity']['machine_id'],
                      'automation_enabled': False, 'cloud_written': False, 'codex_state_written': False}))

try:
    main()
except Exception as exc:
    print(f'Setup failed: {exc}', file=sys.stderr)
    raise SystemExit(1)
'@
if (-not $SourceCheckout) { $SourceCheckout = '--clone' }
# Use stdin so Windows PowerShell cannot remove quotes from embedded Python code.
$installer | & $PythonExecutable - $SourceCheckout $InstallRoot $CloudRoot $CodexHome $MachineId
if ($LASTEXITCODE -ne 0) {
    throw "codexSync setup failed with exit code $LASTEXITCODE. No sync or automation was started."
}
