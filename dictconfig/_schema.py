"""Validates an dictconfig schema.

Grammar
-------

The "grammar" of an dictconfig schema is as follows:

.. code::

    <KEY_SCHEMA> = {
        key_1: <VALUE_SCHEMA>,
        [key_2: <VALUE_SCHEMA>,]
        ...
        [key_d: <VALUE_SCHEMA>,]
    }

    <VALUE_SCHEMA> = {
        type: ("string" | "integer" | "float" | "boolean" | "datetime" | "dict" | "list"),
        [schema: (<DICT_SCHEMA>|<VALUE_SCHEMA>)
    }

    -----

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



If the type of a value is "list" or "dict", then the schema must be provided.
Furthermore, if the type is "list", the schema must be a VALUE_SCHEMA,
and if it is "dict" the schema must be a DICT_SCHEMA.

This grammar is a subset of that defined by the Cerberus dict validator. Therefore,
dictconfig schemas can be parsed by Cerberus.

Example
-------

This is an example dictconfig schema that will be validated.

.. code::

    {
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

"""
from .exceptions import SchemaError


LEAF_TYPES = {"string", "integer", "float", "boolean", "datetime"}
INTERNAL_TYPES = {"dict", "list"}


# key schema
# --------------------------------------------------------------------------------

def validate_key_schema(schema, path=tuple()):
    """Recusrively checks to make sure that a KEY_SCHEMA is valid.

    Parameters
    ----------
    schema : dict
        A schema dictionary for an dictconfig.

    Raises
    ------
    SchemaError
        If the schema does not validate.

    """
    if not isinstance(schema, dict):
        raise SchemaError("Must be a dictionary.", path)

    if not schema:
        raise SchemaError("Schema must be non-empty.", path)

    for key, value_schema in schema.items():
        if not isinstance(key, str):
            raise SchemaError(f"Key {path}.{key} must be a string.", path)

        validate_value_schema(value_schema, path + tuple([key]))


# value schemas
# --------------------------------------------------------------------------------


def validate_value_schema(value_schema, path=tuple()):
    """Recursively validates a VALUE_SCHEMA.

    Recall that a value schema must have a `type` key. If the value schema describes
    a list or dict, then it must also have a `schema` key.

    """
    if not isinstance(value_schema, dict):
        raise SchemaError(
                f"Value schema for '{'.'.join(path)}' is not a dictionary. "
                " Did you mean for this to be a SCHEMA instead?"
                , path)

    _validate_value_schema_type_field(value_schema, path)
    _validate_value_schema_schema_field(value_schema, path)

    if value_schema['type'] == 'list':
        return validate_value_schema(value_schema['schema'], path=path)

    if value_schema['type'] == 'dict':
        return validate_key_schema(value_schema['schema'], path=path)


def _validate_value_schema_type_field(value_schema, path):
    if "type" not in value_schema:
        raise SchemaError('Value schema must have a "type" value.', path)

    valid_types = INTERNAL_TYPES | LEAF_TYPES

    if value_schema["type"] not in valid_types:
        raise SchemaError(
            f'Type "{value_schema["type"]}" is not one of the valid types: {valid_types}.', path
        )


def _validate_value_schema_schema_field(value_schema, path):
    if value_schema["type"] in {"list", "dict"}:
        if "schema" not in value_schema:
            raise SchemaError(
                f'{path} is a {value_schema["type"]}, but no schema was provided.', path
            )
    else:
        if "schema" in value_schema:
            raise SchemaError(
                f'{path} is a {value_schema["type"]}, but a schema was provided. '
                "Must be a dict or list to provide a schema.",
                path,
            )

# ----------

def _basic_schema_checks(schema, path):
    if not isinstance(schema, dict):
        raise SchemaError("Must be a dictionary.", path)

    if 'type' not in schema:
        raise SchemaError('Does not have a "type" field.', path)


def validate_schema(schema, path=tuple()):
    _basic_schema_checks(schema, path)

    if schema['type'] == 'dict':
        validate_dict_schema(schema, path)
    elif schema['type'] == 'list':
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

    if dict_schema['type'] != 'dict':
        raise SchemaError('Type must be "dict".', path)

    if 'schema' not in dict_schema:
        raise SchemaError('Does not have a "schema" field.', path)

    if not isinstance(dict_schema['schema'], dict):
        raise SchemaError('"schema" field must be a dictionary.', path)

    for key, child_schema in dict_schema['schema'].items():
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

    if list_schema['type'] != 'list':
        raise SchemaError('Type must be "list".', path)

    if 'schema' not in list_schema:
        raise SchemaError('Does not have a "schema" field.', path)

    if not isinstance(list_schema['schema'], dict):
        raise SchemaError('"schema" field must be a dictionary.', path)

    validate_schema(list_schema['schema'], path)


def validate_leaf_schema(leaf_schema, path=tuple()):
    _basic_schema_checks(leaf_schema, path)

    valid_types = {
            "string" , "integer" , "float" , "boolean" , "datetime"
            }

    if leaf_schema['type'] not in valid_types:
        raise SchemaError(f'Leaf type {leaf_schema["type"]} is not a valid type.')
