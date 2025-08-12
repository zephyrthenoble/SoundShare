"""Project-wide constants and simple predicates."""
from __future__ import annotations
import os
from typing import List

# Supported audio file extensions (lowercase, with leading dot)
AUDIO_EXTENSIONS: set[str] = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".wma"}

def is_supported_audio_extension(path: str) -> bool:
    """Return True if path has a supported audio extension."""
    idx = path.rfind('.')
    if idx == -1:
        return False
    return path[idx:].lower() in AUDIO_EXTENSIONS

def find_audio_files(root: str, recursive: bool = True, *, skip_zero_length: bool = True) -> List[str]:
    """Locate audio files under root respecting recursion and size filtering."""
    found: list[str] = []
    if recursive:
        for dirpath, _, filenames in os.walk(root):
            for name in filenames:
                if is_supported_audio_extension(name):
                    full = os.path.join(dirpath, name)
                    if skip_zero_length:
                        try:
                            if os.path.getsize(full) == 0:
                                continue
                        except OSError:
                            continue
                    found.append(full)
    else:
        try:
            for name in os.listdir(root):
                full = os.path.join(root, name)
                if os.path.isfile(full) and is_supported_audio_extension(name):
                    if skip_zero_length:
                        try:
                            if os.path.getsize(full) == 0:
                                continue
                        except OSError:
                            continue
                    found.append(full)
        except OSError:
            return []
    return found

__all__ = ["AUDIO_EXTENSIONS", "is_supported_audio_extension", "find_audio_files"]
