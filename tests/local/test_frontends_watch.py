import pytest

from mnamer.frontends import Cli
from mnamer.setting_store import SettingStore

pytestmark = pytest.mark.local


def test_cli__watch_mode_does_not_require_targets(tmp_path):
    settings = SettingStore(watch_enabled=True, watch_input_directory=tmp_path)
    cli = Cli(settings)
    assert cli.watch_mode is True


def test_cli__non_watch_requires_targets():
    settings = SettingStore()
    with pytest.raises(SystemExit) as exc_info:
        Cli(settings)
    assert exc_info.value.code == 2
