"""Reutiliza token-saver si la version instalada coincide con la fuente incluida."""
import ast
import importlib.metadata
from pathlib import Path
import sys


def source_version(root):
    tree = ast.parse((root / 'src/__init__.py').read_text(encoding='utf-8-sig'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '__version__' for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError('Version de token-saver ausente.')


if __name__ == '__main__':
    try:
        ready = importlib.metadata.version('token-saver') == source_version(Path(sys.argv[1]))
    except (OSError, ValueError, importlib.metadata.PackageNotFoundError):
        ready = False
    raise SystemExit(0 if ready else 1)
