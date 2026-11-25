"""Valida sintaxis sin importar ni ejecutar los servicios protegidos."""
import ast
from pathlib import Path
import sys

root = Path(sys.argv[1])
for name in ('bridge_server.py', 'consultar_gemini.py', 'bucle_autonomo.py'):
    path = root / name
    ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))
print('Sintaxis de scripts protegidos: correcta (no se ejecutaron).')
