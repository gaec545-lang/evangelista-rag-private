"""File watcher sobre el Obsidian Vault para re-ingesta automática."""
import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from src.utils.logger import get_logger

logger = get_logger(__name__)

DEBOUNCE_SECONDS = 2.0


class VaultEventHandler(FileSystemEventHandler):
    """Maneja eventos de sistema de archivos del vault con debounce."""

    def __init__(self, ingest_callback, delete_callback) -> None:
        super().__init__()
        self._ingest_callback = ingest_callback
        self._delete_callback = delete_callback
        self._pending: dict[str, float] = {}

    def _should_process(self, path: str) -> bool:
        """Verifica si el archivo debe procesarse según las reglas del vault."""
        p = Path(path)
        if not p.suffix == ".md":
            return False
        for part in p.parts:
            if part == "_templates":
                return False
            if part == "_meta":
                return False
            if part.startswith("."):
                return False
        name = p.name
        if name.startswith("_") and not name.startswith("_moc-"):
            return False
        return True

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory or not self._should_process(event.src_path):
            return
        self._pending[event.src_path] = time.time()
        logger.info("archivo_modificado_detectado", path=event.src_path)

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory or not self._should_process(event.src_path):
            return
        self._pending[event.src_path] = time.time()
        logger.info("archivo_creado_detectado", path=event.src_path)

    def on_deleted(self, event: FileSystemEvent) -> None:
        if event.is_directory or not self._should_process(event.src_path):
            return
        logger.info("archivo_eliminado_detectado", path=event.src_path)
        self._delete_callback(event.src_path)

    def flush_pending(self) -> list[str]:
        """Retorna rutas con cambios pendientes que superaron el debounce."""
        now = time.time()
        ready = [p for p, t in self._pending.items() if now - t >= DEBOUNCE_SECONDS]
        for p in ready:
            del self._pending[p]
        return ready


class VaultWatcher:
    """Observa el vault en tiempo real y re-ingesta archivos modificados."""

    def __init__(self, vault_path: str, ingest_callback, delete_callback) -> None:
        self.vault_path = vault_path
        self._handler = VaultEventHandler(ingest_callback, delete_callback)
        self._observer = Observer()

    def start(self) -> None:
        """Inicia el observer de watchdog."""
        self._observer.schedule(self._handler, self.vault_path, recursive=True)
        self._observer.start()
        logger.info("watcher_iniciado", vault=self.vault_path)

    def stop(self) -> None:
        """Detiene el observer."""
        self._observer.stop()
        self._observer.join()
        logger.info("watcher_detenido")

    def get_pending(self) -> list[str]:
        """Retorna archivos pendientes de re-ingesta."""
        return self._handler.flush_pending()
