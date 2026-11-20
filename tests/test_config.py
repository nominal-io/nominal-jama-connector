from __future__ import annotations

from pathlib import Path

import pytest

from nominal_checks_from_jama.config import AuthKind, Config, JamaSettings, NominalSettings

from .conftest import BASE


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "jama-checks.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_round_trip(tmp_path: Path) -> None:
    config = Config(
        jama=JamaSettings(base_url=BASE, project="12", item_types=("34",), auth=AuthKind.BASIC, account="stester"),
        nominal=NominalSettings(checklist_name="Widget checks", priority="P1", channel_markers=("{}",)),
    )
    path = config.save(tmp_path / "jama-checks.toml")
    assert Config.load(path) == config.with_path(path)


def test_defaults_and_numeric_ids(tmp_path: Path) -> None:
    config = Config.load(_write(tmp_path, f'[jama]\nbase_url = "{BASE}"\nproject = 12\nitem_types = [34]\n'))
    assert (config.jama.project, config.jama.item_types) == ("12", ("34",))
    assert config.nominal == NominalSettings()


def test_empty_checklist_name_is_left_out(tmp_path: Path) -> None:
    path = Config(jama=JamaSettings(base_url=BASE, project="12")).save(tmp_path / "jama-checks.toml")
    assert "checklist_name" not in path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (f'[jama]\nbase_url = "{BASE}"\n', "base_url and project"),
        (f'[jama]\nbase_url = "{BASE}"\nproject = 12\nauth = "magic"\n', "auth must be one of"),
        (f'[jama]\nbase_url = "{BASE}"\nproject = 12\nitem_types = [true]\n', "item_types"),
        (f'[jama]\nbase_url = "{BASE}"\nproject = 12\n[nominal]\npriority = "P9"\n', "priority"),
        (f'[jama]\nbase_url = "{BASE}"\nproject = 12\n[nominal]\nref_name = " "\n', "ref_name"),
        (f'[jama]\nbase_url = "{BASE}"\nproject = 12\n[nominal]\nchannel_markers = ["()"]\n', "channel_markers"),
        ('jama = 1\n[nominal]\nprofile = "x"\n', "must be a table"),
    ],
)
def test_invalid_settings(tmp_path: Path, text: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        Config.load(_write(tmp_path, text))
