"""
Reads clrenv environment files.
"""
import yaml

try:
    # If available, use the C bindings for far, far faster loading
    # See: https://pyyaml.org/wiki/PyYAMLDocumentation
    from yaml import CSafeLoader as SafeLoader
except ImportError:
    # If the C bindings aren't available, fall back to the "much slower" Python bindings
    from yaml import SafeLoader  # type: ignore

import logging
import os
from collections import abc, deque
from pathlib import Path
from typing import Any, Deque, Iterable, Mapping, MutableMapping, Optional, Tuple, Union

import boto3
from botocore.exceptions import EndpointConnectionError  # type: ignore

from .deepmerge import deepmerge
from .path import environment_paths

logger = logging.getLogger(__name__)

# Types that can be read or set as values of leaf nodes.

# PrimitiveValues unofficially also could be a List[Union[bool, int, float, str]], but this
# is discouraged.
PrimitiveValue = Union[bool, int, float, str]
NestedMapping = Mapping[str, Union[PrimitiveValue, Mapping[str, Any]]]
MutableNestedMapping = MutableMapping[
    str, Union[PrimitiveValue, MutableMapping[str, Any]]
]

# Flag to prevent clrenv from throwing errors
#  if it cannot connect to the Parameter Store API.
OFFLINE_PARAMETER_FLAG = "CLRENV_OFFLINE_DEV"
OFFLINE_PARAMETER_VALUE = "CLRENV_OFFLINE_PLACEHOLDER"


class EnvReader:
    def __init__(self, environment_paths: Iterable[Path]):
        self.environment_paths: Tuple[Path, ...] = tuple(environment_paths)
        self.mode: Optional[str] = os.environ.get("CLRENV_MODE")

    def read(self) -> NestedMapping:
        """Reads, merges and post-processes environment from disk.

        Clrenv can read from multiple files. Each file must contains a "base" section
        which will always be evaluted as well as optionally several other sections
        which will only be evaluated if their name is equal to CLRENV_MODE.

        Assuming CLRENV_MODE=mode1 and environment_paths=[file1, file2, file3], values
        will be read in the following order (values read later will override those read
        earlier):
        1) base section of file3 (required)
        2) mode1 section of file3 (optional)
        3) base section of file2 (required)
        4) mode1 section of file2 (optional)
        5) base section of file1 (required)
        6) mode1 section of file1 (optional)
        """

        # Whether a section for the specified mode has been read.
        mode_read = False
        # The merged config.
        result: MutableNestedMapping = {}

        # Paths are in decending precedence so loop over in reverse for merging.
        for config_path in self.environment_paths[::-1]:
            config: Mapping[str, Any] = safe_load(config_path.read_text())
            # safe_load will return None if the file is empty
            if not config:
                continue
            # All environment files must have a base section.
            if "base" not in config:
                raise ValueError(f"base section missing from {config_path}")
            deepmerge(result, config["base"])
            # And optionally an overlay section for the mode.
            if self.mode and self.mode in config:
                mode_read = True
                deepmerge(result, config[self.mode])

        # If mode was specified it must be read.
        if self.mode and not mode_read:
            raise ValueError(
                f"CLRENV_MODE set to {self.mode}, but no corresponding section found in any environment file."
            )

        # Post process values. Breadth-first search.
        postprocess_queue: Deque[Tuple[str, MutableNestedMapping]] = deque()
        postprocess_queue.append(("", result))
        while postprocess_queue:
            key_prefix, mapping = postprocess_queue.pop()
            for key, value in mapping.items():
                # Disallow non string keys
                if not isinstance(key, str):
                    raise ValueError(f"Only string keys are allowed: {key_prefix}{key}")
                if key.startswith("_"):
                    raise ValueError(f"Keys can not start with _: {key_prefix}{key}")
                if isinstance(value, abc.Mapping):
                    # Add to queue for post processing.
                    postprocess_queue.append((f"{key_prefix}{key}.", value))
                elif value is None:
                    # Coerce Nones to empty strings.
                    mapping[key] = ""  # type: ignore
                elif isinstance(value, str):
                    mapping[key] = self.postprocess_str(value)
                elif not isinstance(value, (float, bool, int, list)):
                    # TODO(michael.cusack): Stop supporting lists to we can support
                    # setting everything with env vars.
                    raise ValueError(
                        f"Non primitive value type: {key_prefix}{key}={value}"
                    )

        return result

    def postprocess_str(self, value: str) -> str:
        """Post process string values."""
        # Expand environmental variables in the form of $FOO or ${FOO}.
        value = os.path.expandvars(value)
        # If value is a path starting with ~, expand.
        if value.startswith("~"):
            value = os.path.expanduser(value)
        # Substitute from clrypt keyfile.
        elif value.startswith("^keyfile "):
            value = self.evaluate_clrypt_key(value[9:])
        # Substitute from aws ssm parameter store.
        elif value.startswith("^parameter "):
            value = self.evaluate_ssm_parameter(value[11:])

        return value

    def evaluate_clrypt_key(self, name: str) -> str:
        """Returns a value from clrypt."""
        if not hasattr(self, "clrypt_keyfile"):
            # Not all environments use clrypt, delay import until it is needed.
            logger.info("Loading clrypt for clrenv")
            import clrypt

            self.clrypt_keyfile = clrypt.read_file_as_dict("keys", "keys")

        return str(self.clrypt_keyfile.get(name, ""))

    def evaluate_ssm_parameter(self, name: str) -> str:
        """Returns a value from aws ssm parameter store."""
        if os.environ.get(OFFLINE_PARAMETER_FLAG):
            logger.warning(f"Offline, using placeholder value for {name}.")
            return OFFLINE_PARAMETER_VALUE

        if not hasattr(self, "ssm_client"):
            # Not all environments use ssm, delay import until it is needed.
            logger.info("Loading SSM ParameterStore for clrenv")
            self.ssm_client = boto3.client("ssm")

        try:
            parameter = self.ssm_client.get_parameter(Name=name, WithDecryption=True)
            return str(parameter["Parameter"]["Value"])
        except EndpointConnectionError:
            logger.error(
                "clrenv could not connect to AWS to fetch parameters. "
                "If you're developing locally, try setting the offline environment variable (CLRENV_OFFLINE_DEV) to use placeholder values."
            )
            raise
        except self.ssm_client.exceptions.ParameterNotFound:
            logger.error(f"Could not find {name} in Parameter Store.")
            raise


def safe_load(str_content: str):
    """Safely load YAML, doing so quickly with C bindings if available.

    By default, `yaml.safe_load()` uses the (slower) Python bindings.
    This method is a stand-in replacement that can be considerably faster.
    """
    return yaml.load(str_content, Loader=SafeLoader)


def read_mapping_section():
    """Returns the 'mapping' map from the base enviroment file.

    This contains key names which should be turned into true enviroment
    variables.

    # TODO(michael.cusack): Refactor this so we don't need to read the yaml
    twice.
    """
    return safe_load(environment_paths()[-1].read_text())["mapping"]
