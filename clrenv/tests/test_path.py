import clrenv
import pytest


@pytest.fixture(autouse=True)
def clear_overlay_path(monkeypatch):
    monkeypatch.setenv("CLRENV_OVERLAY_PATH", "")


def test_custom_base(tmp_path, monkeypatch):
    custom_path = tmp_path / 'custom/path'
    custom_path.parent.mkdir()
    custom_path.write_text('data')
    monkeypatch.setenv("CLRENV_PATH", str(custom_path))
    assert clrenv.path.environment_paths() == [custom_path]


def test_missing_base(tmp_path, monkeypatch):
    monkeypatch.setenv("CLRENV_PATH", str(tmp_path / 'aaa'))

    with pytest.raises(ValueError):
        clrenv.path.environment_paths()


def test_overlay(tmp_path, monkeypatch):
    env_path = tmp_path / 'env'
    monkeypatch.setenv("CLRENV_PATH", str(env_path))
    env_path.write_text('')

    overlay_path1 = tmp_path / 'overlay1'
    overlay_path2 = tmp_path / 'overlay2'
    overlay_path1.write_text('data')
    overlay_path2.write_text('data2')
    monkeypatch.setenv("CLRENV_OVERLAY_PATH", f"{overlay_path1}:{overlay_path2}")
    assert clrenv.path.environment_paths() == [
        overlay_path1,
        overlay_path2,
        env_path,
    ]
