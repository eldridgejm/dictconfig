import re
import collections

from ._schema import validate_dict_schema, validate_list_schema, validate_leaf_schema
from . import exceptions
from . import parsers as _parsers


def _explode_dotted_path_string(path):
    components = path.split(".")
    return tuple(_parse_path_component(c) for c in components)


# building configuration trees
# ----------------------------

def _build_configuration_tree(raw_cfg, schema, external_variables, parsers):
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
        root = _DictNode.from_raw(*args)
    elif isinstance(raw_cfg, list):
        validate_list_schema(schema)
        root = _ListNode.from_raw(*args)
    else:
        validate_leaf_schema(schema)
        root = _LeafNode.from_raw(*args)

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
        self._resolved = _UNDISCOVERED

    @classmethod
    def from_raw(cls, raw, leaf_schema):
        return cls(raw, leaf_schema['type'])

    @property
    def references(self):
        if not isinstance(self.raw, str):
            return []

        pattern = r"\$\{(.+?)\}"
        return re.findall(pattern, self.raw)

    def resolve(self, resolver):

        if self._resolved is _PENDING:
            raise exceptions.ResolutionError("Circular reference")

        if self._resolved is not _UNDISCOVERED:
            return self._resolved

        self._resolved = _PENDING

        s = self.raw
        for reference_path in self.references:
            s = resolver.interpolate(s, reference_path)

        self._resolved = resolver.parse(s, self.type_)
        return self._resolved


class _DictNode:

    def __init__(self, children):
        self.children = children

    @classmethod
    def from_raw(cls, dct, dict_schema):
        children = {}

        for dct_key, dct_value in dct.items():
            try:
                child_schema = dict_schema["schema"][dct_key]
            except KeyError:
                child_schema = {"type": "string"}

            args = (dct_value, child_schema)

            if child_schema["type"] == "dict":
                children[dct_key] = _DictNode.from_raw(*args)
            elif child_schema["type"] == "list":
                children[dct_key] = _ListNode.from_raw(*args)
            else:
                children[dct_key] = _LeafNode.from_raw(*args)

        return cls(children)

    def __getitem__(self, key):
        return self.children[key]

    def resolve(self, resolver):
        return {
            key: child.resolve(resolver)
            for key, child in self.children.items()
        }


class _ListNode:

    def __init__(self, children):
        self.children = children

    @classmethod
    def from_raw(cls, lst, list_schema):
        """Make an internal list node from a raw list and recurse on the children."""
        child_schema = list_schema["schema"]

        children = []
        for lst_value in lst:
            args = (lst_value, child_schema)
            if child_schema["type"] == "dict":
                r = _DictNode.from_raw(*args)
            elif child_schema["type"] == "list":
                r = _ListNode.from_raw(*args)
            else:
                r = _LeafNode.from_raw(*args)
            children.append(r)

        return cls(children)

    def __getitem__(self, ix):
        return self.children[ix]

    def resolve(self, resolver):
        return [
            child.resolve(resolver)
            for child in self.children
        ]


class _Resolver:

    def __init__(self, root, external_variables, parsers):
        self.root = root
        self.external_variables = external_variables
        self.parsers = parsers

    def interpolate(self, s, reference_path):
        exploded_path = _explode_dotted_path_string(reference_path)

        if exploded_path[0] == "self":
            substitution = self._retrieve_from_root(exploded_path)
        else:
            substitution = self._retrieve_from_external_variables(exploded_path)

        pattern = r"\$\{" + reference_path + r"\}"
        return re.sub(pattern, str(substitution), s)

    def parse(self, s, type_):
        return self.parsers[type_](s)

    def _retrieve_from_root(self, exploded_path):
        try:
            referred_leaf_node = _get_path(self.root, exploded_path[1:])
        except KeyError:
            raise exceptions.ResolutionError(f"Cannot resolve {exploded_path}")

        return referred_leaf_node.resolve(self)

    def _retrieve_from_external_variables(self, exploded_path):
        try:
            return _get_path(self.external_variables, exploded_path)
        except KeyError:
            raise exceptions.ResolutionError(f"Cannot find {exploded_path} in external variables.")



def _parse_path_component(c):
    if c.isnumeric():
        return int(c)
    else:
        return c


def _get_path(dct, path):
    if isinstance(path, str):
        path = path.split(".")

    if len(path) == 1:
        return dct[path[0]]
    return _get_path(dct[path[0]], path[1:])




def resolve(raw_cfg, schema, external_variables=None, override_parsers=None):
    if external_variables is None:
        external_variables = {}
    elif "self" in external_variables:
        raise ValueError('external_variables cannot contain a "self" key; it is reserved.')

    parsers = _update_parsers(override_parsers)
    root = _build_configuration_tree(raw_cfg, schema, external_variables, parsers)
    resolver = _Resolver(root, external_variables, parsers)
    return root.resolve(resolver)



def _update_parsers(overrides):
    parsers = _parsers.DEFAULT_PARSERS
    if overrides is not None:
        for type_, parser in overrides.items():
            parsers[type_] = parser
    return parsers




def _resolve_from_self(path, components):
    exploded_path = _explode_dotted_path_string(path)
    try:
        referred_node = _get_path(components.root, exploded_path[1:])
    except KeyError:
        raise exceptions.ResolutionError(f"Cannot resolve {path}")

    _resolve_leaf_node(referred_node, components)
    return referred_node.resolved


def _resolve_from_external_variables(path, external_variables):
    exploded_path = _explode_dotted_path_string(path)
    try:
        return _get_path(external_variables, exploded_path)
    except KeyError:
        raise exceptions.ResolutionError(f"Cannot find {path} in external_variables.")


def _interpolate(s, path, components):
    exploded_path = _explode_dotted_path_string(path)
    if exploded_path[0] == "self":
        substitution = _resolve_from_self(path, components)
    else:
        substitution = _resolve_from_external_variables(path, components.external_variables)

    return _substitute_reference(s, path, substitution)


def _substitute_reference(s, reference, replacement_value):
    pattern = r"\$\{" + reference + r"\}"
    return re.sub(pattern, str(replacement_value), s)


def _build_value_store(external_variables, root, parsers):

    def _retrieve_from_self(exploded_path):
        leaf_node = _get_path(root, exploded_path[1:])
        leaf_node.resolve(value_store, parsers)

    def value_store(path):
        exploded_path = _explode_dotted_path_string(path)

        if exploded_path[0] == "self":
            return _retrieve_from_self(exploded_path)
        else:
            return _retrieve_from_external_variables(exploded_path)

    return value_store

