dictconfig
==========

`dictconfig` is a Python library that makes it more convenient to use dictionaries
for program configuration.

The three main features of `dictconfig` are:

- **Validation**: Dictionaries can be validated to ensure that required keys
  are provided and their values have the right type, and missing optional
  values are replaced with defaults.
- **Interpolation**: Configuration values can reference other parts of the
  configuration, or even external variables supplied by the user. This allows
  for configuration following the DRY ("Don't Repeat Yourself") principle.
- **Calculation**: Configuration values can be computed from expressions.
  Built-in parsers are provided to do simple arithmetic on numbers and dates,
  as well as logical operations on booleans. Custom parsers can be added to
  handle other types.

.. testsetup:: *

   import datetime
   import dictconfig
   from pprint import pprint

Demo
====

The following toy example demonstrates the core features of `dictconfig`. Consider
the YAML configuration file below:

.. code:: yaml

   release-date: 2025-01-10
   due: 7 days after ${this.release-date}
   x: 10
   y: 3
   z: 2 * ${this.x} + ${this.y}

Notice that some of the fields in this configuration file contain references to
other fields and are calculated based on these references. For example, we'd
like the eventual value of `due` to be ``2025-01-17`` (i.e., 7 days after the
value of ``release-date``).

Of course, if we read this YAML into a Python dictionary using any standard
YAML loader, the result will be the below dictionary, where the values of each
field are simply the literal values from the YAML file:

.. code:: python

   {
       'release-date': '2025-01-10',
       'due': '7 days after ${this.release-date}',
       'x': 10,
       'y': 3,
       'z': '2 * ${this.x} + ${this.y}'
    }


`dictconfig` takes this dictionary as input and "resolves" references and calculated
values to obtain the following dictionary:

.. code:: python

   {
       'release-date': datetime.date(2025, 1, 10),
       'due': datetime.date(2025, 1, 17),
       'x': 10,
       'y': 3,
       'z': 23
   }


.. toctree::
   :maxdepth: 2
   :caption: Contents:

Quick Start
===========

There are three steps to reading a configuration file with `dictconfig`:

1. Read the configuration file into a Python dictionary (e.g., with PyYAML or the ``json`` module).
2. Define a schema for the configuration.
3. Call :func:`dictconfig.resolve()` to resolve the configuration.

Step 1: Read the configuration file into a Python dictionary
------------------------------------------------------------

If your program configuration is stored in a file (such as a YAML, JSON, or
TOML file), the first step is to read that configuration into a Python
dictionary. `dictconfig` is agnostic to the configration file format, and it
does not provide any file-reading functionality. Instead, you should use
third-party libraries like PyYAML, the `json` module, or the `toml` module to
read configuration files.

One note regarding YAML files: YAML parsers that stick to older versions of the
specification (somewhat infamously) try to guess user intent when parsing
strings. This leads to things like the "Norway problem" where Norway's 2-letter
country code ("NO") is parsed into the boolean `False`. Avoiding these issues
is actually quite simple: configure your YAML parser to read all values as
strings and let `dictconfig` handle the type conversion.

Step 2: Define a Schema
-----------------------

In order to validate a configuration and resolve its values, `dictconfig` needs
to know what keys to expect and the types of their values. This is done by
defining a schema. A schema is a Python dictionary that describes the expected
structure of the configuration.

A full description of the schema format can be found in the `Schemata`_ section
below, however, a few simple examples are probably enough to help you get started.

Step 3: Resolve the configuration
---------------------------------

Call :func:`dictconfig.resolve()` to resolve the configuration. This function
takes the configuration dictionary, the schema, and any external variables that
the configuration may reference. It returns the resolved configuration.

Examples
========

Example 1: Revisting the demo with external variables
-----------------------------------------------------

This example extends the demo to show how external variables (variables that
aren't defined in the configuration file, but which are provided and the time
of resolution) can be used in configuration values. The configuration file is
the same as before, but now we have an external variable `today` that is used
in the calculation of the `tomorrow` field:

.. testcode::

    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "integer"},
            "y": {"type": "integer"},
            "z": {"type": "integer"},
            "release_date": {"type": "date"},
            "due": {"type": "date"},
            "tomorrow": {"type": "date"},
        }
    }

    raw_configuration = {
        'release_date': '2025-01-10',
        'due': '7 days after ${this.release_date}',
        'tomorrow': '1 day after ${today}',
        'x': 10,
        'y': 3,
        'z': '2 * ${this.x} + ${this.y}'
    }

    resolved_configuration = dictconfig.resolve(
        raw_configuration,
        schema,
        external_variables={"today": datetime.date(2025, 1, 7)}
    )

    pprint(resolved_configuration)

The result is:

.. testoutput::

    {'due': datetime.date(2025, 1, 17),
     'release_date': datetime.date(2025, 1, 10),
     'tomorrow': datetime.date(2025, 1, 8),
     'x': 10,
     'y': 3,
     'z': 23}

A usecase of this feature is to allow configurations files to reference values
from *other* configuration files. This is done by reading the other
configuration files into dictionaries and passing them as external variables to
the `resolve` function.

Example 2: Missing required keys
--------------------------------

Consider the example below, which is the same as the previous example, but where a
required key ("z") is missing. :func:`dictconfig.resolve` will catch this when it
does its validation and will raise a :class:`dictconfig.exceptions.ResolutionError`:

.. testcode::

    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "integer"},
            "y": {"type": "integer"},
            "z": {"type": "integer"},
            "release_date": {"type": "date"},
            "due": {"type": "date"},
        }
    }

    raw_configuration = {
        'release_date': '2025-01-10',
        'due': '7 days after ${this.release_date}',
        'x': 10,
        'y': 3,
    }

    try:
        resolved_configuration = dictconfig.resolve(raw_configuration, schema)
    except dictconfig.exceptions.ResolutionError as e:
        pprint(str(e))

The error message is:

.. testoutput::

    'Cannot resolve keypath: "z": Missing required key.'

Example 3: Schema with optional keys and default values
-------------------------------------------------------

Suppose some keys are not required and should have default values if they are
missing. In the example below, the key "x" is optional and has a default value
of 10:

.. testcode::

    schema = {
        "type": "dict",
        "required_keys": {
            "y": {"type": "integer"},
            "z": {"type": "integer"},
        },
        "optional_keys": {
            "x": {"type": "integer", "default": 10},
        }
    }

    raw_configuration = {
        'y': 3,
        'z': '2 * ${this.x} + ${this.y}'
    }

    resolved_configuration = dictconfig.resolve(raw_configuration, schema)
    pprint(resolved_configuration)

The result is:

.. testoutput::

    {'x': 10, 'y': 3, 'z': 23}



Example 4: Lists
----------------

Despite its name, `dictconfig` can be used to validate and resolve more than
just dictionaries. The schema below describes a list of dictionaries, each dictionary
containing a string key `name` and an integer key `age`:

.. testcode::

    schema = {
        "type": "list",
        "element_schema": {
            "type": "dict",
            "required_keys": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            }
        }
    }

    raw_configuration = [
        {"name": "Alice", "age": 30},
        {"name": "Bob", "age": 25},
        {"name": "Charlie", "age": 35},
    ]

    resolved_configuration = dictconfig.resolve(raw_configuration, schema)
    pprint(resolved_configuration)

The result is:

.. testoutput::

   [{'age': 30, 'name': 'Alice'},
    {'age': 25, 'name': 'Bob'},
    {'age': 35, 'name': 'Charlie'}]


Example 5: Nested dictionaries
------------------------------

In the previous example, the ``element_schema`` key was used to describe the
schema for a list of dictionaries. A similar approach can be taken to write a
schema for nested dictionaries. The below example uses a schema describing a
dictionary with top-level keys "number" and "videos", where the value of
"videos" is a list of dictionaries, each containing a string key `title` and an
integer key `url`:

.. testcode::

    schema = {
        "type": "dict",
        "required_keys": {
            "number": {"type": "integer"},
            "videos": {
                "type": "list",
                "element_schema": {
                    "type": "dict",
                    "required_keys": {
                        "title": {"type": "string"},
                        "url": {"type": "integer"},
                    }
                }
            }
        }
    }

    raw_configuration = {
        "number": 3,
        "videos": [
            {"title": "Video 1", "url": 1},
            {"title": "Video 2", "url": 2},
            {"title": "Video 3", "url": 3},
        ]
    }

    resolved_configuration = dictconfig.resolve(raw_configuration, schema)
    pprint(resolved_configuration)

The result is:

.. testoutput::

    {'number': 3,
     'videos': [{'title': 'Video 1', 'url': 1},
                {'title': 'Video 2', 'url': 2},
                {'title': 'Video 3', 'url': 3}]}

Example 6: Using `jinja2` features during interpolation
-------------------------------------------------------

`dictconfig` uses the `jinja2` templating engine for interpolation. This means
that you can use all the features of `jinja2` in your configuration files. For
example, `jinja2` allows for a kind of ternaly operator which can be used to
dynamically set the value of a key based on a condition.

.. testcode::

    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "integer"},
            "y": {"type": "integer"},
            "z": {"type": "integer"},
        }
    }

    raw_configuration = {
        'x': 10,
        'y': 3,
        'z': '${ this.x if this.x > this.y else this.y }'
    }

    resolved_configuration = dictconfig.resolve(raw_configuration, schema)
    pprint(resolved_configuration)

The result is:

.. testoutput::

    {'x': 10, 'y': 3, 'z': 10}



Schemata
========

It is necessary to define a schema in order to specify the types of
configuration values. This section defines the formal grammar of a schema, but you
may be able to get a start by copying and modifying the examples above.

Before describing the grammar of a schema, it will be useful to reframe a
configuration dictionary as a tree.  For example, take the following dictionary
of options:

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

    <SCHEMA> = (<DICT_SCHEMA> | <LIST_SCHEMA> | <LEAF_SCHEMA> | <ANY_SCHEMA>)

    <DICT_SCHEMA> = {
        "type": "dict",
        ["required_keys": {<KEY_NAME>: <SCHEMA>, ...}],
        ["optional_keys": {<KEY_NAME>: (<SCHEMA> | <SCHEMA_WITH_DEFAULT>), ...}],
        ["extra_keys_schema": <SCHEMA>],
        ["nullable": (True | False)],
    }

    <LIST_SCHEMA> = {
        "type": "list",
        "element_schema": <SCHEMA>,
        ["nullable": (True | False)]
    }

    LEAF_SCHEMA = {
        "type": ("string" | "integer" | "float" | "boolean" | "date" | "datetime"),
        ["nullable": (True | False)]
    }

    <ANY_SCHEMA> = {
        "type": "any"
    }

    <SCHEMA_WITH_DEFAULT> = (
        <DICT_SCHEMA_WITH_DEFAULT>
        | <LIST_SCHEMA_WITH_DEFAULT>
        | <LEAF_SCHEMA_WITH_DEFAULT>
        | <ANY_SCHEMA_WITH_DEFAULT>
    )

A ``<SCHEMA_WITH_DEFAULT>`` is like its corresponding schema, but with an added
"default" key that supplies a default value.

A type of "any" denotes that the configuration option will be left as-is with
no parsing, however, interpolation still takes place.

Optionally, a leaf value can be "nullable", meaning that `None` is a valid
type. By default, the leaf values are not nullable.

``resolve()``
=============

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
=======

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

Custom parsers can be added by defining a function that accepts a string and
returns the resolved value. The function should then be passed to the
:func:`dictconfig.resolve` function in the ``override_parsers`` argument.

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
