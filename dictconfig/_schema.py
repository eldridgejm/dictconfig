"""Validates an dictconfig schema.

Grammar
-------

The "grammar" of an dictconfig schema is as follows:

.. code::

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
        type: ("string" | "integer" | "float" | "boolean" | "datetime")
    }


This grammar is a subset of that defined by the Cerberus dict validator.
Therefore, dictconfig schemas can be parsed by Cerberus.

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


def _basic_schema_checks(schema, path):
    if not isinstance(schema, dict):
        raise SchemaError("Must be a dictionary.", path)

    if "type" not in schema:
        raise SchemaError('Does not have a "type" field.', path)


def validate_schema(schema, path=tuple()):
    _basic_schema_checks(schema, path)

    if schema["type"] == "dict":
        validate_dict_schema(schema, path)
    elif schema["type"] == "list":
        validate_list_schema(schema, path)
    else:
        validate_leaf_schema(schema, path)


def validate_dict_schema(dict_schema, path=tuple()):
    """Recursively checks to make sure that a dict schema is valid.

    Parameters
    ----------
    schema : dict
        A schema dictionary for a dict node.

    Raises
    ------
    SchemaError
        If the schema does not validate.

    """
    _basic_schema_checks(dict_schema, path)

    if dict_schema["type"] != "dict":
        raise SchemaError('Type must be "dict".', path)

    if "schema" not in dict_schema:
        raise SchemaError('Does not have a "schema" field.', path)

    if not isinstance(dict_schema["schema"], dict):
        raise SchemaError('"schema" field must be a dictionary.', path)

    for key, child_schema in dict_schema["schema"].items():
        if not isinstance(key, str):
            raise SchemaError(f"Key {path}.{key} must be a string.", path)

        validate_schema(child_schema, path + tuple([key]))


def validate_list_schema(list_schema, path=tuple()):
    """Recursively checks to make sure that a list schema is valid.

    Parameters
    ----------
    schema : dict
        A schema dictionary for a list node.

    Raises
    ------
    SchemaError
        If the schema does not validate.

    """
    _basic_schema_checks(list_schema, path)

    if list_schema["type"] != "list":
        raise SchemaError('Type must be "list".', path)

    if "schema" not in list_schema:
        raise SchemaError('Does not have a "schema" field.', path)

    if not isinstance(list_schema["schema"], dict):
        raise SchemaError('"schema" field must be a dictionary.', path)

    validate_schema(list_schema["schema"], path)


def validate_leaf_schema(leaf_schema, path=tuple()):
    _basic_schema_checks(leaf_schema, path)
