#!/usr/bin/env python3
from pathlib import Path
import json, hashlib
ROOT=Path(__file__).resolve().parents[1]
version=(ROOT/'VERSION').read_text().strip()
payload={
 'schemaVersion':1,'version':version,'channel':'rc','artifacts':[],
 'notes':'Release candidate local. Los binarios publicados deben firmarse en CI antes de distribución.'
}
out=ROOT/'dist'/'update-manifest.template.json'; out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n')
print(out)
