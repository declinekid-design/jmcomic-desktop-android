from __future__ import annotations

import logging
import queue


class QueueLogHandler(logging.Handler):
    def __init__(self, events: queue.Queue):
        super().__init__()
        self.events = events

    def emit(self, record: logging.LogRecord) -> None:
        topic = str(getattr(record, "topic", "") or "")
        if topic.startswith(("image.before", "image.after", "req.")):
            return

        try:
            message = record.getMessage()
            prefix = f"[{topic}] " if topic else ""
            self.events.put(("log", record.levelno, prefix + message))
        except Exception:
            self.handleError(record)
