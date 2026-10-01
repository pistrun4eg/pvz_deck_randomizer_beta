# -*- coding: utf-8 -*-
"""
Тонкий слой WinAPI для чтения/записи памяти чужого процесса (PvZ.exe).

Работает только на Windows. Никаких внешних зависимостей — только ctypes,
поэтому скрипт запускается простым `python pvz_randomizer.py` (от админа),
без pip и без Cheat Engine.
"""

import ctypes
import sys
from ctypes import wintypes

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
else:
    kernel32 = None  # ф-ни ниже всё равно вызовут _require_windows()


def _require_windows():
    if not IS_WINDOWS:
        raise RuntimeError(
            "Чтение памяти доступно только на Windows. "
            "Запускайте скрипт на том ПК, где стоит PvZ.")
    return kernel32

PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
PROCESS_QUERY_INFORMATION = 0x0400

TH32CS_SNAPPROCESS = 0x00000002


class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.ReadProcessMemory.argtypes = [
    wintypes.HANDLE, wintypes.LPCVOID, wintypes.LPVOID,
    ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t),
]
kernel32.WriteProcessMemory.argtypes = [
    wintypes.HANDLE, wintypes.LPVOID, wintypes.LPCVOID,
    ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t),
]


class MemoryError_(Exception):
    pass


def find_process(name):
    """Вернуть PID процесса. Принимает имя или список имён exe
    (регистронезависимо, можно без расширения — 'Plants' == 'Plants.exe').
    None если ничего не найдено."""
    _require_windows()
    names = name if isinstance(name, (list, tuple)) else [name]
    norm = set()
    for n in names:
        n = n.strip().lower()
        if not n.endswith(".exe"):
            n += ".exe"
        norm.add(n)
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    try:
        entry = PROCESSENTRY32()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
        if not kernel32.Process32First(snap, ctypes.byref(entry)):
            return None
        while True:
            if entry.szExeFile.lower() in norm:
                return int(entry.th32ProcessID)
            if not kernel32.Process32Next(snap, ctypes.byref(entry)):
                return None
    finally:
        kernel32.CloseHandle(snap)


def list_processes():
    """Список имён всех процессов — для диагностики ('какое имя у твоей игры?')."""
    _require_windows()
    result = []
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    try:
        entry = PROCESSENTRY32()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
        if not kernel32.Process32First(snap, ctypes.byref(entry)):
            return result
        while True:
            result.append(entry.szExeFile)
            if not kernel32.Process32Next(snap, ctypes.byref(entry)):
                break
    finally:
        kernel32.CloseHandle(snap)
    return result


def open_process(pid: int) -> wintypes.HANDLE:
    _require_windows()
    h = kernel32.OpenProcess(
        PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION
        | PROCESS_QUERY_INFORMATION, False, pid)
    if not h:
        raise MemoryError_(
            f"Не удалось открыть процесс {pid} (err={ctypes.get_last_error()}). "
            "Запусти скрипт от администратора."
        )
    return h


def read_bytes(h, addr: int, size: int) -> bytes:
    _require_windows()
    buf = ctypes.create_string_buffer(size)
    got = ctypes.c_size_t(0)
    ok = kernel32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, size,
                                    ctypes.byref(got))
    if not ok or got.value != size:
        raise MemoryError_(f"ReadProcessMemory провалился на 0x{addr:X}")
    return buf.raw


def write_bytes(h, addr: int, data: bytes):
    _require_windows()
    got = ctypes.c_size_t(0)
    ok = kernel32.WriteProcessMemory(h, ctypes.c_void_p(addr), data,
                                     len(data), ctypes.byref(got))
    if not ok or got.value != len(data):
        raise MemoryError_(f"WriteProcessMemory провалился на 0x{addr:X}")


def read_int(h, addr: int) -> int:
    import struct
    return struct.unpack("<i", read_bytes(h, addr, 4))[0]


def write_int(h, addr: int, value: int):
    import struct
    write_bytes(h, addr, struct.pack("<i", int(value)))


def read_pointer_chain(h, base: int, offsets):
    """Классический CE-цепочек: [[base]+o1]+o2 ... Вернуть итоговый адрес."""
    addr = base
    for off in offsets:
        addr = read_int(h, addr) + off
    return addr
