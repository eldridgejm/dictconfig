.. dictconfig documentation master file, created by
   sphinx-quickstart on Mon Sep 13 23:56:58 2021.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

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
        "x": {"type": "integer"},
        "y": {"type": "integer"},
        "z": {"type": "integer"}
    }

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
therefore produces the value of

Theory
------

Before describing how to use `dictconfig`, it is useful to define some key terms
and to lay down some theory.

Configuration Trees
~~~~~~~~~~~~~~~~~~~

A nested dictionary of configuration options can be thought of as a tree. For example,
take the following dictionary of options:

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
node. The third child is the list corresponding to the authors; it is also not
a leaf node.

Internal nodes of the configuration tree are either dictionaries or lists. Leaf
nodes are non-container types, like strings, numbers, etc.

In short, :code:`dictconfig.resolve()` takes in an unresolved configuration tree
and resolves each of the leaf nodes.

Schemata
~~~~~~~~

A *schema* defines the type of each of the nodes of the configuration tree.



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
