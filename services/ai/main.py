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

# BetaAlpha Lite excluye Torch/Transformers. Antes de importar el CLI instalamos
# el preparador Marian nativo para que OPUS-MT se convierta con CTranslate2
# directamente desde sus pesos Marian originales.
from mily_ai.betaalpha_native_marian import (  # noqa: E402
    install_betaalpha_native_marian_patch,
)

install_betaalpha_native_marian_patch()

from mily_ai.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
