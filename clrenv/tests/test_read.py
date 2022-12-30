from pathlib import Path
from types import SimpleNamespace
from typing import Optional

import botocore.exceptions
from clrenv.read import MissingEnvVar, MissingEnvVarsError  # type: ignore
import pytest
import yaml

import clrenv
from clrenv.types import Secret


@pytest.fixture(autouse=True)
def clear_mode(monkeypatch):
    monkeypatch.setenv("CLRENV_MODE", "")


def test_empty_file(tmp_path):
    env_path = tmp_path / "env"
    env_path.write_text(yaml.dump({"base": {"foo": "bar"}}))

    empty_env_path = tmp_path / "empty_env"
    empty_env_path.write_text("")

    env = clrenv.read.EnvReader([empty_env_path, env_path]).read()
    assert env["foo"] == "bar"


def test_int_key(tmp_path):
    env_path = tmp_path / "env"
    env_path.write_text(yaml.dump({"base": {"foo": "bar", 2: "bazz"}}))

    with pytest.raises(ValueError):
        clrenv.read.EnvReader([env_path]).read()


def test_underscore_key(tmp_path):
    env_path = tmp_path / "env"
    env_path.write_text(yaml.dump({"base": {"foo": "bar", "_foo": "bazz"}}))

    with pytest.raises(ValueError):
        clrenv.read.EnvReader([env_path]).read()


def test_expands_user(tmp_path):
    env_path = tmp_path / "env"
    env_path.write_text(yaml.dump({"base": {"foo": "~/aaa"}}))
    env = clrenv.read.EnvReader([env_path]).read()
    assert env["foo"] == Path("~/aaa").expanduser().as_posix()


def test_none_values_to_empty_str(tmp_path):
    env_path = tmp_path / "env"
    env_path.write_text(yaml.dump({"base": {"foo": None}}))
    env = clrenv.read.EnvReader([env_path]).read()
    assert env["foo"] == ""


def test_expands_vars(tmp_path, monkeypatch):
    monkeypatch.setenv("VAR_FOR_CLRENV_TEST", "aaa")
    env_path = tmp_path / "env"
    env_path.write_text(yaml.dump({"base": {"foo": "$VAR_FOR_CLRENV_TEST"}}))
    env = clrenv.read.EnvReader([env_path]).read()
    assert env["foo"] == "aaa"


def test_clrypt(tmp_path, monkeypatch):
    import clrypt

    def mock_read(group, name):
        assert group == "keys"
        assert name == "keys"
        return {"aaa": "bbb"}

    monkeypatch.setattr(clrypt, "read_file_as_dict", mock_read)

    env_path = tmp_path / "env"
    env_path.write_text(yaml.dump({"base": {"foo": "^keyfile aaa"}}))
    env = clrenv.read.EnvReader([env_path]).read()
    assert isinstance(env["foo"], Secret)
    assert env["foo"].value == "bbb"


def test_chamber_env_golden_path(tmp_path):
    env_path = tmp_path / "env"

    env_data = {
        "NICEPATHOKAAA": "1",
        "NICE_WITH_UNDERSCORE_CCC": "2",
    }

    def _fake_get_env(name: str) -> Optional[str]:
        return env_data.get(name, None)

    env_path = tmp_path / "env"
    env_path.write_text(
        yaml.dump(
            {
                "base": {
                    "foo": "^chamber/v1 nicepathokaaa",
                    "ns": {
                        "quux": "^chamber/v1 nice_with_underscore_ccc",
                    },
                }
            }
        )
    )

    env = clrenv.read.EnvReader([env_path], getenv=_fake_get_env).read()
    assert isinstance(env["foo"], Secret)
    assert env["foo"].value == "1"
    assert isinstance(env["ns"]["quux"], Secret)
    assert env["ns"]["quux"].value == "2"


