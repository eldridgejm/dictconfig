"""Validates a dictconfig schema.

Grammar
-------

The "grammar" of an dictconfig schema is as follows:

.. code::

    <SCHEMA> = (<DICT_SCHEMA> | <LIST_SCHEMA> | <LEAF_SCHEMA> | <ANY_SCHEMA>)

    <DICT_SCHEMA> = {
        "type": "dict",
        "keys": {
            <KEYNAME>: {
                "required": (True | False | {"default": <value>}),
                "value": <SCHEMA>
            },
            [...]
        },
        "extravalues": (False | <SCHEMA>),
        "nullable": (True | False)
    }

    <ANY_SCHEMA> = {
        "type": "any"
    }

    <LIST_SCHEMA> = {
        "type": "list",
        "entries": <SCHEMA>,
        "nullable": (True | False)
    }

    LEAF_SCHEMA = {
        "type": ("string" | "integer" | "float" | "boolean" | "date" | "datetime"),
        "nullable": (True | False)
    }


Example
-------

This is an example dictconfig schema that will be validated.

.. code::

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

"""
from .exceptions import SchemaError


LEAF_TYPES = {"string", "integer", "float", "boolean", "date", "datetime"}
INTERNAL_TYPES = {"dict", "list"}


def validate_schema(schema):
    pass
