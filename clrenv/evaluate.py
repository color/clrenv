"""
Defines classes that allow environment to be evaluated as a series of attributes.

Exposes a nested MutableMapping with values that can be accessed via itemgetter
or attribute syntax.

The environment is built from three sources (in order of priority):
1) Runtime overrides.
2) Environmental variables. Variables in the form of CLRENV__FOO__BAR=baz will cause
   env.foo.bar==baz. These are evaluated at access time.
   TODO(michael.cusack): Should these also be fixed on the state at first env usage?
   Should we monitor and warn changes?
3) By reading a set of yaml files from disk as described in path.py. Files are read
   lazily when the first attribute is referenced and never reloaded.

# Runtime Overrides
RootClrEnv.set_runtime_override(key_path, value) allows you to override values at
runtime. Using this is encouraged over setting a value using attribute setters, but
discouraged in preference of only doing so in tests and using unittest.mock.patch
or monkeypath.setattr instead.
Runtime overrides can be cleared with env.clear_runtime_overrides()- for instance
in test teardown.
"""
import logging
import os
import traceback
from collections import abc
from pathlib import Path
from typing import (
    Iterable,
    Iterator,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)

from .path import environment_paths
from .read import EnvReader
from .types import LeafValue, NestedMapping, Secret, check_valid_leaf_value

logger = logging.getLogger(__name__)

DEBUG_MODE = os.environ.get("CLRENV_DEBUG", "").lower() in ("true", "1")

# Access to an attribute might return a primitive or if it is not a leaf node
# another SubClrEnv.
Value = Union[LeafValue, "SubClrEnv"]


class SubClrEnv(abc.MutableMapping):
    def __init__(self, parent: "SubClrEnv", next_key: str):
        # The RootClrEnv class omits these, but SubClrEnv needs them.
        assert parent and next_key

        self._cached_env: Optional[NestedMapping] = None
        self._parent: SubClrEnv = parent
        self._key_path: Tuple[str, ...] = parent._sub_key_path(next_key)
        self._root: RootClrEnv = parent._root

    def __getitem__(self, key: str) -> Value:
        """Allows access with item getter, like a Mapping."""
        if key.startswith("_"):
            raise KeyError("Keys can not start with _")

        value = self._evaluate_key(key)

        if value is None:
            # There will never be explicit Nones.
            raise KeyError(f"Unknown key in {self}: {key}")

        if isinstance(value, abc.Mapping):
            # Nest to allow deeper lookups.
            return SubClrEnv(self, key)

        # Return the actual value.
        return value

    def __getattr__(self, key: str) -> Value:
        """Allows access as attributes."""
        if key.startswith("_"):
            # This is raise an exception.
            object.__getattribute__(self, key)
        try:
            return self[key]
        except KeyError as e:
            raise AttributeError(str(e))

    def __setitem__(self, key: str, value: LeafValue):
        self._root.set_runtime_override(self._sub_key_path(key), value)

    def __setattr__(self, key: str, value: LeafValue):
        """Sets a runtime override as an attribute."""
        # Internal fields are prefixed with a _ and should be treated normally.
        if key.startswith("_"):
            return object.__setattr__(self, key, value)
        self[key] = value

    def __delitem__(self, key: str):
        """Only support deleting runtime overrides."""
        del self._root._runtime_overrides[self._key_path][key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._sub_keys)

    def __len__(self):
        return len(self._sub_keys)

    def __repr__(self):
        return f"ClrEnv[{'.'.join(self._key_path)}]={self._env}"

    def _make_env(self) -> NestedMapping:
        """Creates an env map relative to this path."""
        # Get subtree of parent env.
        return self._parent._env.get(self._key_path[-1], {})  # type: ignore

    @property
    def _env(self) -> NestedMapping:
        """Returns the env map relative to this path.

        Using this function allows lazy evaluation."""
        if not self._cached_env:
            self._cached_env = self._make_env()
        return self._cached_env

    @property
    def _sub_keys(self) -> Set[str]:
        """Returns the set of all valid keys under this node."""
        # Keys in the merged env.
        subkeys = set(self._env.keys())

        # Keys in runtime overrides
        if self._key_path in self._root._runtime_overrides:
            subkeys.update(self._root._runtime_overrides[self._key_path])

        # Keys defined in environmental vars.
        env_var_prefix = self._make_env_var_name(as_prefix=True)
        for env_var in os.environ:
            if env_var.startswith(env_var_prefix):
                env_var = env_var[len(env_var_prefix) :]
                subkeys.add(env_var.split("__")[0].lower())
        return subkeys

    def _evaluate_key(self, key: str) -> Union[LeafValue, Mapping, None]:
        """Returns the stored value for the given key.

        There are three potential sources of data (in order of priority):
        1) Runtime overrides
        2) Environment variables
        3) Merged yaml files

        If the returned value is a mapping it indicates this is not a leaf node and a
        SubClrEnv should be returned to the user.

        If the returned value is None it indicates a KeyError/AttributeError should be
        raised. This can be assumed because ClrEnv does not support explicit null/None
        values. Any nulls in the yaml files are coerced to empty strings when read.
        Runtime overrides are not allowed to set None.
        """
        key_path = self._sub_key_path(key)

        # Check for runtime overrides.
        if self._key_path in self._root._runtime_overrides:
            if key in self._root._runtime_overrides[self._key_path]:
                return self._root._runtime_overrides[self._key_path][key]

        # Check for env var override.
        env_var_name = self._make_env_var_name(key_path=key_path)
        if env_var_name in os.environ:
            env_var_value = os.environ[env_var_name]
            # TODO(michael.cusack) cast type?
            return env_var_value

        # Get value from the merged env.
        value = self._env.get(key)

        # If the value is absent from all three sources but the key does exist in
        # subkeys it means this is an intermediate node of a value set via env vars.
        # Return a Mapping which will cause a SubClrEnv to be returned to the user.
        # The content of the returned mapping does not matter.
        if value is None and key in self._sub_keys:
            return {}

        if isinstance(value, Secret):
            return value.value

        return value

    def _sub_key_path(self, key: str) -> Tuple[str, ...]:
        """Returns an attribute path with the given key appended."""
        return self._key_path + (key,)

    def _make_env_var_name(
        self, key_path: Optional[Iterable[str]] = None, as_prefix: bool = False
    ) -> str:
        """Returns the env var name that can be used to set the given attribute path."""
        if key_path is None:
            key_path = self._key_path
        key_path = list(key_path)
        key_path.insert(0, "CLRENV")
        if as_prefix:
            key_path.append("")
        return "__".join(key_path).upper()


