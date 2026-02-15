from pathlib import Path

import pytest

from mnamer.setting_store import SettingStore
from mnamer.watcher import Watcher

pytestmark = pytest.mark.local


def test_watcher__missing_watch_directory():
    settings = SettingStore(watch_enabled=True)
    with pytest.raises(RuntimeError):
        Watcher(settings, lambda target: True)


def test_watcher__run_once_processes_file_once(tmp_path: Path):
    media_file = tmp_path / "show.s01e01.mkv"
    media_file.write_text("test")
    seen = []
    settings = SettingStore(
        watch_enabled=True,
        watch_input_directory=tmp_path,
        watch_settle_seconds=0,
    )
    watcher = Watcher(settings, lambda target: seen.append(target.source) or True)

    assert watcher.run_once() == 1
    assert watcher.run_once() == 0
    assert seen == [media_file]


def test_watcher__waits_for_settle_time(tmp_path: Path, monkeypatch):
    media_file = tmp_path / "show.s01e01.mkv"
    media_file.write_text("test")
    seen = []
    settings = SettingStore(
        watch_enabled=True,
        watch_input_directory=tmp_path,
        watch_settle_seconds=10,
    )
    watcher = Watcher(settings, lambda target: seen.append(target.source) or True)

    ticks = iter([0.0, 5.0, 11.0])
    monkeypatch.setattr("mnamer.watcher.time.monotonic", lambda: next(ticks))

    assert watcher.run_once() == 0
    assert watcher.run_once() == 0
    assert watcher.run_once() == 1
    assert seen == [media_file]


def test_watcher__cleanup_empty_source_dir_after_processed_move(tmp_path: Path):
    source_dir = tmp_path / "drop" / "release"
    source_dir.mkdir(parents=True)
    media_file = source_dir / "show.s01e01.mkv"
    media_file.write_text("test")
    settings = SettingStore(
        watch_enabled=True,
        watch_input_directory=tmp_path / "drop",
        watch_recursive=True,
        watch_settle_seconds=0,
        cleanup_empty_source_dirs=True,
    )

    def process_target(target):
        target.source.unlink()
        return True

    watcher = Watcher(settings, process_target)
    assert watcher.run_once() == 1
    assert not source_dir.exists()


def test_watcher__dangerous_cleanup_deletes_processed_dir_contents(tmp_path: Path):
    source_dir = tmp_path / "drop" / "release"
    source_dir.mkdir(parents=True)
    media_file = source_dir / "show.s01e01.mkv"
    media_file.write_text("test")
    (source_dir / "release.nfo").write_text("notes")
    screens = source_dir / "Screens"
    screens.mkdir()
    (screens / "screen1.jpg").write_text("image")
    settings = SettingStore(
        watch_enabled=True,
        watch_input_directory=tmp_path / "drop",
        watch_recursive=True,
        watch_settle_seconds=0,
        cleanup_empty_source_dirs=True,
        cleanup_processed_source_dirs=True,
    )

    def process_target(target):
        target.source.unlink()
        return True

    watcher = Watcher(settings, process_target)
    assert watcher.run_once() == 1
    assert not source_dir.exists()


def test_watcher__dangerous_cleanup_skips_folders_without_mask_matches(tmp_path: Path):
    untouched_dir = tmp_path / "drop" / "nonmedia"
    untouched_dir.mkdir(parents=True)
    (untouched_dir / "readme.txt").write_text("text")
    (untouched_dir / "info.nfo").write_text("info")
    settings = SettingStore(
        watch_enabled=True,
        watch_input_directory=tmp_path / "drop",
        watch_settle_seconds=0,
        cleanup_empty_source_dirs=True,
        cleanup_processed_source_dirs=True,
    )
    watcher = Watcher(settings, lambda target: True)
    assert watcher.run_once() == 0
    assert untouched_dir.exists()


def test_watcher__dangerous_cleanup_requires_empty_cleanup_flag(tmp_path: Path):
    source_dir = tmp_path / "drop" / "release"
    source_dir.mkdir(parents=True)
    media_file = source_dir / "show.s01e01.mkv"
    media_file.write_text("test")
    (source_dir / "release.nfo").write_text("notes")
    settings = SettingStore(
        watch_enabled=True,
        watch_input_directory=tmp_path / "drop",
        watch_recursive=True,
        watch_settle_seconds=0,
        cleanup_empty_source_dirs=False,
        cleanup_processed_source_dirs=True,
    )

    def process_target(target):
        target.source.unlink()
        return True

    watcher = Watcher(settings, process_target)
    assert watcher.run_once() == 1
    assert source_dir.exists()
