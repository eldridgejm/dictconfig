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
import dataclasses
import re
import typing

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
    "any": lambda x: x,
}


def validate_schema(schema):
    """Validate a schema.

    Raises
    ------
    InvalidSchemaError
        If the schema is not valid.

    """
    _validate_schema(schema)


def resolve(
    raw_cfg,
    schema,
    external_variables=None,
    override_parsers=None,
    schema_validator=validate_schema,
):
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
        the raw configuration. External variables can be referred to by dotted keypaths in
        the configuration. For example, :code:`${foo.bar.baz}` will reference the value
        42 in the dictionary :code:`{'foo': {'bar': {'baz': 42}}}`.
    override_parsers
        A dictionary mapping leaf type names to parser functions. The parser functions
        should take the raw value (after interpolation) and convert it to the specified
        type. If this is not provided, the default parsers are used.

    Raises
    ------
    InvalidSchemaError
        If the schema is not valid.

    """
    if external_variables is None:
        external_variables = {}

    if "self" in external_variables:
        raise ValueError(
            'external_variables cannot contain a "self" key; it is reserved.'
        )

    if schema_validator is not None:
        schema_validator(schema)

    parsers = _update_parsers(override_parsers)
    resolution_context = _ResolutionContext(external_variables, parsers)

    root = _build_configuration_tree_node(raw_cfg, schema)
    _provide_context_to_leaf_nodes(root, resolution_context)

    resolver = _Resolver(root, external_variables, parsers)
    return root.resolve(resolver)


def _provide_context_to_leaf_nodes(node, resolution_context):
    if isinstance(node, _LeafNode):
        node.resolution_context = resolution_context
    elif isinstance(node, _DictNode):
        for child in node.children.values():
            _provide_context_to_leaf_nodes(child, resolution_context)
    elif isinstance(node, _ListNode):
        for child in node.children:
            _provide_context_to_leaf_nodes(child, resolution_context)



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


def _build_configuration_tree_node(raw_cfg, schema, parent=None, keypath=tuple()):
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
    if raw_cfg is None:
        if "nullable" in schema and schema["nullable"]:
            return _LeafNode.from_raw(None, {"type": "any"}, keypath)
        else:
            raise exceptions.ResolutionError("Unexpectedly null.", keypath)

    # construct the configuration tree
    # the configuration tree is a nested container whose terminal leaf values
    # are _LeafNodes. "Internal" nodes are dictionaries or lists.
    if isinstance(raw_cfg, dict):
        if schema["type"] == "any":
            schema = {
                "type": "dict",
                "extra_keys_schema": {"type": "any", "nullable": True},
            }
        return _DictNode.from_raw(raw_cfg, schema, keypath)
    elif isinstance(raw_cfg, list):
        if schema["type"] == "any":
            schema = {
                "type": "list",
                "element_schema": {"type": "any", "nullable": True},
            }
        return _ListNode.from_raw(raw_cfg, schema, keypath)
    else:
        return _LeafNode.from_raw(raw_cfg, schema, keypath)


# denotes that a node is currently being resolved
_PENDING = object()

# denotes that the leaf node has not yet been discovered
_UNDISCOVERED = object()


class _DictNode:
    """Represents an internal dictionary node in a configuration tree.

    Attributes
    ----------
    children
        A dictionary of child nodes.

    """

    def __init__(self, children=None, parent=None):
        self.children = {} if children is None else children
        self.parent = parent

    @classmethod
    def from_raw(cls, dct, dict_schema, keypath, parent=None):
        """Construct a _DictNode from a raw configuration dictionary and its schema."""
        node = cls()

        if parent is not None:
            node.parent = parent

        children = {}
        _populate_required_keys_children(children, dct, dict_schema, node, keypath)
        _populate_optional_keys_children(children, dct, dict_schema, node, keypath)
        _populate_extra_keys_children(children, dct, dict_schema, node, keypath)

        node.children = children
        return node

    def __getitem__(self, key):
        return self.children[key]

    def resolve(self, resolver):
        """Recursively resolve the _DictNode into a dictionary."""
        return {key: child.resolve(resolver) for key, child in self.children.items()}


def _populate_required_keys_children(children, dct, dict_schema, parent, keypath):
    required_keys = dict_schema.get("required_keys", {})

    for key, key_schema in required_keys.items():
        if key not in dct:
            raise exceptions.ResolutionError("Missing required key.", (keypath + (key,)))

        children[key] = _build_configuration_tree_node(
            dct[key], key_schema, parent, keypath + (key,)
        )


def _populate_optional_keys_children(children, dct, dict_schema, parent, keypath):
    optional_keys = dict_schema.get("optional_keys", {})

    for key, key_schema in optional_keys.items():
        if key in dct:
            # key is not missing
            value = dct[key]
        elif "default" in key_schema:
            # key is missing and default was provided
            value = key_schema["default"]
        else:
            # key is missing and no default was provided
            continue

        children[key] = _build_configuration_tree_node(value, key_schema, parent, keypath + (key,))


def _populate_extra_keys_children(children, dct, dict_schema, parent, keypath):
    required_keys = dict_schema.get("required_keys", {})

    optional_keys = dict_schema.get("optional_keys", {})
    expected_keys = set(required_keys) | set(optional_keys)
    extra_keys = dct.keys() - expected_keys

    if extra_keys and "extra_keys_schema" not in dict_schema:
        raise exceptions.ResolutionError(
            f"Unexpected extra key.", keypath + (extra_keys.pop(),)
        )

    for key in extra_keys:
        children[key] = _build_configuration_tree_node(
            dct[key], dict_schema["extra_keys_schema"], parent, keypath + (key,)
        )


class _ListNode:
    """Represents an internal list node in a configuration tree.

    Attributes
    ----------
    children
        A list of the node's children.

    """

    def __init__(self, children=None, parent=None):
        self.children = {} if children is None else {}
        self.parent = parent

    @classmethod
    def from_raw(cls, lst, list_schema, keypath, parent=None):
        """Make an internal list node from a raw list and recurse on the children."""
        node = cls()

        child_schema = list_schema["element_schema"]

        children = []
        for i, lst_value in enumerate(lst):
            r = _build_configuration_tree_node(lst_value, child_schema, node, keypath + (i,))
            children.append(r)

        node.children = children
        return node

    def __getitem__(self, ix):
        return self.children[ix]

    def resolve(self, resolver):
        """Recursively resolve the _ListNode into a list."""
        return [child.resolve(resolver) for child in self.children]


class _LeafNode:
    """Represents a leaf of the configuration tree.

    Attributes
    ----------
    raw
        The "raw" value of the leaf node as it appeared in the raw configuration.
        This can be any type.
    type_ : str
        A string describing the expected type of this leaf once resolved.
    nullable : bool
        Whether the value can be None or not. If raw is None this is True, it
        is not parsed (no matter what type_ is). Default: False.

    """

    def __init__(self, raw, type_, parent, keypath, resolution_context=None, nullable=False):
        self.raw = raw
        self.type_ = type_
        self.parent = parent
        self.keypath = keypath
        self.nullable = nullable
        self.resolution_context = resolution_context

        # The resolved value of the leaf node. There are two special values. If
        # this is _UNDISCOVERED, the resolution process has not yet discovered
        # the leaf node (this is the default value). If this is _PENDING, a
        # step in the resolution process has started to resolve the leaf. Otherwise,
        # this contains the resolved value.
        self._resolved = _UNDISCOVERED

    @classmethod
    def from_raw(cls, raw, leaf_schema, keypath, nullable=False, parent=None):
        """Create a leaf node from the raw configuration and schema."""
        return cls(raw, leaf_schema["type"], parent, keypath, nullable)

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
            raise exceptions.ResolutionError("Circular reference", self.keypath)

        if self._resolved is not _UNDISCOVERED:
            return self._resolved

        self._resolved = _PENDING

        s = self.raw
        for reference_path in self.references:
            s = self._safely(resolver.interpolate, s, reference_path)

        if self.nullable and self.raw is None:
            self._resolved = None
        else:
            self._resolved = self._safely(resolver.parse, s, self.type_)
        return self._resolved

    @property
    def references(self):
        """Return a list of all of the references in the raw value.

        Surrouding whitespace is ignored. That is, ${ self.y } is the same as ${self.y}.

        If the raw value is not a string, there are no references and an empty list is
        returned.

        Example
        -------

        >>> leaf = _LeafNode('this is ${self.x} and ${ self.y }', 'string')
        >>> leaf.references
        ['self.x', 'self.y']

        """
        if not isinstance(self.raw, str):
            return []

        pattern = r"\$\{\s?(.+?)\s?\}"
        return re.findall(pattern, self.raw)

    def _interpolate(self, s, reference_path):
        """Replace a reference keypath with its resolved value.

        Parameters
        ----------
        s : str
            A configuration string with references to other values.
        reference_path : str
            The reference keypath that will be resolved and replaced.

        Returns
        -------
        The interpolated string.

        """
        exploded_path = _explode_dotted_path_string(reference_path)

        if exploded_path[0] == "self":
            substitution = self._retrieve_from_root(exploded_path)
        else:
            substitution = self._retrieve_from_external_variables(exploded_path)

        pattern = r"\$\{\s?" + reference_path + r"\s?\}"
        return re.sub(pattern, str(substitution), s)

    


    def _safely(self, fn, *args):
        try:
            return fn(*args)
        except exceptions.Error as exc:
            raise exceptions.ResolutionError(exc, self.keypath)


# resolver
# --------
# A resolver is responsible for managing the resolution context. When a leaf node is
# resolved, it needs to know how to interpolate its references into a final string
# representation, and how to parse this string representation into its final
# resolved value. A resolver manages this by keeping track of the configuration tree's
# root, the external variables, and the parsers for each type.


@dataclasses.dataclass
class _ResolutionContext:

    external_variables: typing.Mapping
    parsers: typing.Mapping


class _Resolver:
    def __init__(self, root, external_variables, parsers):
        self.root = root
        self.external_variables = external_variables
        self.parsers = parsers

    def interpolate(self, s, reference_path):
        """Replace a reference keypath with its resolved value.

        Parameters
        ----------
        s : str
            A configuration string with references to other values.
        reference_path : str
            The reference keypath that will be resolved and replaced.

        Returns
        -------
        The interpolated string.

        """
        exploded_path = _explode_dotted_path_string(reference_path)

        if exploded_path[0] == "self":
            substitution = self._retrieve_from_root(exploded_path)
        else:
            substitution = self._retrieve_from_external_variables(exploded_path)

        pattern = r"\$\{\s?" + reference_path + r"\s?\}"
        return re.sub(pattern, str(substitution), s)

    def _retrieve_from_root(self, exploded_path):
        try:
            referred_leaf_node = _get_path(self.root, exploded_path[1:])
        except KeyError:
            dotted = ".".join(exploded_path)
            raise exceptions.Error(f"Cannot resolve: {dotted}")

        return referred_leaf_node.resolve(self)

    def _retrieve_from_external_variables(self, exploded_path):
        try:
            return _get_path(self.external_variables, exploded_path)
        except KeyError:
            dotted = '.'.join(exploded_path)
            raise exceptions.Error(
                f"Cannot find \"{dotted}\" in external variables."
            )

    def parse(self, s, type_):
        """Parse the configuration string into its final type."""
        try:
            parser = self.parsers[type_]
        except KeyError:
            raise exceptions.Error(f'No parser for type "{type_}".')

        return parser(s)


# helpers
# -------


def _explode_dotted_path_string(keypath):
    """Takes a dotted keypath string like foo.bar.baz and returns a tuple of parts.

    If a keypath component is a number, the corresponding part is an integer.

    """

    def _parse_path_component(c):
        if c.isnumeric():
            return int(c)
        else:
            return c

    components = keypath.split(".")
    return tuple(_parse_path_component(c) for c in components)


def _get_path(dct, exploded_path):
    """Retrieve a dictionary entry using an exploded keypath."""
    if len(exploded_path) == 1:
        return dct[exploded_path[0]]
    return _get_path(dct[exploded_path[0]], exploded_path[1:])


# validation
# ----------


def _validate_schema(schema, keypath=tuple(), allow_default=False):
    if not isinstance(schema, dict):
        raise exceptions.InvalidSchemaError("Schema must be a dict.", keypath)

    if "type" not in schema:
        raise exceptions.InvalidSchemaError('Required key missing.', keypath + (type,))

    args = (schema, keypath, allow_default)

    if schema["type"] == "dict":
        _validate_dict_schema(*args)
    elif schema["type"] == "list":
        _validate_list_schema(*args)
    else:
        _validate_leaf_schema(*args)


def _check_keys(provided, required, optional, keypath, allow_default):
    allowed = required | optional
    if allow_default:
        allowed.add('default')

    extra = provided - allowed
    missing = required - provided

    if extra:
        exemplar = extra.pop()
        raise exceptions.InvalidSchemaError('Unexpected key.', keypath + (exemplar,))

    if missing:
        exemplar = missing.pop()
        raise exceptions.InvalidSchemaError('Missing key.', keypath + (exemplar,))

def _validate_dict_schema(dict_schema, keypath, allow_default):
    _check_keys(
            dict_schema.keys(),
            required={'type'},
            optional={'required_keys', 'optional_keys', 'extra_keys_schema', 'nullable'},
            keypath=keypath,
            allow_default=allow_default
            )

    for key, key_schema in dict_schema.get('required_keys', {}).items():
        _validate_schema(key_schema, keypath + ('required_keys', key))

    for key, key_schema in dict_schema.get('optional_keys', {}).items():
        _validate_schema(key_schema, keypath + ('optional_keys', key), allow_default=True)

    if 'extra_keys_schema' in dict_schema:
        _validate_schema(dict_schema['extra_keys_schema'], keypath + ('extra_keys_schema',))


def _validate_list_schema(list_schema, keypath, allow_default):
    _check_keys(
            list_schema.keys(),
            required={'type', 'element_schema'},
            optional={'nullable'},
            keypath=keypath,
            allow_default=allow_default
            )

    _validate_schema(list_schema['element_schema'], keypath + ('element_schema',), allow_default)


def _validate_leaf_schema(leaf_schema, keypath, allow_default):
    _check_keys(
            leaf_schema.keys(),
            required={'type'},
            optional={'nullable'},
            keypath=keypath,
            allow_default=allow_default
            )


def _validate_any_schema(any_schema, keypath, allow_default):
    _check_keys(
            any_schema.keys(),
            required={'type'},
            optional={'nullable'},
            keypath=keypath,
            allow_default=allow_default
            )
