from __future__ import annotations

import sys
from pathlib import Path

# El Python embebido de Windows usa python313._pth y por diseño no agrega
# automáticamente la carpeta del script a sys.path. Insertamos únicamente el
# directorio local del motor para que `mily_ai` sea importable sin depender de
# PYTHONPATH, del Python del sistema ni de rutas externas.
ENGINE_ROOT = Path(__file__).resolve().parent
engine_root_text = str(ENGINE_ROOT)
if engine_root_text not in sys.path:
    sys.path.insert(0, engine_root_text)

from mily_ai.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
