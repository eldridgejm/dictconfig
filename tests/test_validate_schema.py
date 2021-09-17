from dictconfig import validate_schema, exceptions

from pytest import raises


# all schemata
# ============

def test_raises_if_type_field_is_omitted():
    schema = {
    }

    with raises(exceptions.SchemaError):
        validate_schema(schema)

# dict schemata
# =============

def test_dict_schema_smoke():
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"value_schema": {"type": "integer"}},
        },
        "optional_keys": {
            "bar": {"value_schema": {"type": "integer"}, "default": 42},
        }
    }

    validate_schema(schema)




def test_raises_if_unknown_key_is_provided_for_dict_schema():
    schema = {
        "type": "dict",
        "foo": 42
    }

    with raises(exceptions.SchemaError):
        validate_schema(schema)


def test_raises_if_unknown_key_is_provided_for_required_key_spec():
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {
                "value_schema": {"type": "integer"},
                "testing": 42
            }
        }
    }

    with raises(exceptions.SchemaError):
        validate_schema(schema)


def test_raises_if_unknown_key_is_provided_for_optional_key_spec():
    schema = {
        "type": "dict",
        "optional_keys": {
            "foo": {
                "value_schema": {"type": "integer"},
                "testing": 42
            }
        }
    }

    with raises(exceptions.SchemaError):
        validate_schema(schema)


def test_raises_if_extra_keys_schema_is_not_a_valid_schema():
    schema = {
        "type": "dict",
        "extra_keys_schema": 42
    }

    with raises(exceptions.SchemaError):
        validate_schema(schema)

# list schemata
# =============

def test_list_schema_smoke():
    schema = {
        "type": "list",
        "element_schema": {"type": "integer"},
        "nullable": True
    }

    validate_schema(schema)


def test_raises_if_unknown_key_is_provided_for_list_schema():
    schema = {
        "type": "list",
        "woo": "hoo"
    }

    with raises(exceptions.SchemaError):
        validate_schema(schema)


# any types
# =========

def test_any_type_smoke():
    schema = {
        "type": "any",
        "nullable": True
    }

    validate_schema(schema)


def test_raises_if_unknown_key_provided_with_any_type():
    schema = {
        "type": "any",
        "nullable": True,
        "foo": "bar"
    }

    with raises(exceptions.SchemaError):
        validate_schema(schema)
