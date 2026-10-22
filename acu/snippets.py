"""Read the external snippet store; never launch scripts or acquire a desktop lease."""

import ctypes
import os
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

HEADER_KEYS = frozenset({"does", "args", "needs", "effect", "check", "tested"})


# Resolve the snippet store independently of ACU_HOME (which holds diagnostics).
def snippets_root() -> Path:
    return Path(os.environ.get("ACU_SNIPPETS_ROOT", Path.home() / ".ahk-computer-use" / "snippets")).resolve()


@dataclass(frozen=True)
class Snippet:
    """A script path and its index fields, shared by CLI and automatic discovery."""

    path: Path
    header: dict[str, str]


# Read only the leading semicolon-comment block, accepting UTF-8 with a BOM.
def read_snippet(path: Path) -> Snippet:
    header = {}
    with path.open(encoding="utf-8-sig") as source:
        for line in source:
            line = line.strip()
            if not line.startswith(";"):
                break
            key, separator, value = line[1:].partition(":")
            key = key.strip().casefold()
            if separator and key in HEADER_KEYS:
                header[key] = value.strip()
    return Snippet(path, header)


# Rank distinct, case-insensitive substring hits; without keywords, list every file.
def list_snippets(folder: Path, keywords: tuple[str, ...] | list[str] = ()) -> list[Snippet]:
    terms = {keyword.casefold() for keyword in keywords}
    ranked = []
    for path in folder.iterdir():
        if not path.is_file() or path.suffix.casefold() != ".ahk":
            continue
        snippet = read_snippet(path)
        text = "\n".join([path.name, *(f"{key}: {value}" for key, value in snippet.header.items())]).casefold()
        hits = sum(term in text for term in terms)
        if not terms or hits:
            ranked.append((hits, snippet))
    ranked.sort(key=lambda item: (-item[0], item[1].path.name.casefold(), item[1].path.name))
    return [snippet for _, snippet in ranked]


# Keep one canonical line format for explicit and automatic discovery.
def format_snippet(snippet: Snippet) -> str:
    if not snippet.header:
        return f"{snippet.path.name} | no header"
    return f"{snippet.path.name} | args: {snippet.header.get('args', '')} | does: {snippet.header.get('does', '')}"


# Include the absolute folder so an agent can construct an acu run path.
def format_snippets(folder: Path, snippets: list[Snippet]) -> str:
    return "\n".join([f"snippets {folder.resolve()}", *(format_snippet(snippet) for snippet in snippets)])


# Find a running executable without starting or interacting with any desktop app.
def running_executable(exe_name: str) -> Path | None:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    psapi.EnumProcesses.argtypes = [ctypes.POINTER(wintypes.DWORD), wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    psapi.EnumProcesses.restype = wintypes.BOOL
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    capacity = 1024
    while True:
        pids = (wintypes.DWORD * capacity)()
        used = wintypes.DWORD()
        if not psapi.EnumProcesses(pids, ctypes.sizeof(pids), ctypes.byref(used)):
            raise ctypes.WinError(ctypes.get_last_error())
        if used.value < ctypes.sizeof(pids):
            break
        capacity *= 2
    for pid in pids[:used.value // ctypes.sizeof(wintypes.DWORD)]:
        handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:  # Protected or exited processes cannot supply a path.
            continue
        try:
            size = wintypes.DWORD(32768)
            buffer = ctypes.create_unicode_buffer(size.value)
            if kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                path = Path(buffer.value)
                if path.name.casefold() == exe_name.casefold():
                    return path
        finally:
            kernel.CloseHandle(handle)
    return None


# App Paths covers installed apps that are not currently running, in both registry views.
def registered_executable(exe_name: str) -> Path | None:
    import winreg

    key = rf"Software\Microsoft\Windows\CurrentVersion\App Paths\{exe_name}"
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(hive, key, 0, winreg.KEY_READ | view) as entry:
                    value, _ = winreg.QueryValueEx(entry, None)
            except (FileNotFoundError, PermissionError):
                continue
            path = Path(os.path.expandvars(value).strip('"'))
            if path.is_file():
                return path
    return None


# Read localized FileDescription strings from the executable's version resource.
def file_description(path: Path) -> str:
    version = ctypes.WinDLL("version", use_last_error=True)
    version.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
    version.GetFileVersionInfoSizeW.restype = wintypes.DWORD
    version.GetFileVersionInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
    version.GetFileVersionInfoW.restype = wintypes.BOOL
    version.VerQueryValueW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.UINT)]
    version.VerQueryValueW.restype = wintypes.BOOL
    ignored = wintypes.DWORD()
    size = version.GetFileVersionInfoSizeW(str(path), ctypes.byref(ignored))
    if not size:  # Executables need not contain a version resource.
        return ""
    data = ctypes.create_string_buffer(size)
    if not version.GetFileVersionInfoW(str(path), 0, size, data):
        raise ctypes.WinError(ctypes.get_last_error())
    pointer = ctypes.c_void_p()
    length = wintypes.UINT()
    if not version.VerQueryValueW(data, r"\VarFileInfo\Translation", ctypes.byref(pointer), ctypes.byref(length)):
        return ""
    translations = ctypes.cast(pointer, ctypes.POINTER(wintypes.WORD))
    for index in range(0, length.value // 2, 2):
        key = rf"\StringFileInfo\{translations[index]:04x}{translations[index + 1]:04x}\FileDescription"
        value = ctypes.c_void_p()
        if version.VerQueryValueW(data, key, ctypes.byref(value), ctypes.byref(length)) and length.value:
            return ctypes.wstring_at(value.value, length.value).rstrip("\0")
    return ""


# Unresolvable folders remain searchable by exe name; running paths take precedence.
def exe_description(exe_name: str) -> str:
    if os.name != "nt":
        return ""
    path = running_executable(exe_name) or registered_executable(exe_name)
    return file_description(path) if path else ""


# CLI discovery stays separate from script execution and its desktop lease.
def list_for_app(app: str, keywords: list[str]) -> str:
    root = snippets_root()
    if not root.is_dir():
        return f"Snippets folder not found: {root}"
    folders = sorted((path for path in root.iterdir() if path.is_dir()), key=lambda path: (path.name.casefold(), path.name))
    query = app.casefold().removesuffix(".exe")
    matches = [folder for folder in folders
               if query in folder.name.casefold().removesuffix(".exe")
               or query in exe_description(folder.name).casefold()]
    if not matches:
        return "No snippet folder matches. Existing folders: " + (", ".join(folder.name for folder in folders) or "(none)")
    if len(matches) > 1:
        return "Several snippet folders match; choose one: " + ", ".join(folder.name for folder in matches)
    folder = matches[0]
    return format_snippets(folder, list_snippets(folder, keywords))
