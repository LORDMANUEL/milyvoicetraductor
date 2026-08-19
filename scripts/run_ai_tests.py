#!/usr/bin/env python3
"""Ejecuta cada archivo de pruebas del motor en aislamiento y con límite duro.

El objetivo es mantener el CI diagnosticable: si una prueba se bloquea, se
informa el archivo exacto en vez de dejar detenidos Linux, Windows y la
verificación de fuente sin evidencia.
"""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
from pathlib import Path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tests-dir",
        default="services/ai/tests",
        help="Directorio que contiene módulos unittest test_*.py.",
    )
    parser.add_argument(
        "--pattern",
        default="test_*.py",
        help="Glob utilizado para seleccionar módulos de prueba.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="Segundos máximos permitidos para cada archivo de pruebas.",
    )
    return parser


def _terminate(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            process.kill()
        else:
            os.killpg(process.pid, signal.SIGKILL)
    except (OSError, ProcessLookupError):
        process.kill()


def _decode_output(payload: bytes) -> str:
    """Decodifica salida de tests Linux/Windows sin introducir U+FFFD evitable."""

    preferred = getattr(sys.stdout, "encoding", None) or "utf-8"
    attempted: set[str] = set()
    for encoding in ("utf-8-sig", preferred, "cp1252"):
        normalized = encoding.casefold()
        if normalized in attempted:
            continue
        attempted.add(normalized)
        try:
            return payload.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return payload.decode("utf-8", errors="backslashreplace")


def _write_output(text: str, *, error: bool = False) -> None:
    """Escribe incluso cuando la consola Windows usa CP1252."""

    if not text:
        return
    stream = sys.stderr if error else sys.stdout
    encoding = getattr(stream, "encoding", None) or "utf-8"
    try:
        safe = text.encode(encoding, errors="backslashreplace").decode(encoding)
    except LookupError:
        safe = text.encode("utf-8", errors="backslashreplace").decode("utf-8")
    stream.write(safe)
    stream.flush()


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.timeout <= 0:
        _write_output(
            "AI TEST RUNNER ERROR: --timeout debe ser mayor que cero\n", error=True
        )
        return 2

    root = Path(__file__).resolve().parents[1]
    tests_dir = (root / args.tests_dir).resolve()
    ai_root = (root / "services" / "ai").resolve()
    if not tests_dir.is_dir():
        _write_output(f"AI TEST RUNNER ERROR: no existe {tests_dir}\n", error=True)
        return 2

    files = sorted(path for path in tests_dir.glob(args.pattern) if path.is_file())
    if not files:
        _write_output("AI TEST RUNNER ERROR: no se encontraron pruebas\n", error=True)
        return 2

    environment = os.environ.copy()
    existing = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = str(ai_root) + (
        os.pathsep + existing if existing else ""
    )

    for index, path in enumerate(files, start=1):
        relative = path.relative_to(root)
        _write_output(f"\n=== AI TEST FILE {index}/{len(files)}: {relative} ===\n")
        command = [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            str(tests_dir),
            "-p",
            path.name,
            "-v",
        ]
        creationflags = 0
        start_new_session = os.name != "nt"
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        process = subprocess.Popen(
            command,
            cwd=root,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=False,
            start_new_session=start_new_session,
            creationflags=creationflags,
        )
        try:
            output, _ = process.communicate(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            _terminate(process)
            output, _ = process.communicate()
            _write_output(_decode_output(output or b""))
            _write_output(
                f"AI TEST TIMEOUT: {relative} excedió {args.timeout:g} segundos\n",
                error=True,
            )
            return 124
        _write_output(_decode_output(output or b""))
        if process.returncode != 0:
            _write_output(
                f"AI TEST FAILED: {relative} (exit {process.returncode})\n",
                error=True,
            )
            return int(process.returncode or 1)

    _write_output(f"\nAI TEST RUNNER OK: {len(files)} archivos\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