def test_chamber_env_missing_env_vars(tmp_path):
    env_path = tmp_path / "env"

    env_data = {
        "NICEPATHOKAAA": "1",
        "NICE_WITH_UNDERSCORE_CCC": "3",
        "EMPTY_EEE": "",
    }

    def _fake_get_env(name: str) -> Optional[str]:
        return env_data.get(name, None)

    env_path = tmp_path / "env"
    env_path.write_text(
        yaml.dump(
            {
                "base": {
                    "foo": "^chamber/v1 nicepathokaaa",
                    "ns": {
                        "quux": "^chamber/v1 nice_with_underscore_ccc",
                    },
                    "nonexistent1": "^chamber/v1 nonexistent_ddd",
                    "empty": "^chamber/v1 empty_eee",
                }
            }
        )
    )
    with pytest.raises(MissingEnvVarsError) as excinfo:
        _env = clrenv.read.EnvReader([env_path], getenv=_fake_get_env).read()
    assert excinfo.type is MissingEnvVarsError
    missing = [
        MissingEnvVar(
            yaml_key_path="empty",
            chamber_var_name="empty_eee",
            env_var="EMPTY_EEE",
        ),
        MissingEnvVar(
            yaml_key_path="nonexistent1",
            chamber_var_name="nonexistent_ddd",
            env_var="NONEXISTENT_DDD",
        ),
    ]
    assert excinfo.value.missing == missing
    assert (
        excinfo.value.args[0]
        == "The following parameters were not set in the environment variables or were set to empty strings:\n\tEnv var 'EMPTY_EEE' from the Chamber var name 'empty_eee' from YAML key path 'empty'\n\tEnv var 'NONEXISTENT_DDD' from the Chamber var name 'nonexistent_ddd' from YAML key path 'nonexistent1'\n"
    )


def test_chamber_env_invalid_characters(tmp_path):
    env_path = tmp_path / "env"

    env_data = {}

    def _fake_get_env(name: str) -> Optional[str]:
        return env_data.get(name, None)

    bad_data = ["dot.aaa", "dash-bbb", "foo'bar", 'bar"foo']
    x = 0
    for name in bad_data:
        env_path = tmp_path / f"env-{x}"
        x += 1
        env_path.write_text(
            yaml.dump(
                {
                    "base": {
                        "yep": {
                            "foo": f"^chamber/v1 {name}",
                        },
                    }
                }
            )
        )
        with pytest.raises(ValueError) as excinfo:
            _env = clrenv.read.EnvReader([env_path], getenv=_fake_get_env).read()
        assert (
            excinfo.value.args[0]
            == f"Chamber variable name '{name}' in key 'yep.foo' contains invalid characters."
        )


def test_ssm(tmp_path, monkeypatch):
    monkeypatch.setenv("CLRENV_OFFLINE_DEV", "")
    import boto3

    class MockClient:
        exceptions = SimpleNamespace()
        exceptions.ParameterNotFound = botocore.exceptions.ClientError

        def get_parameter(self, Name=None, WithDecryption=None):
            assert WithDecryption is True
            assert Name in ("aaa", "endpoint_error", "param_error")
            if Name == "aaa":
                return {"Parameter": {"Value": "bbb"}}
            elif Name == "endpoint_error":
                raise botocore.exceptions.EndpointConnectionError(endpoint_url="url")
            elif Name == "param_error":
                raise MockClient.exceptions.ParameterNotFound(
                    error_response={}, operation_name=""
                )

    def mock_client(name):
        assert name == "ssm"
        return MockClient()

    monkeypatch.setattr(boto3, "client", mock_client)

    env_path = tmp_path / "env"
    env_path.write_text(yaml.dump({"base": {"foo": "^parameter aaa"}}))
    env = clrenv.read.EnvReader([env_path]).read()
    assert isinstance(env["foo"], Secret)
    assert env["foo"].value == "bbb"

    env_path.write_text(yaml.dump({"base": {"foo": "^parameter endpoint_error"}}))
    with pytest.raises(botocore.exceptions.EndpointConnectionError):
        env = clrenv.read.EnvReader([env_path]).read()

    env_path.write_text(yaml.dump({"base": {"foo": "^parameter param_error"}}))
    with pytest.raises(MockClient.exceptions.ParameterNotFound):
        env = clrenv.read.EnvReader([env_path]).read()


def test_offline_parameter_flag(tmp_path, monkeypatch):
    monkeypatch.setenv("CLRENV_OFFLINE_DEV", "true")

    env_path = tmp_path / "env"
    env_path.write_text(yaml.dump({"base": {"foo": "^parameter aaa"}}))
    env = clrenv.read.EnvReader([env_path]).read()
    assert isinstance(env["foo"], Secret)
    assert env["foo"].value == "CLRENV_OFFLINE_PLACEHOLDER"
