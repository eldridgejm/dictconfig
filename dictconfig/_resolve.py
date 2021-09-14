import re

from ._schema import validate_dict_schema, validate_list_schema, validate_leaf_schema
from . import exceptions
from . import parsers as _parsers


PENDING = object()

def _parse_path_component(c):
    if c.isnumeric():
        return int(c)
    else:
        return c


def _explode_dotted_path_string(path):
    components = path.split(".")
    return tuple(_parse_path_component(c) for c in components)


def _get_path(dct, path):
    if isinstance(path, str):
        path = path.split(".")

    if len(path) == 1:
        return dct[path[0]]
    return _get_path(dct[path[0]], path[1:])



class _LeafNode:
    def __init__(self, raw, type_):
        self.raw = raw
        self.type_ = type_
        self.resolved = None

    @property
    def references(self):
        if not isinstance(self.raw, str):
            return []

        pattern = r"\$\{(.+?)\}"
        return re.findall(pattern, self.raw)

def _make_dict_node(dct, dict_schema):
    """Construct an internal dictionary node from a dictionary and its key schema."""
    result = {}

    for dct_key, dct_value in dct.items():
        try:
            child_schema = dict_schema["schema"][dct_key]
        except KeyError:
            child_schema = {"type": "string"}

        args = (dct_value, child_schema)

        if child_schema["type"] == "dict":
            result[dct_key] = _make_dict_node(*args)
        elif child_schema["type"] == "list":
            result[dct_key] = _make_list_node(*args)
        else:
            result[dct_key] = _make_leaf_node(*args)

    return result


def _make_list_node(lst, list_schema):
    child_schema = list_schema["schema"]

    result = []
    for lst_value in lst:
        args = (lst_value, child_schema)
        if child_schema["type"] == "dict":
            r = _make_dict_node(*args)
        elif child_schema["type"] == "list":
            r = _make_list_node(*args)
        else:
            r = _make_leaf_node(*args)
        result.append(r)
    return result


def _make_leaf_node(s, leaf_schema):
    return _LeafNode(s, leaf_schema['type'])


def resolve(data, schema, context=None, custom_parsers=None):
    if context is None:
        context = {}
    elif "self" in context:
        raise ValueError('context cannot contain a "self" key; it is reserved.')

    parsers = _parsers.DEFAULT_PARSERS
    if custom_parsers is not None:
        for type_, parser in custom_parsers.items():
            parsers[type_] = parser

    args = (data, schema)
    if isinstance(data, dict):
        validate_dict_schema(schema)
        root = _make_dict_node(*args)
    elif isinstance(data, list):
        validate_list_schema(schema)
        root = _make_list_node(*args)
    else:
        validate_leaf_schema(schema)
        root = _make_leaf_node(*args)

    return _resolve_node(root, parsers, context=context)


def _resolve_node(node, parsers, root=None, context=None):
    if root is None:
        root = node

    if context is None:
        context = {}

    args = (node, parsers, root, context)
    if isinstance(node, dict):
        return _resolve_dict_node(*args)
    elif isinstance(node, list):
        return _resolve_list_node(*args)
    else:
        return _resolve_leaf_node(*args)


def _resolve_dict_node(node, parsers, root, context):
    return {
        key: _resolve_node(child_node, parsers, root, context)
        for key, child_node in node.items()
    }


def _resolve_list_node(node, parsers, root, context):
    return [_resolve_node(child_node, parsers, root, context) for child_node in node]


def _resolve_leaf_node(node, parsers, root, context):
    string_representation = node.raw

    if node.resolved is PENDING:
        raise exceptions.ResolutionError("Circular reference")

    if node.resolved is not None:
        return node.resolved

    node.resolved = PENDING

    for path in node.references:
        string_representation = _interpolate(string_representation, parsers, root, context, path)

    parser = parsers[node.type_]
    node.resolved = parser(string_representation)
    return node.resolved


def _fill_placeholder(s, reference, replacement_value):
    pattern = r"\$\{" + reference + r"\}"
    return re.sub(pattern, str(replacement_value), s)


def _interpolate_from_self(path, parsers, root, context):
    exploded_path = _explode_dotted_path_string(path)
    try:
        referred_node = _get_path(root, exploded_path[1:])
    except KeyError:
        raise exceptions.ResolutionError(f"Cannot resolve {path}")

    _resolve_leaf_node(referred_node, parsers, root, context)
    return referred_node.resolved


def _interpolate_from_context(path, context):
    exploded_path = _explode_dotted_path_string(path)
    try:
        return _get_path(context, exploded_path)
    except KeyError:
        raise exceptions.ResolutionError(f"Cannot find {path} in context.")


def _interpolate(s, parsers, root, context, path):
    exploded_path = _explode_dotted_path_string(path)
    if exploded_path[0] == "self":
        substitution = _interpolate_from_self(path, parsers, root, context)
    else:
        substitution = _interpolate_from_context(path, context)

    return _fill_placeholder(s, path, substitution)
