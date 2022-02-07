from typing import Any, List, Mapping, MutableMapping, Union

"""Defines type annotations for use in clrenv.

Ideally we would only allow str leaf values so that they can be migrated to an env
var based system. For now we must supports more complex values.
"""

# Type that can be read or set as values of leaf nodes.
LeafValue = Union[bool, int, float, str, List[Union[bool, int, float, str]]]
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
