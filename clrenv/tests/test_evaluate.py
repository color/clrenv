import functools

import clrenv
import pytest
import yaml


@pytest.fixture(autouse=True)
def clear_mode(monkeypatch):
    monkeypatch.setenv("CLRENV_MODE", "")


@pytest.fixture()
def default_env(tmp_path):
    env_path = tmp_path / "env"
    env_path.write_text(
        yaml.dump({"base": {"a": "b", "aa": {"bb": "cc", "bbb": "ccc"}}})
    )
    return clrenv.evaluate.RootClrEnv([env_path])


def test_make_env_var_name():
    fn = functools.partial(clrenv.evaluate.SubClrEnv._make_env_var_name, None)

    assert fn(("a",)) == "CLRENV__A"
    assert fn(("a", "b", "c")) == "CLRENV__A__B__C"
    assert fn(("a", "b", "c_d")) == "CLRENV__A__B__C_D"
    assert fn(tuple(), as_prefix=True) == "CLRENV__"
    assert fn(("a", "b"), as_prefix=True) == "CLRENV__A__B__"


def test_base(default_env):
    assert default_env.a == "b"
    assert default_env.aa.bb == "cc"
    assert default_env.aa.bbb == "ccc"

    assert default_env["a"] == "b"
    assert default_env.aa["bb"] == "cc"
    assert default_env["aa"].bbb == "ccc"


def test_mode(tmp_path, monkeypatch):
    env_path = tmp_path / "env"
    env_path.write_text(yaml.dump({"base": {"foo": "bar"}, "test": {"foo": "baz"}}))

    monkeypatch.setenv("CLRENV_MODE", "test")
    env = clrenv.evaluate.RootClrEnv([env_path])
    assert env.foo == "baz"


def test_missing_mode(tmp_path, monkeypatch):
    env_path = tmp_path / "env"
    env_path.write_text(yaml.dump({"base": {"foo": "bar"}}))

    monkeypatch.setenv("CLRENV_MODE", "test")
    with pytest.raises(ValueError):
        env = clrenv.evaluate.RootClrEnv([env_path])
        # The env is read lazily, access an element.
        env.foo  # pylint: disable=W0104


def test_missing_base(tmp_path):
    env_path = tmp_path / "env"
    env_path.write_text(yaml.dump({"notbase": {"foo": "bar"}}))

    with pytest.raises(ValueError):
        env = clrenv.evaluate.RootClrEnv([env_path])
        # The env is read lazily, access an element.
        env.foo  # pylint: disable=W0104


def test_nested(tmp_path):
    env_path = tmp_path / "env"
    env_path.write_text(yaml.dump({"base": {"a": {"b": {"c": {"d": {"e": "f"}}}}}}))
    env = clrenv.evaluate.RootClrEnv([env_path])
    assert env.a.b.c.d.e == "f"


def test_keyerror(default_env):
    with pytest.raises(KeyError):
        default_env["b"]  # pylint: disable=W0104


def test_attributeerror(default_env):
    with pytest.raises(AttributeError):
        default_env.b  # pylint: disable=W0104


def test_runtime_override(default_env):
    assert default_env.a == "b"
    default_env.set_runtime_override("a", "z")
    assert default_env.a == "z"
    default_env.clear_runtime_overrides()
    assert default_env.a == "b"


def test_runtime_override_empty_path(default_env):
    with pytest.raises(ValueError):
        default_env.set_runtime_override([], "aaa")


def test_runtime_override_nonprimitive(default_env):
    with pytest.raises(ValueError):
        default_env.set_runtime_override("a", [])
        default_env.set_runtime_override("a", {})
        default_env.set_runtime_override("a", object())


def test_nested_runtime_override(default_env):
    assert default_env.aa.bb == "cc"
    default_env.set_runtime_override(("aa", "bb"), "zz")
    assert default_env.aa.bb == "zz"
    default_env.set_runtime_override("aa.bb", "zzz")
    assert default_env.aa.bb == "zzz"

    default_env.clear_runtime_overrides()
    assert default_env.aa.bb == "cc"


def test_runtime_override_as_attributes(default_env):
    assert default_env.a == "b"
    default_env.a = "z"
    assert default_env.a == "z"

    assert default_env.aa.bb == "cc"
    default_env.aa.bb = "zz"
    assert default_env.aa.bb == "zz"


def test_runtime_override_as_items(default_env):
    assert default_env["a"] == "b"
    default_env["a"] = "z"
    assert default_env["a"] == "z"

    assert default_env["aa"]["bb"] == "cc"
    default_env["aa"]["bb"] = "zz"
    assert default_env["aa"]["bb"] == "zz"

    # Delete it
    del default_env.aa["bb"]
    assert default_env.aa.bb == "cc"
    with pytest.raises(KeyError):
        # Can only delete overrides
        del default_env.aa["bb"]

    # Set it again.
    default_env.aa.bb = "zz"
    assert default_env.aa.bb == "zz"
    # Clear them all
    default_env.clear_runtime_overrides()
    assert default_env.aa.bb == "cc"


def test_env_var(monkeypatch, default_env):
    # Known attribute
    monkeypatch.setenv("CLRENV__A", "z")
    assert default_env.a == "z"

    # New attribute
    assert "z" not in default_env
    monkeypatch.setenv("CLRENV__Z", "z")
    assert "z" in default_env
    assert "z" in list(default_env)
    assert default_env.z == "z"

    # Deeply set
    assert "y" not in default_env
    monkeypatch.setenv("CLRENV__Y__YY__YYY", "yyyy")
    assert default_env.y.yy.yyy == "yyyy"
    assert "y" in default_env

    # Runtime overrides take priority
    default_env.z = "w"
    assert default_env.z == "w"
    default_env.clear_runtime_overrides()
    assert default_env.z == "z"


def test_underscored_keys(default_env):
    with pytest.raises(KeyError):
        default_env["__env"]  # pylint: disable=pointless-statement
    with pytest.raises(AttributeError):
        getattr(default_env.__unknown)
