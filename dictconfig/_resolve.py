"""Provides the resolve() function for resolving raw configurations.

A raw configuration is a dictionary, list, or non-container type. If it is a
dictionary, its keys are strings and values are, recursively, raw
configurations. If it is a list, its entries are raw configurations.

The code in this module works by building a tree representation of the raw
configuration.  Dictionaries and lists become internal nodes of the tree, and
non-container values become leaf nodes. These nodes are represented by the
_DictNode, _ListNode, and _LeafNode classes below.

Each node type has a `.resolve()` method that knows how to resolve the node
itself and recursively delegates the resolution of the child nodes. For
instance, _DictNode.resolve() returns a dictionary whose values are resolved
child nodes. The "real work" occurs in two key places. First is _LeafNode.resolve().
Here, the resolution of a leaf node is orchestrated: references to other leaf
nodes and to external variables are interpolated and the parser is applied. The
actual implementation of the interpolating code is in _Resolver; an instance of
the _Resolver is passed to a node when it is resolved. The reason for involving the
_Resolver class is that individual nodes know little about the world: they do not know
the root of their tree or what parsers are available. While this information could be
supplied when the node is instantiated, it is thought cleaner to keep it separate.

"""
import re

from ._schema import validate_dict_schema, validate_list_schema, validate_leaf_schema
from . import exceptions
from . import parsers as _parsers

# the default parsers used by resolve()
DEFAULT_PARSERS = {
    "integer": _parsers.arithmetic(int),
    "float": _parsers.arithmetic(float),
    "string": str,
    "boolean": _parsers.logic,
    "date": _parsers.smartdate,
    "datetime": _parsers.smartdatetime,
}


def resolve(raw_cfg, schema, external_variables=None, override_parsers=None):
    """Resolve a raw configuration by interpolating and parsing its entries.

    The raw configuration can be a dictionary, list, or a non-container type;
    resolution will be done recursively. In any case, the provided schema must
    match the type of the raw configuration; for example, if the raw
    configuration is a dictionary, the schema must be a dict schema.

    Parameters
    ----------
    raw_cfg
        The raw configuration.
    schema
        The schema describing the types in the raw configuration.
    external_variables
        A (nested) dictionary of external variables that may be interpolated into
        the raw configuration. External variables can be referred to by dotted paths in
        the configuration. For example, :code:`${foo.bar.baz}` will reference the value
        42 in the dictionary :code:`{'foo': {'bar': {'baz': 42}}}`.
    override_parsers
        A dictionary mapping leaf type names to parser functions. The parser functions
        should take the raw value (after interpolation) and convert it to the specified
        type. If this is not provided, the default parsers are used.

    """
    if external_variables is None:
        external_variables = {}
    elif "self" in external_variables:
        raise ValueError(
            'external_variables cannot contain a "self" key; it is reserved.'
        )

    parsers = _update_parsers(override_parsers)
    root = _build_configuration_tree(raw_cfg, schema)
    resolver = _Resolver(root, external_variables, parsers)
    return root.resolve(resolver)


def _update_parsers(overrides):
    """Override some of the default parsers. 

    Returns a dictionary of all parsers."""
    parsers = DEFAULT_PARSERS.copy()
    if overrides is not None:
        for type_, parser in overrides.items():
            parsers[type_] = parser
    return parsers


# configuration trees
# -------------------
# A configuration tree is the internal representation of a configuration. The nodes of
# tree come in three types:
#
#   _LeafNode: a leaf node in the tree that can be resolved into a non-container value,
#       such as an integer.
#
#   _DictNode: an internal node that behaves like a dictionary, mapping keys to child
#       nodes.
#
#   _LeafNode: an internal node that behaves like a list, mapping indices to child
#       nodes.


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
        root = _DictNode.from_raw(*args)
    elif isinstance(raw_cfg, list):
        validate_list_schema(schema)
        root = _ListNode.from_raw(*args)
    else:
        validate_leaf_schema(schema)
        root = _LeafNode.from_raw(*args)

    return root


