"""Comprueba versiones del lockfile sin ejecutar scripts npm ni reinstalar."""
import json
from pathlib import Path
import sys


def installed(root):
    try:
        lock = json.loads((root / 'package-lock.json').read_text(encoding='utf-8-sig'))
        packages = lock.get('packages', {})
        if not packages or not (root / 'node_modules').is_dir():
            return False
        for relative, expected in packages.items():
            if not relative:
                continue
            if not relative.startswith('node_modules/') or '..' in Path(relative).parts:
                return False
            manifest = root / relative / 'package.json'
            if not manifest.is_file() and expected.get('optional'):
                continue
            actual = json.loads(manifest.read_text(encoding='utf-8-sig'))
            if expected.get('link') or actual.get('version') != expected.get('version'):
                return False
        return True
    except (OSError, ValueError, TypeError):
        return False


if __name__ == '__main__':
    raise SystemExit(0 if installed(Path(sys.argv[1])) else 1)
