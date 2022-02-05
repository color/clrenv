from pathlib import Path
from types import SimpleNamespace

import botocore.exceptions  # type: ignore
import clrenv
import pytest
import yaml


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
    assert env["foo"] == "bbb"


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
    assert env["foo"] == "bbb"

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
    assert env["foo"] == "CLRENV_OFFLINE_PLACEHOLDER"
