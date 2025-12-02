import threading
from pathlib import Path
from datetime import datetime


class _LoggerSingleton:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._file = Path("debug.log")
                cls._instance._write_lock = threading.Lock()
            return cls._instance

    def log(self, *args):
        msg = " ".join(str(a) for a in args)
        line = f"{datetime.now().isoformat()} | {msg}\n"

        with self._write_lock:
            with self._file.open("a", encoding="utf-8") as f:
                f.write(line)

Logger = _LoggerSingleton()
