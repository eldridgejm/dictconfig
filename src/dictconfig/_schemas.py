"""Validates schemas."""

import typing

from . import exceptions

Schema = typing.Mapping[str, typing.Any]


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
        validate_schema(key_schema, keypath + ("required_keys", key))

    for key, key_schema in dict_schema.get("optional_keys", {}).items():
        validate_schema(
            key_schema, keypath + ("optional_keys", key), allow_default=True
        )

    if "extra_keys_schema" in dict_schema:
        validate_schema(
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

    validate_schema(
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


def validate_schema(schema, keypath=tuple(), allow_default=False):
    """Validate a schema.

    Raises
    ------
    InvalidSchemaError
        If the schema is not valid.

    """
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
