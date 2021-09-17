Welcome to dictconfig's documentation!
======================================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

A straightforward way of configuring a piece of Python software is to read
configuration settings from a file (usually JSON or YAML) into a Python
dictionary. While this is convenient, this approach has some limitations;
namely, fields within a JSON or YAML file cannot make use of variables, nor can
they reference one another.

`dictconfig` is a Python package that aims to ease these limitations by
supporting:

1. **External Variables**: Configuration values can reference external
   variables supplied by the program reading the configuration.
2. **Internal References**: The configuration can reference other settings
   within the same configuration.
3. **Domain-specific languages**: Custom parsers can be provided to convert
   configuration options to Python types in a domain-specific way. `dateconfig`
   comes with parsers for interpreting arithmetic expressions (e.g., `"(4 + 6) / 2"`),
   logical expressions (e.g., `"True and (False or True)"`), and relative datetimes
   (e.g., `"7 days after 2021-10-10"`).

Quick Start
-----------

Below is an example of what `dictconfig` offers. Suppose we have a YAML file
containing:

.. code:: yaml

   x: 10
   y: 32
   z: ${self.x} + ${self.y}
   released: ${foo.bar}
   due: ${self.x} days after ${self.released}

Intuitively, we want the value of `z` to be the sum of `x` and `y` (i.e., 42).
In this example, :code:`${foo.bar}` refers to an "external variable"
provided by the software that reads the config.  Apparently, we want the value
of `due` to resolve to ten days after this release date.

However, if we read this YAML into a Python dictionary :code:`dct` using any
standard YAML loader, the value of `z` will simply be the string above; it will
*not* be the number 42. Likewise, the value of the `released` and `due` fields
will not be as desired.

With `dictconfig`'s interpolation and reference features, however, we can resolve
the configuration above into what we expect. First, we must specify a *schema*.
A *schema* is a Python dictionary that tells `dictconfig` what types to expect
for each configuration option. Here is a schema for this configuration file
that says that the keys `x`, `y`, and `z` are all integers and that `released`
and `due` are dates:

.. code:: python

    schema = {
        "type": "dict",
        "schema": {
            "x": {"type": "integer"},
            "y": {"type": "integer"},
            "z": {"type": "integer"},
            "released": {"type": "date"},
            "due": {"type": "date"}
        }
    }

As can be seen from above, a schema is a nested dictionary describing the expected
types of configuration values. For a more precise definition of a schema, see the
`Schemata`_ section below.

Next, we call :code:`dictconfig.resolve()` to *resolve* the configuration. We provide
a dictionary of external variables that can be resolved.


.. code:: python

   >>> import dictconfig
   >>> external_variables = {
       'foo': {'bar': '2021-10-01', 'baz': None},
       'bar': 42
   }
   >>> dictconfig.resolve(dct, schema, external_variables=external_variables)
   {
       "x": 10,
       "y": 32,
       "z": 42,
       "released": datetime.date(2021, 10, 1),
       "due": datetime.date(2021, 10, 11),
   }

During resolution, the values of `x` and `y` are looked up and interpolated
into the definition of `z`, resulting in the string `10 + 32`. The schema tells
`dictconfig` that the result should be an integer, so an attempt is made to
convert this string to an `int`. The default string-to-int parser in
`dictconfig` is capable of evaluating basic arithmetic expressions, and
therefore produces the value of 42.

Likewise, the reference to :code:`${foo.bar}` is resolved from the external variables
and converted to a date as per the schema. The `due` field is resolved by referring to
the `released` field. The default date parser is smart enough to handle
relative dates written as above. See the `Parsers`_ section below for more
information on the parsers.

Usage
-----

This section describes the usage of the package in greater detail, starting
with the creation of schemata.

Schemata
~~~~~~~~

It is necessary to define a schema in order to specify the types of
configuration values.  But before describing the grammar of a schema, it will
be useful to reconceptualize the configuration as a tree.  For example, take
the following dictionary of options:

.. code:: python

   config = {
        title = 'My Book'
        release = {
            date = '2021-10-10',
            via = 'email'
        },
        authors = ['me', 'you', 'everyone']
   }

