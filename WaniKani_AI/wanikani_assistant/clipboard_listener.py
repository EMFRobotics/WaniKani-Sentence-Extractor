# clipboard_listener.py
import time
import pyperclip
from typing import Generator

class ClipboardListener:
    """
    Simple clipboard listener using polling.
    Use: for text in ClipboardListener().listen(): ...
    """

    def __init__(self, poll_interval: float = 0.5):
        self._poll_interval = poll_interval
        try:
            self._last = pyperclip.paste()
        except Exception:
            self._last = None

    def listen(self) -> Generator[str, None, None]:
        """Generator yielding new clipboard text when it changes."""
        while True:
            try:
                current = pyperclip.paste()
            except Exception:
                current = None

            if current and current != self._last:
                self._last = current
                yield current
            time.sleep(self._poll_interval)

