"""Verify standalone payload without touching real tasks, home, repo or credentials."""
import base64
import hashlib
import io
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
import zipfile

import crear_reparacion_chats as builder

ROOT = Path(__file__).resolve().parent.parent


class RepairTests(unittest.TestCase):
    def build(self, folder):
        bat = folder / 'repair.bat'
        builder.build(ROOT, bat)
        content = bat.read_text(encoding='ascii')
        payload = base64.b64decode(re.search(r"\$payload = '([^']+)'", content)[1])
        return bat, content, payload

    def test_allowlist_complete_and_checksum_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, content, payload = self.build(Path(tmp))
            self.assertIn(hashlib.sha256(payload).hexdigest(), content)
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                self.assertEqual(set(archive.namelist()), {'scripts/chats/' + n for n in builder.FILES})
                for name in builder.FILES:
                    self.assertEqual(archive.read('scripts/chats/' + name), (ROOT / 'scripts/chats' / name).read_bytes())
            self.assertNotIn('git pull', builder.BODY)
            self.assertNotIn('Stop-Process', builder.BODY)

    def test_extract_repeat_and_preserve_modified_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            _, content, payload = self.build(folder)
            code = content.split('# POWERSHELL_START\n', 1)[1]
            code = code.replace("& (Join-Path $runner 'scripts\\chats\\reparar_aislado.ps1')", "Write-Host 'EXTRACTION_VERIFIED'")
            code = "$env:LOCALAPPDATA = '" + str(folder).replace("'", "''") + "'\n" + code
            script = folder / 'extract.ps1'
            script.write_text(code, encoding='utf-8-sig')
            def run():
                return subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script)], capture_output=True, text=True, errors='replace', timeout=30)
            for _ in range(2):
                result = run()
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('EXTRACTION_VERIFIED', result.stdout)
            runner = folder / 'CodexSync' / ('runner-' + hashlib.sha256(payload).hexdigest()[:16])
            worker = runner / 'scripts/chats/sync_chats_abierto.py'
            worker.write_text('local modification', encoding='ascii')
            result = run()
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(worker.read_text(), 'local modification')
            self.assertNotIn('EXTRACTION_VERIFIED', result.stdout)

    def test_powershell_51_syntax_all_payload_scripts(self):
        paths = [ROOT / 'scripts/chats' / n for n in builder.FILES if n.endswith('.ps1')]
        code = "$allErrors = @(); foreach ($p in @(" + ','.join("'" + str(p).replace("'", "''") + "'" for p in paths) + ")) { $tokens=$null; $errors=$null; [System.Management.Automation.Language.Parser]::ParseFile($p,[ref]$tokens,[ref]$errors) | Out-Null; $allErrors += $errors }; if ($allErrors.Count) { $allErrors | Out-String | Write-Output; exit 1 }"
        result = subprocess.run(['powershell.exe', '-NoProfile', '-Command', code], capture_output=True, text=True, errors='replace', timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