The root of the configuration tree is a dictionary with keys `title`,
`release`, and `authors`. This root has three children: first, the string `"My
Book"` corresponding to the `title` key. This child node is a leaf. The second
child is the dictionary corresponding to the `release` key; it is not a leaf
node. Instead, it is an *internal* dictionary node with two string-type leaf
nodes as children. The third child of the root is the list corresponding to the
authors; it is also not a leaf node. It is again an *internal* list node with
three string-type leaf nodes as children.

In general, internal nodes of the configuration tree are either dictionaries or
lists. Leaf nodes are non-container types, like strings, numbers, etc.

A *schema* defines the type of each of the nodes (internal and leaf) of the
configuration tree.  The "grammar" of a schema is roughly as follows:

.. code:: text

    <SCHEMA> = (<DICT_SCHEMA> | <LIST_SCHEMA> | <LEAF_SCHEMA>)

    <DICT_SCHEMA> = <DICT_SCHEMA_BY_KEY> | <DICT_SCHEMA_FOR_ALL_KEYS>

    <DICT_SCHEMA_BY_KEY> = {
        "type": "dict",
        schema = {
            key_1: <SCHEMA>,
            [key_2: <SCHEMA>,]
            [key_3: <SCHEMA>,]
        }
    }

    <DICT_SCHEMA_FOR_ALL_KEYS> = {
        "type": "dict",
        "valuesrules" = <SCHEMA>
    }

    <LIST_SCHEMA> = {
        "type": "list",
        "schema": <SCHEMA>
    }

    <LEAF_SCHEMA> = {
        "type": ("string" | "integer" | "float" | "boolean" | "datetime" | "any")
    }

A leaf type of "any" denotes that the raw leaf value will be left as-is, and will not be
parsed.

Optionally, a leaf value can be "nullable", meaning that `None` is a valid type. By default,
the leaf values are not nullable.

This grammar is a subset of that defined by the `Cerberus <https://docs.python-cerberus.org/en/stable/>`_ dict validator.
Therefore, `dictconfig` schemas can be parsed by Cerberus.

Here is an example of a valid schema for the configuration dictionary from
the start of this section:

.. code:: text

    {
        'type': 'dict',
        'schema': {
            'title': {'type': 'string'},
            'release': {
                'type': 'dict',
                'schema': {
                    'date': 'date',
                    'via': 'string'
                }
            },
            'authors': {
                'type': 'list',
                'schema': {'type': 'string'}
            }
        }
    }

Resolving Configurations
~~~~~~~~~~~~~~~~~~~~~~~~

Resolving a configuration is done via the :func:`dictconfig.resolve` function:

.. autofunction:: dictconfig.resolve

Resolving a leaf value in a configuration involves two steps: interpolation and
parsing.  In the easiest case, a leaf has no references to other fields or
external variables. In this case, the leaf's raw value is passed through the
appropriate parser as determined by the schema in order to convert it to its
resolved value.

On the other hand, if the leaf value contains references to other fields or
external variables, these must be interpolated before parsing. If another
configuration field is referred to, it is first resolved recursively. The
resolved value of the field (or external variable) is then cast back into a
string and interpolated into the original leaf node's value. Only then is the
parser applied to convert the leaf node's string into the final resolved value.

In summary, the resolution of leaf nodes occurs via recursive string interpolation
followed by parsing into the final type.

Parsers
~~~~~~~

.. currentmodule:: dictconfig.parsers

A parser is a function that accepts a raw value -- often, but not necessarily a
string -- and returns a resolved value with the appropriate type.

The default parsers are as follows:

- "integer": The :func:`arithmetic` parser with type `int`.
- "float": The :func:`arithmetic` parser with type `float`.
- "string": No parser needed (left as string).
- "boolean": The :func:`logic` parser.
- "date": The :func:`smartdate` parser.
- "datetime": The :func:`smartdatetime` parser.

All available parsers in :mod:`dictconfig.parsers` are shown below:

.. autosummary::

    arithmetic
    logic
    smartdate
    smartdatetime

.. autofunction:: arithmetic
.. autofunction:: logic
.. autofunction:: smartdate
.. autofunction:: smartdatetime



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
