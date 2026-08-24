from __future__ import annotations

import sys

from .control import serve_stream
from .host import EngineHost


def main() -> int:
    serve_stream(EngineHost(), sys.stdin, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
