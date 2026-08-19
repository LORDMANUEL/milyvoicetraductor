"""Medición sin dependencias del árbol de procesos de MilyVoice.

Los motores nativos pueden vivir en sidecars persistentes. Medir únicamente el
Python padre permitiría superar silenciosamente el contrato de 2 GiB, por lo que
esta capa agrega el working set del proceso raíz y todos sus descendientes.
"""

from __future__ import annotations

import ctypes
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True, slots=True)
class ProcessTreeMemorySnapshot:
    current_mb: float
    peak_mb: float
    process_count: int

    def __post_init__(self) -> None:
        if self.process_count < 0:
            raise ValueError("process_count no puede ser negativo")
        for value in (self.current_mb, self.peak_mb):
            if not math.isfinite(float(value)) or float(value) < 0:
                raise ValueError("La memoria debe ser finita y no negativa")
        if self.peak_mb < self.current_mb:
            raise ValueError("El pico no puede ser menor que el uso actual")


def descendant_pids(root_pid: int, parent_by_pid: Mapping[int, int]) -> set[int]:
    """Devuelve raíz + descendientes, tolerando procesos que desaparecen/ciclos."""

    root = int(root_pid)
    if root <= 0:
        raise ValueError("root_pid debe ser positivo")
    children: dict[int, list[int]] = {}
    for raw_pid, raw_parent in parent_by_pid.items():
        pid, parent = int(raw_pid), int(raw_parent)
        if pid <= 0 or parent < 0 or pid == parent:
            continue
        children.setdefault(parent, []).append(pid)
    seen = {root}
    pending = [root]
    while pending:
        parent = pending.pop()
        for child in children.get(parent, ()):
            if child in seen:
                continue
            seen.add(child)
            pending.append(child)
    return seen


def aggregate_process_tree(
    root_pid: int,
    parent_by_pid: Mapping[int, int],
    memory_by_pid: Mapping[int, tuple[float, float]],
) -> ProcessTreeMemorySnapshot:
    """Agrega inventario inyectable; facilita tests sin depender del SO."""

    current_total = 0.0
    peak_total = 0.0
    measured = 0
    for pid in descendant_pids(root_pid, parent_by_pid):
        values = memory_by_pid.get(pid)
        if values is None:
            continue
        current, peak = (float(values[0]), float(values[1]))
        if not all(
            math.isfinite(value) and value >= 0 for value in (current, peak)
        ):
            continue
        current_total += current
        peak_total += max(current, peak)
        measured += 1
    return ProcessTreeMemorySnapshot(
        current_mb=current_total,
        peak_mb=max(current_total, peak_total),
        process_count=measured,
    )


def _parse_linux_status(path: Path) -> tuple[int, float, float] | None:
    try:
        parent = 0
        current_kib = 0.0
        peak_kib = 0.0
        for line in path.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines():
            if line.startswith("PPid:"):
                parent = int(line.split(":", 1)[1].strip().split()[0])
            elif line.startswith("VmRSS:"):
                current_kib = float(line.split(":", 1)[1].strip().split()[0])
            elif line.startswith("VmHWM:"):
                peak_kib = float(line.split(":", 1)[1].strip().split()[0])
        current = current_kib / 1024.0
        peak = max(current, peak_kib / 1024.0)
        return parent, current, peak
    except (OSError, ValueError, IndexError):
        return None


def _linux_snapshot(root_pid: int) -> ProcessTreeMemorySnapshot:
    parent_by_pid: dict[int, int] = {}
    memory_by_pid: dict[int, tuple[float, float]] = {}
    proc = Path("/proc")
    try:
        entries = tuple(proc.iterdir())
    except OSError:
        entries = ()
    for entry in entries:
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        parsed = _parse_linux_status(entry / "status")
        if parsed is None:
            continue
        parent, current, peak = parsed
        parent_by_pid[pid] = parent
        memory_by_pid[pid] = (current, peak)
    snapshot = aggregate_process_tree(root_pid, parent_by_pid, memory_by_pid)
    if snapshot.process_count:
        return snapshot
    return _fallback_snapshot()


def _windows_inventory() -> tuple[dict[int, int], set[int]]:
    from ctypes import wintypes

    class ProcessEntry32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_snapshot = kernel32.CreateToolhelp32Snapshot
    create_snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    create_snapshot.restype = wintypes.HANDLE
    first = kernel32.Process32FirstW
    first.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry32W)]
    first.restype = wintypes.BOOL
    next_process = kernel32.Process32NextW
    next_process.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry32W)]
    next_process.restype = wintypes.BOOL
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL

    handle = create_snapshot(0x00000002, 0)
    invalid_handle = ctypes.c_void_p(-1).value
    if not handle or int(handle) == int(invalid_handle):
        return {}, set()
    parents: dict[int, int] = {}
    pids: set[int] = set()
    entry = ProcessEntry32W()
    entry.dwSize = ctypes.sizeof(entry)
    try:
        ok = bool(first(handle, ctypes.byref(entry)))
        while ok:
            pid = int(entry.th32ProcessID)
            if pid > 0:
                pids.add(pid)
                parents[pid] = int(entry.th32ParentProcessID)
            entry.dwSize = ctypes.sizeof(entry)
            ok = bool(next_process(handle, ctypes.byref(entry)))
    finally:
        close_handle(handle)
    return parents, pids


def _windows_process_memory(pid: int) -> tuple[float, float] | None:
    from ctypes import wintypes

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    open_process = kernel32.OpenProcess
    open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    open_process.restype = wintypes.HANDLE
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL
    get_info = psapi.GetProcessMemoryInfo
    get_info.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ProcessMemoryCounters),
        wintypes.DWORD,
    ]
    get_info.restype = wintypes.BOOL

    handle = open_process(0x0400 | 0x0010, False, int(pid))
    if not handle:
        handle = open_process(0x1000, False, int(pid))
    if not handle:
        return None
    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    try:
        if not get_info(handle, ctypes.byref(counters), counters.cb):
            return None
        divisor = 1024.0 * 1024.0
        current = float(counters.WorkingSetSize) / divisor
        peak = max(current, float(counters.PeakWorkingSetSize) / divisor)
        return current, peak
    finally:
        close_handle(handle)


def _windows_snapshot(root_pid: int) -> ProcessTreeMemorySnapshot:
    try:
        parents, pids = _windows_inventory()
        descendants = descendant_pids(root_pid, parents)
        memory = {
            pid: values
            for pid in descendants.intersection(pids | {root_pid})
            if (values := _windows_process_memory(pid)) is not None
        }
        snapshot = aggregate_process_tree(root_pid, parents, memory)
        if snapshot.process_count:
            return snapshot
    except (AttributeError, OSError, ValueError):
        pass
    return _fallback_snapshot()


def _fallback_snapshot() -> ProcessTreeMemorySnapshot:
    try:
        import resource

        raw = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        peak = raw / (
            1024.0 * 1024.0 if sys.platform == "darwin" else 1024.0
        )
        return ProcessTreeMemorySnapshot(peak, peak, 1)
    except (ImportError, OSError, ValueError):
        return ProcessTreeMemorySnapshot(0.0, 0.0, 0)


def process_tree_memory_snapshot_mb(
    root_pid: int | None = None,
) -> ProcessTreeMemorySnapshot:
    """Mide el proceso indicado y sus sidecars descendientes."""

    root = int(root_pid or os.getpid())
    if root <= 0:
        raise ValueError("root_pid debe ser positivo")
    if os.name == "nt":
        return _windows_snapshot(root)
    if Path("/proc").is_dir():
        return _linux_snapshot(root)
    return _fallback_snapshot()
