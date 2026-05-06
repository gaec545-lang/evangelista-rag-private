"""Utilidades de hashing para detección de cambios en archivos."""
import hashlib
from pathlib import Path


def compute_file_hash(file_path: str | Path) -> str:
    """Calcula el hash MD5 de un archivo para detectar cambios."""
    path = Path(file_path)
    hasher = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_text_hash(text: str) -> str:
    """Calcula el hash MD5 de un string."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()
