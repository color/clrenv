from typing import Any, List, Mapping, MutableMapping, NamedTuple, Union

"""Defines type annotations for use in clrenv.

Ideally we would only allow str leaf values so that they can be migrated to an env
var based system. For now we must supports more complex values.
"""

class Secret(NamedTuple):
    source: str
    value: str

    def __repr__(self) -> str:
        """
        Return a Secret's representation without exposing the secret.

        In the event that a Secret's (or, more generally, a ClrEnv object's)
        representation is logged, this will prevent us from leaking secrets into
        plaintext.
        """
        return f"Secret(source='{self.source}')"


# Type that can be read or set as values of leaf nodes.
LeafValue = Union[bool, int, float, str, List[Union[bool, int, float, str]], Secret]
# Type of a non leaf node.
NestedMapping = Mapping[str, Union[LeafValue, Mapping[str, Any]]]
MutableNestedMapping = MutableMapping[str, Union[LeafValue, MutableMapping[str, Any]]]

PRIMITIVE_TYPES = (bool, int, float, str)


def check_valid_leaf_value(key: Any, value: Any) -> None:
    """Raises a ValueError is the value is not a valid type.

    key is only used for the error message."""
    if isinstance(value, PRIMITIVE_TYPES):
        return
    if isinstance(value, list) and all(isinstance(_, PRIMITIVE_TYPES) for _ in value):
        return
    raise ValueError(f"Non primitive value type: {key}={value}")
