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

1. **Interpolation**: Configuration values can reference variables supplied by
   the program reading the configuration.
2. **References**: The configuration can reference other settings within the same
   configuration.
3. **Domain-specific languages**: Custom parsers can be provided to convert
   configuration options to Python types in a domain-specific way.

Quick Start
-----------

Below is an example of what `dictconfig` offers. Suppose we have a YAML file
containing:

.. code:: yaml

   x: 10
   y: 32
   z: ${x} + ${y}


Intuitively, we want the value of `z` to be the sum of `x` and `y` (i.e., 42).
If we read this into a Python dictionary :code:`dct` using any standard YAML
loader, the value of `z` will simply be the string above; it will *not* be the
number 42.

With `dictconfig`'s interpolation and reference features, however, we can resolve
the configuration above into what we expect. First, we must specify a *schema*.
A *schema* is a Python dictionary that tells `dictconfig` what types to expect
for each configuration option. Here is a schema for this configuration file
that says that the keys `x`, `y`, and `z` are all integers:

.. code:: python

    schema = {
        "type": "dict",
        "schema": {
            "x": {"type": "integer"},
            "y": {"type": "integer"},
            "z": {"type": "integer"}
        }
    }

As can be seen from above, a schema is a nested dictionary describing the expected
types of configuration values.

Next, we call :code:`dictconfig.resolve()` to *resolve* the configuration. 


.. code:: python

   >>> import dictconfig
   >>> dictconfig.resolve(dct, schema)
   {
       x: 10,
       y: 32,
       z: 42
   }

During resolution, the values of `x` and `y` are looked up and interpolated
into the definition of `z`, resulting in the string `10 + 32`. The schema tells
`dictconfig` that the result should be an integer, so an attempt is made to
convert this string to an `int`. The default string-to-int parser in
`dictconfig` is capable of evaluating basic arithmetic expressions, and
therefore produces the value of 42.

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

    <DICT_SCHEMA> = {
        type: "dict",
        schema = {
            key_1: <SCHEMA>,
            [key_2: <SCHEMA>,]
            [key_3: <SCHEMA>,]
        }
    }

    <LIST_SCHEMA> = {
        type: "list",
        schema: <SCHEMA>
    }

    <LEAF_SCHEMA> = {
        type: ("string" | "integer" | "float" | "boolean" | "datetime" | <custom_type>)
    }

Note that there are several leaf types understood by default -- "string",
"integer", "float", and so on.  However, custom leaf types may also be
provided.

This grammar is a subset of that defined by the `Cerberus <https://docs.python-cerberus.org/en/stable/>`_ dict validator.
Therefore, `dictconfig` schemas can be parsed by Cerberus.

Here is an example of a valid schema:

.. code:: text

    {
        'type': 'dict',
        'schema': {
            'name': {'type': 'string'},
            'number': {'type': 'integer'},
            'videos': {
                'type': 'list',
                'schema': {
                    'type': 'dict',
                    'schema': {
                        'title': {'type': 'string'},
                        'url': {'type': 'url'}
                    }
                }
            }
        }
    }

Resolving Configurations
------------------------

Resolving a configuration is done via the :func:`dictconfig.resolve` function:

.. autofunction:: dictconfig.resolve

Parsers
-------

.. automodule:: dictconfig.parsers

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
