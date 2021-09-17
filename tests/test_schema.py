from dictconfig import exceptions, validate_schema

from pytest import raises, mark


def test_validate_schema_infers_dict_schema_smoke():
    # given
    schema = {
        "type": "dict",
        "keys": {
            "foo": {
                "required": False,
                "value": {"type": "string"}
            },
            "bar": {
                "value": {"type": "integer"}
            }
        },
        "extravalues": {
            "type": "string"
        }
    }

    # then (no exceptions raised)
    validate_schema(schema)

def test_validate_schema_infers_list_schema_smoke():
    # given
    schema = {"type": "list", "elements": {"type": "string"}}

    # then (no exceptions raised)
    validate_schema(schema)


def test_validate_schema_infers_leaf_schema_smoke():
    # given
    schema = {
        "type": "boolean",
    }

    # then (no exceptions raised)
    validate_schema(schema)


def test_dict_schema_has_extra_keys_raises():
    # given
    schema = {
        "type": "dict",
        "thisdoesntbelong": 42,
        "keys": {
            "foo": {
                "required": False,
                "value": {"type": "string"}
            },
            "bar": {
                "value": {"type": "integer"}
            }
        },
        "extravalues": {
            "type": "string"
        }
    }

    # then
    with raises(exceptions.SchemaError):
        validate_schema(schema)


def test_dict_schema_keys_field_is_not_dict_raises():
    # given
    schema = {
        "type": "dict",
        "keys": 42,
        "extravalues": {
            "type": "string"
        }
    }

    # then
    with raises(exceptions.SchemaError):
        validate_schema(schema)
