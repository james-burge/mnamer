from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from shutil import rmtree
from typing import Callable

from mnamer import tty
from mnamer.setting_store import SettingStore
from mnamer.target import Target
from mnamer.types import MessageType
from mnamer.utils import crawl_in, filter_blacklist, filter_containers


@dataclass(frozen=True)
class FileState:
    size: int
    mtime_ns: int


class Watcher:
    """Polls a directory and processes files once they have settled."""

    def __init__(
        self,
        settings: SettingStore,
        process_target: Callable[[Target], bool],
    ):
        self.settings = settings
        self.process_target = process_target
        self.watch_directory = settings.watch_input_directory
        if not self.watch_directory:
            raise RuntimeError("watch_input_directory must be configured for watch mode")
        self.poll_interval = max(1, int(settings.watch_poll_interval))
        self.settle_seconds = max(0, int(settings.watch_settle_seconds))
        self.cleanup_empty_source_dirs = bool(settings.cleanup_empty_source_dirs)
        self.cleanup_processed_source_dirs = bool(
            settings.cleanup_empty_source_dirs and settings.cleanup_processed_source_dirs
        )
        self._pending: dict[Path, tuple[FileState, float]] = {}
        self._attempted: dict[Path, FileState] = {}
        self._processed_dirs: set[Path] = set()

    def run(self) -> None:
        tty.msg(
            f"watching '{self.watch_directory}' (poll={self.poll_interval}s settle={self.settle_seconds}s)",
            MessageType.ALERT,
        )
        while True:
            self.run_once()
            time.sleep(self.poll_interval)

    def run_once(self) -> int:
        """One polling cycle. Returns number of files processed."""
        now = time.monotonic()
        processed = 0
        seen_paths = set()
        for file_path in self._iter_files():
            seen_paths.add(file_path)
            try:
                stat = file_path.stat()
            except OSError:
                continue
            state = FileState(size=stat.st_size, mtime_ns=stat.st_mtime_ns)
            if self._attempted.get(file_path) == state:
                continue
            previous = self._pending.get(file_path)
            if previous and previous[0] == state:
                first_seen = previous[1]
            else:
                first_seen = now
                self._pending[file_path] = (state, first_seen)
            if now - first_seen < self.settle_seconds:
                continue
            target = Target(file_path, self.settings)
            self.process_target(target)
            if not file_path.exists():
                self._processed_dirs.add(file_path.parent)
            self._attempted[file_path] = state
            self._pending.pop(file_path, None)
            processed += 1

        self._prune_missing(seen_paths)
        self._cleanup_processed_directories()
        return processed

    def _iter_files(self) -> list[Path]:
        file_paths = crawl_in([self.watch_directory], recurse=self.settings.watch_recursive)
        file_paths = filter_blacklist(file_paths, self.settings.ignore)
        file_paths = filter_containers(file_paths, self.settings.mask)
        return file_paths

    def _prune_missing(self, seen_paths: set[Path]) -> None:
        for file_path in tuple(self._pending):
            if file_path not in seen_paths:
                del self._pending[file_path]
        for file_path in tuple(self._attempted):
            if file_path not in seen_paths:
                del self._attempted[file_path]

    def _cleanup_processed_directories(self) -> None:
        if not self.cleanup_empty_source_dirs and not self.cleanup_processed_source_dirs:
            return
        watch_root = self.watch_directory.resolve()
        for directory in tuple(self._processed_dirs):
            if not directory.exists():
                self._processed_dirs.discard(directory)
                continue
            if directory.resolve() == watch_root:
                continue
            if self._has_masked_files(directory):
                continue
            try:
                if self.cleanup_processed_source_dirs:
                    rmtree(directory)
                    tty.msg(
                        f"deleted processed source directory '{directory}'",
                        MessageType.ALERT,
                    )
                elif self.cleanup_empty_source_dirs and not any(directory.iterdir()):
                    directory.rmdir()
                    tty.msg(
                        f"deleted empty source directory '{directory}'",
                        MessageType.ALERT,
                    )
            except OSError:
                continue
            self._processed_dirs.discard(directory)

    def _has_masked_files(self, directory: Path) -> bool:
        file_paths = crawl_in([directory], recurse=True)
        file_paths = filter_containers(file_paths, self.settings.mask)
        return any(file_paths)
