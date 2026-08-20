"""Motor local de MilyVoiceTraductor.

El paquete mantiene dependencias pesadas detrás de imports diferidos para que
las tareas administrativas, diagnósticos y pruebas puedan ejecutarse sin
cargar Torch/Whisper en memoria.
"""

__version__ = "2.1.0"
