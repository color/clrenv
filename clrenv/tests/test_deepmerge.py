from clrenv.deepmerge import deepmerge


def test_deepmerge():
    dst = {"a": {"b": 1, "c": 1}}
    src = {"a": {"b": 3, "d": 3}}
    deepmerge(dst, src)
    assert dst == {"a": {"b": 3, "c": 1, "d": 3}}


def test_empty_src():
    dst = {"a": {"b": 1, "c": 1}}
    src = {}
    deepmerge(dst, src)
    assert dst == {"a": {"b": 1, "c": 1}}


def test_empty_dst():
    dst = {}
    src = {"a": {"b": 1, "c": 1}}
    deepmerge(dst, src)
    assert dst == {"a": {"b": 1, "c": 1}}


def test_empty_nested_src():
    dst = {"a": {}}
    src = {"a": {"b": 1, "c": 1}}
    deepmerge(dst, src)
    assert dst == {"a": {"b": 1, "c": 1}}
