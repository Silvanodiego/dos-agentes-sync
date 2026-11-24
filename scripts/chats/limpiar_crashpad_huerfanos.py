"""Retira solo reportadores Crashpad huerfanos persistentes de Codex MSIX."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import re
import subprocess
import time


def eligible(snapshot, program_files):
    records = {p['pid']: p for p in snapshot}
    prefix = str(Path(program_files) / 'WindowsApps').replace('\\', '/')
    pattern = re.compile(re.escape(prefix) + r'/OpenAI\.Codex_[^/]+/app/ChatGPT\.exe$', re.I)

    def handler(p):
        return (p.get('kind') == 'crashpad-handler' and isinstance(p.get('born'), int)
                and bool(pattern.fullmatch((p.get('path') or '').replace('\\', '/'))))

    result = []
    for p in snapshot:
        cursor = p
        seen = set()
        while handler(cursor) and cursor['pid'] not in seen:
            seen.add(cursor['pid'])
            parent = records.get(cursor['parent'])
            if parent is None:
                # A mixed descendant tree is unknown, not disposable.
                descendants = set(seen)
                changed = True
                while changed:
                    changed = False
                    for child in snapshot:
                        if child['parent'] in descendants and child['pid'] not in descendants:
                            descendants.add(child['pid'])
                            changed = True
                if all(handler(records[i]) and
                       (records[i]['parent'] not in records or
                        (handler(records[records[i]['parent']]) and
                         records[records[i]['parent']]['born'] <= records[i]['born']))
                       for i in descendants):
                    result.append(p)
                break
            # Reused parent PIDs are deliberately treated as unknown/active.
            if not handler(parent) or parent['born'] > cursor['born']:
                break
            cursor = parent
    return result


def snapshot():
    script = r'''
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$rows = @(Get-CimInstance Win32_Process | ForEach-Object {
    $kind = ''
    if ($_.Name -eq 'ChatGPT.exe' -and $_.CommandLine -match '(?:^|\s)--type=([^\s"]+)') { $kind = $Matches[1] }
    [pscustomobject]@{pid=[int]$_.ProcessId; parent=[int]$_.ParentProcessId;
        path=$_.ExecutablePath; kind=$kind; born=if ($_.CreationDate) {$_.CreationDate.ToFileTimeUtc()} else {$null}}
})
ConvertTo-Json -InputObject $rows -Compress
'''
    completed = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
        capture_output=True, text=True, encoding='utf-8', errors='strict', check=True,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), timeout=30)
    return json.loads(completed.stdout)


def cleanup(root):
    current = eligible(snapshot(), os.environ['ProgramFiles'])
    observation_path = root / 'orphan-crashpad-observations.json'
    previous = json.loads(observation_path.read_text(encoding='utf-8')) if observation_path.exists() else {}
    now = time.time()
    observed = {}
    for p in current:
        key = str(p['pid']) + ':' + str(p['born'])
        observed[key] = previous.get(key, now)
    observation_path.write_text(json.dumps(observed), encoding='utf-8')
    stale = [p for p in current if now - observed[str(p['pid']) + ':' + str(p['born'])] >= 120]
    if not stale:
        return []
    # Second full snapshot verifies command type and orphan ancestry immediately
    # before opening handles. No bare-name ChatGPT termination is permitted.
    fresh = {p['pid']: p for p in eligible(snapshot(), os.environ['ProgramFiles'])}
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel.GetProcessTimes.restype = wintypes.BOOL
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.TerminateProcess.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handles = []
    terminated = []
    try:
        # Fix all handles before terminating anything, protecting against PID reuse.
        for p in stale:
            if fresh.get(p['pid']) != p:
                continue
            handle = kernel.OpenProcess(0x1000 | 0x0001, False, p['pid'])
            if not handle:
                raise OSError('No se pudo verificar el reportador; no se termina ningun proceso')
            handles.append((p, handle))
            times = [wintypes.FILETIME() for _ in range(4)]
            if not kernel.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
                raise OSError('No se pudo verificar la identidad del reportador')
            born = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
            buffer = ctypes.create_unicode_buffer(32768)
            size = wintypes.DWORD(len(buffer))
            if (abs(born - p['born']) > 10 or
                not kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)) or
                buffer.value.casefold() != p['path'].casefold()):
                raise OSError('Identidad de proceso cambio; limpieza suspendida')
        for p, handle in reversed(handles):
            if kernel.TerminateProcess(handle, 0):
                terminated.append(p['pid'])
        return terminated
    finally:
        for _, handle in handles:
            kernel.CloseHandle(handle)