class RootClrEnv(SubClrEnv):
    """Special case of SubClrEnv for the root node."""

    def __init__(self, paths: Optional[List[Path]] = None):
        self._environment_paths = paths
        self._cached_env: Optional[NestedMapping] = None
        self._root: RootClrEnv = self
        self._parent: RootClrEnv = self
        self._key_path: Tuple[str, ...] = tuple()

        # Runtime overrides for all key paths are stored in the root node. The first
        # key is the parent key path and the second key is the leaf key. This allows
        # efficent lookup for subkeys.
        # env.a.b.c = 'd' ==> _runtime_overrides = {('a', 'b'): {'c': 'd'}}
        self._runtime_overrides: MutableMapping[
            Tuple[str, ...], MutableMapping[str, LeafValue]
        ] = {}

    def _make_env(self) -> NestedMapping:
        # Lazily read the environment from disk.
        return EnvReader(self._environment_paths or environment_paths()).read()

    def clear_runtime_overrides(self):
        """Clear all runtime overrides."""
        self._runtime_overrides.clear()

    def set_runtime_override(
        self, key_path: Union[str, Sequence[str]], value: LeafValue
    ):
        """Sets a runtime override.

        Only do this in tests and ideally use unittest.mock.patch or monkeypath.setattr
        instead.

        Notice that this method is only on the root node."""
        if not key_path:
            raise ValueError("key_path can not be empty.")
        # No support for nested runtime overrides. Only allow primitives.
        check_valid_leaf_value(key_path, value)

        if isinstance(key_path, str):
            key_path = key_path.split(".")

        # Check that the key already exists.
        parent: Union[SubClrEnv, LeafValue] = self
        for name in key_path:
            assert isinstance(parent, Mapping)
            assert name in parent, f"{name, parent}"
            parent = parent[name]

        # Ideally we wouldn't be overriding global state like this at all, but at least
        # make it loud.
        logger.warning(f"Manually overriding env.{'.'.join(key_path)} to {value}.")
        if DEBUG_MODE:
            # Get stack and remove this frame.
            tb = traceback.extract_stack()[:-1]
            logger.warning("".join(traceback.format_list(tb)))

        parents = tuple(key_path[:-1])
        if parents not in self._root._runtime_overrides:
            self._root._runtime_overrides[parents] = {}
        self._root._runtime_overrides[parents][key_path[-1]] = value
