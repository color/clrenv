from collections import abc, deque
from typing import Any, Mapping, MutableMapping


def deepmerge(dst: MutableMapping[str, Any], src: Mapping[str, Any]):
    """Merges src into dst.

    If both source and dest values are Mappings merge them as well.
    """
    # Queue of (dict, dict) tuples to merge.
    to_merge = deque([(dst, src)])

    while to_merge:
        _dst, _src = to_merge.pop()
        for key, src_value in _src.items():
            dst_value = _dst.get(key)
            if isinstance(dst_value, abc.Mapping) and isinstance(
                src_value, abc.Mapping
            ):
                to_merge.append((dst_value, src_value))
            else:
                _dst[key] = src_value
