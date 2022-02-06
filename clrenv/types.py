from typing import Any, List, Mapping, MutableMapping, Union

# Type that can be read or set as values of leaf nodes.
LeafValue = Union[bool, int, float, str, List[Union[bool, int, float, str]]]
# Type of a non leaf node.
NestedMapping = Mapping[str, Union[LeafValue, Mapping[str, Any]]]
MutableNestedMapping = MutableMapping[str, Union[LeafValue, MutableMapping[str, Any]]]

PRIMITIVE_TYPES = (bool, int, float, str)


def check_valid_leaf_value(key, value: Any) -> None:
    """Returns whether the"""
    if isinstance(value, PRIMITIVE_TYPES):
        return
    if isinstance(value, list) and all(isinstance(_, PRIMITIVE_TYPES) for _ in value):
        return
    raise ValueError(f"Non primitive value type: {key}={value}")