# denotes that a node is currently being resolved
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
    type_ : str
        A string describing the expected type of this leaf once resolved.

    """

    def __init__(self, raw, type_):
        self.raw = raw
        self.type_ = type_

        # The resolved value of the leaf node. There are two special values. If
        # this is _UNDISCOVERED, the resolution process has not yet discovered
        # the leaf node (this is the default value). If this is _PENDING, a
        # step in the resolution process has started to resolve the leaf. Otherwise,
        # this contains the resolved value.
        self._resolved = _UNDISCOVERED

    @classmethod
    def from_raw(cls, raw, leaf_schema):
        """Create a leaf node from the raw configuration and schema."""
        return cls(raw, leaf_schema["type"])

    @property
    def references(self):
        """Return a list of all of the references in the raw value.

        If the raw value is not a string, there are no references and an empty list is
        returned.

        Example
        -------

        >>> leaf = _LeafNode('this is ${self.x} and ${self.y}', 'string')
        >>> leaf.references
        ['self.x', 'self.y']

        """
        if not isinstance(self.raw, str):
            return []

        pattern = r"\$\{(.+?)\}"
        return re.findall(pattern, self.raw)

    def resolve(self, resolver):
        """Resolve the leaf's value by 1) interpolating and 2) parsing.

        Parameters
        ----------
        resolver : _Resolver
            A _Resolver instance. The resolver is responsible for carrying out the 
            interpolation of references and for doing the actual parsing.

        Returns
        -------
        The resolved value.

        """

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
    """Represents an internal dictionary node in a configuration tree.

    Attributes
    ----------
    children
        A dictionary of child nodes.

    """

    def __init__(self, children):
        self.children = children

    @classmethod
    def from_raw(cls, dct, dict_schema):
        """Construct a _DictNode from a raw configuration dictionary and its schema."""
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
        """Recursively resolve the _DictNode into a dictionary."""
        return {key: child.resolve(resolver) for key, child in self.children.items()}


class _ListNode:
    """Represents an internal list node in a configuration tree.

    Attributes
    ----------
    children
        A list of the node's children.

    """

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
        """Recursively resolve the _ListNode into a list."""
        return [child.resolve(resolver) for child in self.children]


# resolver
# --------
# A resolver is responsible for managing the resolution context. When a leaf node is
# resolved, it needs to know how to interpolate its references into a final string
# representation, and how to parse this string representation into its final
# resolved value. A resolver manages this by keeping track of the configuration tree's
# root, the external variables, and the parsers for each type.


class _Resolver:
    def __init__(self, root, external_variables, parsers):
        self.root = root
        self.external_variables = external_variables
        self.parsers = parsers

    def interpolate(self, s, reference_path):
        """Replace a reference path with its resolved value.

        Parameters
        ----------
        s : str
            A configuration string with references to other values.
        reference_path : str
            The reference path that will be resolved and replaced.

        Returns
        -------
        The interpolated string.

        """
        exploded_path = _explode_dotted_path_string(reference_path)

        if exploded_path[0] == "self":
            substitution = self._retrieve_from_root(exploded_path)
        else:
            substitution = self._retrieve_from_external_variables(exploded_path)

        pattern = r"\$\{" + reference_path + r"\}"
        return re.sub(pattern, str(substitution), s)

    def _retrieve_from_root(self, exploded_path):
        try:
            referred_leaf_node = _get_path(self.root, exploded_path[1:])
        except KeyError:
            path = "${" + ".".join(exploded_path) + "}"
            raise exceptions.ResolutionError(f"Cannot resolve {path}")

        return referred_leaf_node.resolve(self)

    def _retrieve_from_external_variables(self, exploded_path):
        try:
            return _get_path(self.external_variables, exploded_path)
        except KeyError:
            raise exceptions.ResolutionError(
                f"Cannot find {exploded_path} in external variables."
            )

    def parse(self, s, type_):
        """Parse the configuration string into its final type."""
        try:
            parser = self.parsers[type_]
        except KeyError:
            raise exceptions.ResolutionError(f'No parser for type "{type_}".')

        return parser(s)


# helpers
# -------


def _explode_dotted_path_string(path):
    """Takes a dotted path string like foo.bar.baz and returns a tuple of parts.

    If a path component is a number, the corresponding part is an integer.

    """

    def _parse_path_component(c):
        if c.isnumeric():
            return int(c)
        else:
            return c

    components = path.split(".")
    return tuple(_parse_path_component(c) for c in components)


def _get_path(dct, exploded_path):
    """Retrieve a dictionary entry using an exploded path."""
    if len(exploded_path) == 1:
        return dct[exploded_path[0]]
    return _get_path(dct[exploded_path[0]], exploded_path[1:])
