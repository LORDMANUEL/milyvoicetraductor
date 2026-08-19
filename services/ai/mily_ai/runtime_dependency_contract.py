"""Referencias estáticas para verificar el runtime privado de producción.

Este módulo no se importa por el hot path. Existe para que la auditoría de
fuente pueda asociar cada dependencia declarada con un import real sin cargar
Moonshine ni Hugging Face cuando arranca el motor ligero.
"""

import huggingface_hub as _huggingface_hub_runtime  # noqa: F401
import moonshine_voice as _moonshine_voice_runtime  # noqa: F401

__all__: tuple[str, ...] = ()
