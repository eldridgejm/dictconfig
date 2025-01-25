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

import copy

from . import parsers as _parsers
from ._schemas import validate_schema
from ._tree import (
    _ResolutionContext,
    _build_configuration_tree_node,
    _provide_context_to_leaf_nodes,
)


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


def _update_parsers(overrides):
    """Override some of the default parsers.

    Returns a dictionary of all parsers."""
    parsers = DEFAULT_PARSERS.copy()
    if overrides is not None:
        for type_, parser in overrides.items():
            parsers[type_] = parser
    return parsers


def resolve(
    raw_cfg,
    schema,
    external_variables=None,
    override_parsers=None,
    schema_validator=validate_schema,
    preserve_type=False,
):
    """Resolve a raw configuration by interpolating and parsing its entries.

    The raw configuration can be a dictionary, list, or a non-container type;
    resolution will be done recursively. In any case, the provided schema must
    match the type of the raw configuration; for example, if the raw
    configuration is a dictionary, the schema must be a dict schema.

    Default parsers are provided which attempt to convert raw values to the
    specified types. They are:

        - "integer": :func:`dictconfig.parsers.arithmetic` with type `int`
        - "float": :func:`dictconfig.parsers.arithmetic` with type `float`
        - "string": n/a.
        - "boolean": :func:`dictconfig.parsers.logic`
        - "date": :func:`dictconfig.parsers.smartdate`
        - "datetime": :func:`dictconfig.parsers.smartdatetime`

    These parsers provide "smart" behavior, allowing values to be expressed in
    a variety of formats. They can be overridden by providing a dictionary of
    parsers to `override_parsers`.

    A dictionary of external variables can be provided; these will be available
    at interpolation time. A special key, ``this``, is reserved and cannot
    be used as an external variable. It refers to the root of the resolved
    configuration.

    This function uses the `jinja2` template engine for interpolation. This means
    that many powerful `Jinja2` features can be used. For example, a `Jinja2` supports
    a ternary operator, so dictionaries can contain expressions like the following:"

    .. code-block:: python

        {
            'x': 10,
            'y': 3,
            'z': '${ this.x if this.x > this.y else this.y }'
        }

    Typically, `raw_cfg` will be a plain Python dictionary. Sometimes, however,
    it may be another mapping type that behaves like a `dict`, but has some
    additional functionality. One example is the `ruamel` package which is
    capable of round-tripping yaml, comments and all. To accomplish this,
    ruamel produces a dict-like object which stores the comments internally. If
    we resolve this dict-like object with :code:`preserve_type = False`, then
    we'll lose these comments; therefore, we should use :code:`preserve_type =
    True`.

    At present, type preservation is done by constructing the resolved output
    as normal, but then making a deep copy of `raw_cfg` and recursively copying
    each leaf value into this deep copy. Therefore, there is a performance
    cost.

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
        42 in the dictionary :code:`{'foo': {'bar': {'baz': 42}}}`. Cannot contain a key
        named "this".
    override_parsers
        A dictionary mapping leaf type names to parser functions. The parser functions
        should take the raw value (after interpolation) and convert it to the specified
        type. If this is not provided, the default parsers are used.
    preserve_type : bool (default: False)
        If False, the return value of this function is a plain dictionary. If this is
        True, however, the return type will be the same as the type of raw_cfg. See
        below for details.

    Raises
    ------
    InvalidSchemaError
        If the schema is not valid.
    ResolutionError
        If the configuration does not match the schema, if there is a circular
        reference, or there is some other issue with the configuration itself.

    """
    if external_variables is None:
        external_variables = {}

    if "this" in external_variables:
        raise ValueError(
            'external_variables cannot contain a "this" key; it is reserved.'
        )

    if schema_validator is not None:
        schema_validator(schema)

    parsers = _update_parsers(override_parsers)
    resolution_context = _ResolutionContext(external_variables, parsers)

    root = _build_configuration_tree_node(raw_cfg, schema)
    _provide_context_to_leaf_nodes(root, resolution_context)

    resolved = root.resolve()

    if not preserve_type:
        return resolved
    else:
        output = copy.deepcopy(raw_cfg)
        _copy_into(output, resolved)
        return output
