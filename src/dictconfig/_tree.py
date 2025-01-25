"""Internal representation of a configuration.

This module does the "heavy lifting" involved in resolving a configuration. The
raw configuration is transformed into a tree of nodes. Each node knows how to
resolve itself, and how to validate itself against a schema. Resolution is
performed recursively, so that resolving a node will resolve all of its
children. References within the configuration are resolved by looking up the
target node in the tree.

"""

import dataclasses
import datetime
import re
import typing

import jinja2

from . import exceptions
from . import parsers as _parsers
from ._schemas import Schema, validate_schema


ConfigurationContainer = typing.Union["ConfigurationDict", "ConfigurationList"]
ConfigurationValue = typing.Union[
    str, int, float, bool, datetime.datetime, datetime.date, None
]
ConfigurationList = typing.List[
    typing.Union[ConfigurationContainer, ConfigurationValue]
]
ConfigurationDict = typing.Dict[
    str, typing.Union[ConfigurationContainer, ConfigurationValue]
]
Configuration = typing.Union[ConfigurationContainer, ConfigurationValue]

KeyPath = typing.Tuple[str, ...]


def _is_leaf(x):
    return not isinstance(x, dict) and not isinstance(x, list)


def _copy_into(dst, src):
    """Recursively copy the leaf values from src to dst.

    Used when preserve_type = True in resolve()
    """
    if isinstance(dst, dict):
        keys = dst.keys()
    elif isinstance(dst, list):
        keys = range(len(dst))
    else:
        raise ValueError("The destination must be a dictionary or list.")

    for key in keys:
        x = src[key]
        if _is_leaf(x):
            dst[key] = src[key]
        else:
            _copy_into(dst[key], src[key])


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
    elif isinstance(raw_cfg, str) and schema["type"] == "dict":
        return _DictReferenceNode.from_raw(raw_cfg, schema, keypath, parent=parent)
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
        node = cls(parent=parent)

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


class _DictReferenceNode:
    """A special node that references a dict in another part of the configuration."""

    def __init__(self, keypath, parent, reference_keypath, schema):
        self.keypath = keypath
        self.parent = parent
        self.reference_keypath = reference_keypath
        self.schema = schema

    @classmethod
    def from_raw(cls, cfg, dict_schema, keypath, parent=None):
        reference_keypath = cfg.strip("${}").strip().split(".")[1:]
        return cls(keypath, parent, reference_keypath, dict_schema)

    @property
    def dict_node(self):
        referenced_node = self.root
        for key in self.reference_keypath:
            if isinstance(referenced_node, _DictReferenceNode):
                referenced_node = referenced_node.dict_node
            referenced_node = referenced_node.children[key]

        referenced_cfg = referenced_node.resolve()
        return _DictNode.from_raw(
            referenced_cfg, self.schema, self.keypath, self.parent
        )

    def resolve(self):
        node = self.dict_node
        _provide_context_to_leaf_nodes(node, _ResolutionContext({}, DEFAULT_PARSERS))
        return node.resolve()

    @property
    def root(self):
        if self.parent is None:
            return self
        else:
            return self.parent.root


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
        node = cls(parent=parent)

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

        if self.type_ in {"list", "dict"}:
            # we special case this. A leaf node for whom the schema prescribes a type
            # of list or dict must be a simple reference to another part of the
            # configuration. That is, it should look like "${foo.bar.baz}". We
            # simply resolve that other part of the configuration and return it.
            self._resolved = self._resolve_reference_to_container()
        else:
            s = self.raw
            if isinstance(s, str):
                s = self._safely(self._interpolate, s)

            if self.nullable and self.raw is None:
                self._resolved = None
            else:
                self._resolved = self._safely(self._parse, s, self.type_)

        return self._resolved

    def _resolve_reference_to_container(self):
        """Resolves leaf nodes whose type is list or dict.

        If the schema says that this node should be a list or dict, then it
        must be that the configuration contains a string referring to another
        part of the configuration which is a list or dict. This function
        resolves that reference.

        """
        if not isinstance(self.raw, str):
            raise exceptions.ResolutionError(
                f"Expected a reference to a {self.type_}.", self.keypath
            )

        keypath = self.raw.strip("${}").strip().split(".")

        try:
            node = {"this": self.root}
            for key in keypath:
                node = node[key]
            return node.resolve()
        except (KeyError, TypeError):
            raise exceptions.ResolutionError(
                f"Could not resolve reference to {self.type_}.", keypath
            )

    def _interpolate(self, s: str) -> str:
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

        if s == "${this.baz.bar}":
            breakpoint()

        try:
            external_variables = self.resolution_context.external_variables
        except AttributeError:
            external_variables = {}

        try:
            return template.render(
                **external_variables, this=self.root
            )
        except jinja2.exceptions.UndefinedError as exc:
            raise exceptions.ResolutionError(str(exc), self.keypath)

    def _parse(self, s, type_):
        """Parse the configuration string into its final type."""
        try:
            parsers = self.resolution_context.parsers
        except AttributeError:
            parsers = DEFAULT_PARSERS

        try:
            parser = parsers[type_]
        except KeyError:
            raise exceptions.Error(f'No parser for type "{type_}".')

        return parser(s)

    def _safely(self, fn, *args):
        try:
            return fn(*args)
        except exceptions.Error as exc:
            raise exceptions.ResolutionError(str(exc), self.keypath)


@dataclasses.dataclass
class _ResolutionContext:
    external_variables: typing.Mapping
    parsers: typing.Mapping
