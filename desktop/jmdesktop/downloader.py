from __future__ import annotations

import queue
import threading

from .jm_bridge import JmDownloader


_BaseDownloader = JmDownloader or object


class DesktopDownloader(_BaseDownloader):
    def __init__(
        self,
        option,
        events: queue.Queue,
        photo_range: tuple[int, int] | None = None,
    ):
        super().__init__(option)
        self.events = events
        self.photo_range = photo_range
        self.total_images = 0
        self.completed_images = 0
        self.export_filepaths: list[str] = []
        self._progress_lock = threading.Lock()

    def do_filter(self, detail):
        if detail.is_album() and self.photo_range is not None:
            start, end = self.photo_range
            return detail[start:end]
        return detail

    def before_album(self, album) -> None:
        super().before_album(album)
        if self.photo_range is None:
            selected_count = len(album)
            self.total_images = max(int(album.page_count or 0), 0)
        else:
            start, end = self.photo_range
            selected_count = max(min(end, len(album)) - start, 0)
            self.total_images = 0
        self.completed_images = 0
        self.events.put(
            (
                "album",
                str(album.name),
                str(album.author),
                selected_count,
                self.total_images,
                len(album),
            )
        )

    def before_photo(self, photo) -> None:
        super().before_photo(photo)
        with self._progress_lock:
            if self.photo_range is not None:
                self.total_images += max(len(photo), 0)
        self.events.put(
            (
                "chapter",
                str(photo.name),
                int(photo.index),
                len(photo.from_album) if photo.from_album is not None else 1,
                len(photo),
            )
        )

    def after_image(self, image, img_save_path) -> None:
        super().after_image(image, img_save_path)
        with self._progress_lock:
            self.completed_images += 1
            completed = self.completed_images
            total = self.total_images
        self.events.put(("progress", completed, total))

    def record_export_filepath(self, detail, filepath: str) -> None:
        super().record_export_filepath(detail, filepath)
        self.export_filepaths.append(filepath)
        self.events.put(("export", filepath))
