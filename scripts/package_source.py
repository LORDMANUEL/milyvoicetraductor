#!/usr/bin/env python3
"""Crea un ZIP de fuente limpio; excluye pesos, cachés, secretos y builds."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import re, shutil, sys
ROOT=Path(__file__).resolve().parents[1]
VERSION=(ROOT/'VERSION').read_text().strip()
out=ROOT.parent/f'milyvoicetraductor-{VERSION}-source.zip'
blocked_names={'.git','node_modules','target','dist','__pycache__','.pytest_cache','.mypy_cache','models','cache','logs'}
blocked_suffixes={'.pyc','.pyo','.key','.pem','.pfx','.p12'}
secret=re.compile(r'(?i)(^|/)(\.env($|\.)|credentials|secrets)')
if out.exists(): out.unlink()
with ZipFile(out,'w',ZIP_DEFLATED,compresslevel=9) as z:
    for p in sorted(ROOT.rglob('*')):
        rel=p.relative_to(ROOT)
        if not p.is_file(): continue
        if any(part in blocked_names for part in rel.parts): continue
        if p.suffix.lower() in blocked_suffixes: continue
        if secret.search(rel.as_posix()) and rel.as_posix() != '.env.example': continue
        z.write(p,Path('milyvoicetraductor')/rel)
print(out)
