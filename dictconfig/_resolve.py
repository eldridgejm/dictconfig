import re

from ._schema import validate_key_schema, validate_value_schema
from . import exceptions


PENDING = object()


def _parse_path_component(c):
    if c.isnumeric():
        return int(c)
    else:
        return c


def _explode_dotted_path_string(path):
    components = path.split('.')
    return tuple(_parse_path_component(c) for c in components)


def _get_path(dct, path):
    if isinstance(path, str):
        path = path.split('.')

    if len(path) == 1:
        return dct[path[0]]
    return _get_path(dct[path[0]], path[1:])


def _make_dict_node(dct, key_schema):
    """Construct an internal dictionary node from a dictionary and its key schema."""
    result = {}

    for dct_key, dct_value in dct.items():
        try:
            value_schema = key_schema[dct_key]
        except KeyError:
            value_schema = {'type': 'string'}

        if value_schema['type'] == 'dict':
            result[dct_key] = _make_dict_node(dct_value, value_schema['schema'])
        elif value_schema['type'] == 'list':
            result[dct_key] = _make_list_node(dct_value, value_schema['schema'])
        else:
            result[dct_key] = _LeafNode(dct_value, value_schema['type'])

    return result


def _make_list_node(lst, value_schema):
    result = []
    for lst_value in lst:
        if value_schema['type'] == 'dict':
            r = _make_dict_node(lst_value, value_schema['schema'])
        elif value_schema['type'] == 'list':
            r = _make_list_node(lst_value, value_schema['schema'])
        else:
            r = _LeafNode(lst_value, value_schema['type'])
        result.append(r)
    return result


class _LeafNode:

    def __init__(self, raw_string, type_):
        self.raw_string = raw_string
        self.type_ = type_
        self.resolved = None

    @property
    def references(self):
        pattern = r'\$\{(.+?)\}'
        return re.findall(pattern, self.raw_string)


def resolve(data, schema, context=None):
    if context is None:
        context = {}
    elif 'self' in context:
        raise ValueError('context cannot contain a "self" key; it is reserved.')

    if isinstance(data, dict):
        validate_key_schema(schema)
        root = _make_dict_node(data, schema)
    elif isinstance(data, list):
        validate_value_schema(schema)
        root = _make_list_node(data, schema['schema'])
    else:
        root = _LeafNode(data, schema['type'])

    return _resolve_node(root, context=context)


def _resolve_node(node, root=None, context=None):
    if root is None:
        root = node

    if context is None:
        context = {}

    if isinstance(node, dict):
        return {key: _resolve_node(child_node, root, context) for key, child_node in node.items()}
    elif isinstance(node, list):
        return [_resolve_node(child_node, root, context) for child_node in node]
    else:
        return _resolve_leaf_node(node, root, context)


def _interpolate_reference(s, reference, replacement_value):
    pattern = r'\$\{' + reference + r'\}'
    return re.sub(pattern, str(replacement_value), s)


def _resolve_leaf_node(node, root, context):
    s = node.raw_string

    if node.resolved is PENDING:
        raise exceptions.ResolutionError('Circular reference')

    if node.resolved is not None:
        return node.resolved

    node.resolved = PENDING

    for path in node.references:
        exploded_path = _explode_dotted_path_string(path)

        if exploded_path[0] == 'self':
            try:
                referred_node = _get_path(root, exploded_path[1:])
            except KeyError:
                raise exceptions.ResolutionError(f'Cannot resolve {path}')

            _resolve_leaf_node(referred_node, root, context)
            substitution = referred_node.resolved
        else:
            try:
                substitution = _get_path(context, exploded_path)
            except KeyError:
                raise exceptions.ResolutionError(f'Cannot find {path} in context.')

        s = _interpolate_reference(s, path, substitution)

    node.resolved = s
    return node.resolved
