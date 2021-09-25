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
child nodes. The "real work" occurs in _LeafNode.resolve(). Here, the
resolution of a leaf node is orchestrated: references to other leaf nodes and
to external variables are interpolated and the parser is applied.

Interpolation is done using the Jinja2 template engine. To facilitate this,
each internal node type defines __getitem__. If the child node being retrieved
is a _LeafNode, it is resolved. When interpolation is performed, the root
node is passed as the variable named "this". Values of the resolved leaf nodes
can be referenced using the standard Jinja dot notation; for example:

    ${ this.foo.bar.baz }

"""
import dataclasses
import re
import typing

import jinja2

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

    return root.resolve()


def _provide_context_to_leaf_nodes(node, resolution_context):
    """Set the resolution_context for all leaf nodes, recursively."""
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
    parent
        The parent node of the node being built. Can be `None`.

    Returns
    -------
        The configuration tree.

    """
    if raw_cfg is None:
        if "nullable" in schema and schema["nullable"]:
            return _LeafNode.from_raw(None, {"type": "any"}, keypath, parent=parent)
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
        return _DictNode.from_raw(raw_cfg, schema, keypath, parent=parent)
    elif isinstance(raw_cfg, list):
        if schema["type"] == "any":
            schema = {
                "type": "list",
                "element_schema": {"type": "any", "nullable": True},
            }
        return _ListNode.from_raw(raw_cfg, schema, keypath, parent=parent)
    else:
        return _LeafNode.from_raw(raw_cfg, schema, keypath, parent=parent)


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
    parent
        The parent of this node. Can be `None`, in which case this is the root
        of the tree.

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

    def __getitem__(self, ix):
        child = self.children[ix]
        if isinstance(child, _LeafNode):
            return child.resolve()
        else:
            return child

    @property
    def root(self):
        if self.parent is None:
            return self
        else:
            return self.parent.root

    def resolve(self):
        """Recursively resolve the _DictNode into a dictionary."""
        return {key: child.resolve() for key, child in self.children.items()}


def _populate_required_keys_children(children, dct, dict_schema, parent, keypath):
    required_keys = dict_schema.get("required_keys", {})

    for key, key_schema in required_keys.items():
        if key not in dct:
            raise exceptions.ResolutionError(
                "Missing required key.", (keypath + (key,))
            )

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

        children[key] = _build_configuration_tree_node(
            value, key_schema, parent, keypath + (key,)
        )


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
    parent
        The parent of this node. Can be `None`, in which case this is the root
        of the tree.

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
            r = _build_configuration_tree_node(
                lst_value, child_schema, node, keypath + (i,)
            )
            children.append(r)

        node.children = children
        return node

    def __getitem__(self, ix):
        child = self.children[ix]
        if isinstance(child, _LeafNode):
            return child.resolve()
        else:
            return child

    @property
    def root(self):
        if self.parent is None:
            return self
        else:
            return self.parent.root

    def resolve(self):
        """Recursively resolve the _ListNode into a list."""
        return [child.resolve() for child in self.children]


class _LeafNode:
    """Represents a leaf of the configuration tree.

    Attributes
    ----------
    raw
        The "raw" value of the leaf node as it appeared in the raw configuration.
        This can be any type.
    type_ : str
        A string describing the expected type of this leaf once resolved.
    parent
        The parent of this node. Can be `None`, in which case this is the root
        of the tree.
    resolution_context: Optional[_ResolutionContext]
        An instance of _ResolutionContext providing a context for resolution.
        This is typically not set when the _LeafNode is created. Rather, it
        is recursively set on all leaf nodes via a tree search.
    nullable : Optional[bool]
        Whether the value can be None or not. If raw is None this is True, it
        is not parsed (no matter what type_ is). Default: False.

    """

    def __init__(
        self, raw, type_, parent, keypath, resolution_context=None, nullable=False
    ):
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

    @property
    def root(self):
        if self.parent is None:
            return self
        else:
            return self.parent.root

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

    def resolve(self):
        """Resolve the leaf's value by 1) interpolating and 2) parsing.

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
        if isinstance(s, str):
            s = self._safely(self._interpolate, s)

        if self.nullable and self.raw is None:
            self._resolved = None
        else:
            self._resolved = self._safely(self._parse, s, self.type_)

        return self._resolved

    def _interpolate(self, s):
        """Replace a reference keypath with its resolved value.

        Parameters
        ----------
        s : str
            A configuration string with references to other values.

        Returns
        -------
        The interpolated string.

        """
        template = jinja2.Template(
            s, variable_start_string="${", variable_end_string="}"
        )

        try:
            return template.render(
                **self.resolution_context.external_variables, this=self.root
            )
        except jinja2.exceptions.UndefinedError as exc:
            raise exceptions.ResolutionError(str(exc), self.keypath)

    def _parse(self, s, type_):
        """Parse the configuration string into its final type."""
        try:
            parser = self.resolution_context.parsers[type_]
        except KeyError:
            raise exceptions.Error(f'No parser for type "{type_}".')

        return parser(s)

    def _safely(self, fn, *args):
        try:
            return fn(*args)
        except exceptions.Error as exc:
            raise exceptions.ResolutionError(exc, self.keypath)


@dataclasses.dataclass
class _ResolutionContext:

    external_variables: typing.Mapping
    parsers: typing.Mapping


# validation
# ----------


def _validate_schema(schema, keypath=tuple(), allow_default=False):
    if not isinstance(schema, dict):
        raise exceptions.InvalidSchemaError("Schema must be a dict.", keypath)

    if "type" not in schema:
        raise exceptions.InvalidSchemaError("Required key missing.", keypath + (type,))

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
        allowed.add("default")

    extra = provided - allowed
    missing = required - provided

    if extra:
        exemplar = extra.pop()
        raise exceptions.InvalidSchemaError("Unexpected key.", keypath + (exemplar,))

    if missing:
        exemplar = missing.pop()
        raise exceptions.InvalidSchemaError("Missing key.", keypath + (exemplar,))


def _validate_dict_schema(dict_schema, keypath, allow_default):
    _check_keys(
        dict_schema.keys(),
        required={"type"},
        optional={"required_keys", "optional_keys", "extra_keys_schema", "nullable"},
        keypath=keypath,
        allow_default=allow_default,
    )

    for key, key_schema in dict_schema.get("required_keys", {}).items():
        _validate_schema(key_schema, keypath + ("required_keys", key))

    for key, key_schema in dict_schema.get("optional_keys", {}).items():
        _validate_schema(
            key_schema, keypath + ("optional_keys", key), allow_default=True
        )

    if "extra_keys_schema" in dict_schema:
        _validate_schema(
            dict_schema["extra_keys_schema"], keypath + ("extra_keys_schema",)
        )


def _validate_list_schema(list_schema, keypath, allow_default):
    _check_keys(
        list_schema.keys(),
        required={"type", "element_schema"},
        optional={"nullable"},
        keypath=keypath,
        allow_default=allow_default,
    )

    _validate_schema(
        list_schema["element_schema"], keypath + ("element_schema",), allow_default
    )


def _validate_leaf_schema(leaf_schema, keypath, allow_default):
    _check_keys(
        leaf_schema.keys(),
        required={"type"},
        optional={"nullable"},
        keypath=keypath,
        allow_default=allow_default,
    )


def _validate_any_schema(any_schema, keypath, allow_default):
    _check_keys(
        any_schema.keys(),
        required={"type"},
        optional={"nullable"},
        keypath=keypath,
        allow_default=allow_default,
    )
