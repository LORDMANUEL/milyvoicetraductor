#!/usr/bin/env python3
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
ROOT=Path(__file__).resolve().parents[1]
src=ROOT/'apps'/'extension'
out=ROOT/'dist'/'MilyVoiceTraductor-Chromium-Extension.zip'
out.parent.mkdir(exist_ok=True)
with ZipFile(out,'w',ZIP_DEFLATED) as z:
    for p in sorted(src.rglob('*')):
        if p.is_file(): z.write(p,p.relative_to(src))
print(out)
