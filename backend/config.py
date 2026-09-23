"""Small literal .env reader: no execution, interpolation or secret logging."""
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load_env(path=None, environ=None):
    path = Path(path) if path is not None else ROOT / '.env'
    env = os.environ if environ is None else environ
    if not path.exists():
        return
    values = {}
    for number, raw in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        key, separator, value = line.partition('=')
        key, value = key.strip(), value.strip()
        if not separator or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key):
            raise ValueError(f'Invalid .env syntax at line {number}; use KEY=value')
        if value.startswith(('"', "'")):
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError(f'Unclosed .env quote at line {number}')
            value = value[1:-1]
        if '\x00' in value:
            raise ValueError(f'Invalid .env character at line {number}')
        values[key] = value
    for key, value in values.items():
        env.setdefault(key, value)
