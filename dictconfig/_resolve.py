import re
import collections

from ._schema import validate_dict_schema, validate_list_schema, validate_leaf_schema
from . import exceptions
from . import parsers as _parsers

# building configuration trees
# ----------------------------

def _build_configuration_tree(raw_cfg, schema):
    """Recursively constructs a configuration tree from a raw configuration.

    The raw configuration can be a dictionary, list, or a non-container type. In any
    case, the provided schema must match the type of the raw configuration; for example,
    if the raw configuration is a dictionary, the schema must be a dict schema.

    Parameters
    ----------
    raw_cfg
        A dictionary, list, or non-container type representing the "raw", unresolved
        configuration.
    schema
        A schema dictionary describing the types of the configuration tree nodes.

    Returns
    -------
        The configuration tree.

    """
    # construct the configuration tree
    # the configuration tree is a nested container whose terminal leaf values
    # are _LeafNodes. "Internal" nodes are dictionaries or lists.
    args = (raw_cfg, schema)
    if isinstance(raw_cfg, dict):
        validate_dict_schema(schema)
        root = _make_dict_node(*args)
    elif isinstance(raw_cfg, list):
        validate_list_schema(schema)
        root = _make_list_node(*args)
    else:
        validate_leaf_schema(schema)
        root = _make_leaf_node(*args)

    return root

# a singleton that marks whether a node in the configuration tree is being resolved
_PENDING = object()

# denotes that the leaf node has not yet been discovered
_UNDISCOVERED = object()

class _LeafNode:
    """Represents a leaf of the configuration tree.

    Attributes
    ----------
    raw
        The "raw" value of the leaf node as it appeared in the raw configuration.
        This can be any type.
    schema_type : str
        A string describing the expected type of this leaf once resolved.

    """

    def __init__(self, raw, type_):
        self.raw = raw
        self.type_ = type_

        # The resolved value of the leaf node. There are two special values. If
        # this is _UNDISCOVERED, the resolution process has not yet discovered
        # the leaf node (this is the default value). If this is _PENDING, a
        # step in the resolution process has started to resolve the leaf. This
        # can be used to detect cycles.
        self.resolved = _UNDISCOVERED

    @property
    def references(self):
        if not isinstance(self.raw, str):
            return []

        pattern = r"\$\{(.+?)\}"
        return re.findall(pattern, self.raw)


def _make_dict_node(dct, dict_schema):
    """Construct an internal dictionary node and recurse on the children."""
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
    """Make an internal list node from a raw list and recurse on the children."""
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
    """Make a leaf node. Helper function simply creates an instance of _LeafNode."""
    return _LeafNode(s, leaf_schema['type'])




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




def resolve(data, schema, context=None, override_parsers=None):
    if context is None:
        context = {}
    elif "self" in context:
        raise ValueError('context cannot contain a "self" key; it is reserved.')

    parsers = _update_parsers(override_parsers)

    root = _build_configuration_tree(data, schema)
    return _resolve_configuration_tree(root, _Components(root=root, context=context, parsers=parsers))


_Components = collections.namedtuple('_Components', 'root context parsers')


def _update_parsers(overrides):
    parsers = _parsers.DEFAULT_PARSERS
    if overrides is not None:
        for type_, parser in overrides.items():
            parsers[type_] = parser
    return parsers




def _resolve_configuration_tree(node, components):
    if isinstance(node, dict):
        return _resolve_dict_node(node, components)
    elif isinstance(node, list):
        return _resolve_list_node(node, components)
    else:
        return _resolve_leaf_node(node, components)


def _resolve_dict_node(node, components):
    return {
        key: _resolve_configuration_tree(child_node, components)
        for key, child_node in node.items()
    }

def _resolve_list_node(node, components):
    return [_resolve_configuration_tree(child_node, components) for child_node in node]





def _resolve_leaf_node(node, components):
    string_representation = node.raw

    if node.resolved is _PENDING:
        raise exceptions.ResolutionError("Circular reference")

    if node.resolved is not _UNDISCOVERED:
        return node.resolved

    node.resolved = _PENDING

    for reference in node.references:
        string_representation = _interpolate(string_representation, reference, components)

    parser = components.parsers[node.type_]
    node.resolved = parser(string_representation)
    return node.resolved


def _resolve_from_self(path, components):
    exploded_path = _explode_dotted_path_string(path)
    try:
        referred_node = _get_path(components.root, exploded_path[1:])
    except KeyError:
        raise exceptions.ResolutionError(f"Cannot resolve {path}")

    _resolve_leaf_node(referred_node, components)
    return referred_node.resolved


def _resolve_from_context(path, context):
    exploded_path = _explode_dotted_path_string(path)
    try:
        return _get_path(context, exploded_path)
    except KeyError:
        raise exceptions.ResolutionError(f"Cannot find {path} in context.")


def _interpolate(s, path, components):
    exploded_path = _explode_dotted_path_string(path)
    if exploded_path[0] == "self":
        substitution = _resolve_from_self(path, components)
    else:
        substitution = _resolve_from_context(path, components.context)

    return _substitute_reference(s, path, substitution)


def _substitute_reference(s, reference, replacement_value):
    pattern = r"\$\{" + reference + r"\}"
    return re.sub(pattern, str(replacement_value), s)
