"""Pruebas locales: sin instalacion del sistema, red ni reinicios."""
from contextlib import closing
import importlib.util
from pathlib import Path
import shutil
import sqlite3
import tempfile
import tomllib
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


setup = load('configurar_pc3')
package = load('crear_paquete_pc3')


class InstallerTests(unittest.TestCase):
    def test_full_template_preserves_plugins_and_expands_paths(self):
        previous = Path.home() / 'Desktop/Migracion_Codex_Limpia_v4.zip'
        with zipfile.ZipFile(previous) as archive:
            base = tomllib.loads(archive.read('config.toml').decode('utf-8-sig'))
        shared = tomllib.loads((ROOT / 'config_compartida/config.toml').read_text(encoding='utf-8-sig'))
        base['mcp_servers']['antigravity_bridge'] = shared['mcp_servers']['antigravity_bridge']
        import tomlkit
        with patch.dict('os.environ', {'CODEX_APP_DIR': 'C:/Apps/Codex/app',
                                      'DRIVE_ROOT': 'J:/Mi unidad', 'LOCALAPPDATA': 'C:/Users/Nuevo/AppData/Local'}):
            rendered = setup.render_config(tomlkit.dumps(base), None, Path('C:/Users/Nuevo'), Path('C:/dos_agentes_local'))
        result = tomllib.loads(rendered)
        self.assertEqual(len(result['plugins']), len(base['plugins']))
        self.assertEqual(set(result['mcp_servers']), {'node_repl', 'cua_repl', 'antigravity_bridge'})
        self.assertNotIn('%USERPROFILE%', rendered)
        self.assertNotIn('%DOS_AGENTES_HOME%', rendered)
        self.assertNotIn('%CODEX_APP_DIR%', rendered)
        self.assertEqual(len(result['notify']), 2)

    def test_merge_preserves_notify_and_other_mcp(self):
        template = (ROOT / 'config_compartida/config.toml').read_text(encoding='utf-8-sig')
        old = 'notify=["cmd", "/c", "echo listo"]\n[mcp_servers.otro]\ncommand="ejemplo"\n'
        result = setup.render_config(template, old, Path('C:/Users/Usuario nuevo'), Path('C:/dos_agentes_local'))
        parsed = tomllib.loads(result)
        self.assertEqual(parsed['notify'], ['cmd', '/c', 'echo listo'])
        self.assertEqual(parsed['mcp_servers']['otro']['command'], 'ejemplo')
        self.assertNotIn('%USERPROFILE%', result)
        self.assertNotIn('H_P', result)
        self.assertIn('Usuario nuevo', parsed['mcp_servers']['antigravity_bridge']['args'][2])

    def test_duplicate_notify_rejected(self):
        template = (ROOT / 'config_compartida/config.toml').read_text(encoding='utf-8-sig')
        with self.assertRaises(tomllib.TOMLDecodeError):
            setup.render_config(template, 'notify=[]\nnotify=[]\n', Path('C:/Users/Nuevo'), ROOT)

    def test_clean_db_and_existing_credentials_preserved(self):
        with tempfile.TemporaryDirectory(prefix='codex-v5-unit-') as temporary:
            base = Path(temporary)
            root, home = base / 'root', base / 'user'
            shutil.copytree(ROOT / 'config_compartida', root / 'config_compartida')
            export = root / 'auth_c1.json'
            export.write_text('{"fixture":"cuenta1"}', encoding='utf-8')
            setup.configure(root, home)
            first_auth = (home / '.codex/auth.json').read_bytes()
            self.assertEqual(first_auth, export.read_bytes())
            export.write_text('{"fixture":"otra-sesion"}', encoding='utf-8')
            token = home / '.antigravity-agent/local_bridge_token'
            first_token = token.read_bytes()
            config = home / '.codex/config.toml'
            first_config = config.read_bytes()
            with closing(sqlite3.connect(root / 'estado_puente.db')) as con, con:
                self.assertEqual(con.execute('select count(*) from config_chats').fetchone()[0], 0)
                con.execute('insert into config_chats values (?,?)', ('DOS_AGENTES', 'https://gemini.google.com/app/prueba'))
            setup.configure(root, home)
            self.assertEqual(first_config, config.read_bytes())
            self.assertEqual(first_token, token.read_bytes())
            self.assertEqual(first_auth, (home / '.codex/auth.json').read_bytes())
            with closing(sqlite3.connect(root / 'estado_puente.db')) as con:
                self.assertEqual(con.execute('select count(*) from config_chats').fetchone()[0], 1)

    def test_package_excludes_private_and_runtime_files(self):
        for path in ('auth.json', 'x/auth_c1.json', 'x/state.db', 'x/state.db-journal',
                     'logs/a.txt', 'node_modules/a.js', '.venv/Scripts/python.exe',
                     'chrome_gemini_profile/Default/Cookies', '.antigravity-agent/gui_config.json',
                     '__pycache__/test.pyc', 'config_backups/AGENTS.md', 'sesion.jsonl',
                     'script_bak_123.py'):
            with self.subTest(path=path):
                self.assertFalse(package.allowed(path))
        for path in ('bridge_server.py', 'config_compartida/config.toml', 'chat_fijo_gemini.py', 'auth_c1.json', 'auth_c2.json'):
            self.assertTrue(package.allowed(path))
        self.assertTrue(package.allowed('repos_referencia/token-saver/pyproject.toml'))
        self.assertFalse(package.allowed('codex/plugins/.plugin-appserver/codex.exe'))


if __name__ == '__main__':
    unittest.main()
