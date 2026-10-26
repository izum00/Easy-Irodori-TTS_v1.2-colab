"""RAM / VRAM release helpers (Linux / Colab)."""
from __future__ import annotations

import ctypes
import gc


def _meminfo_gb(field: str) -> float:
    try:
        with open("/proc/meminfo", encoding="ascii") as stream:
            for line in stream:
                if line.startswith(field + ":"):
                    return int(line.split()[1]) / 1024 / 1024
    except (OSError, ValueError):
        pass
    return 0.0


def process_gb() -> float:
    """RAM used by this app process (resident set size)."""
    try:
        with open("/proc/self/status", encoding="ascii") as stream:
            for line in stream:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024 / 1024
    except (OSError, ValueError):
        pass
    return 0.0


def release() -> None:
    """Free Python garbage, the CUDA cache, and return freed heap pages to the OS."""
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
    except Exception:
        pass
    gc.collect()
    try:
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except Exception:
        pass


def summary(before: float | None = None) -> str:
    total = _meminfo_gb("MemTotal")
    available = _meminfo_gb("MemAvailable")
    text = f"RAM: アプリ {process_gb():.1f}GB / 空き {available:.1f}GB（全体 {total:.1f}GB）"
    if before is not None:
        text = f"RAM解放: {before:.1f}GB → {process_gb():.1f}GB（アプリ使用量）\n" + text
    try:
        import torch
        if torch.cuda.is_available():
            used = torch.cuda.memory_reserved() / 1024 ** 3
            all_gpu = torch.cuda.get_device_properties(0).total_memory / 1024 ** 3
            text += f"\nVRAM: 確保 {used:.1f}GB / {all_gpu:.1f}GB"
    except Exception:
        pass
    return text
