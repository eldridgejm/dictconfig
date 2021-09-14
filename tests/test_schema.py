from dictconfig import exceptions, validate_schema

from pytest import raises, mark


def test_validate_schema_infers_dict_schema_smoke():
    # given
    schema = {
        "type": "dict",
        "schema": {"foo": {"type": "string"}, "bar": {"type": "integer"},},
    }

    # then (no exceptions raised)
    validate_schema(schema)


def test_validate_schema_infers_list_schema_smoke():
    # given
    schema = {"type": "list", "schema": {"type": "string"}}

    # then (no exceptions raised)
    validate_schema(schema)


def test_validate_schema_infers_leaf_schema_smoke():
    # given
    schema = {
        "type": "boolean",
    }

    # then (no exceptions raised)
    validate_schema(schema)


def test_must_be_a_dictionary():
    # given
    schema = "testing"

    # then
    with raises(exceptions.SchemaError) as exc:
        validate_schema(schema)

    assert exc.value.path == tuple()


def test_keys_must_be_strings():
    # given
    schema = {1: {"type": "string"}}

    # then
    with raises(exceptions.SchemaError) as exc:
        validate_schema(schema)

    assert exc.value.path == tuple()


def test_must_have_type():
    # given
    schema = {"name": "testing"}

    # then
    with raises(exceptions.SchemaError) as exc:
        validate_schema(schema)


def test_dict_schema_must_have_child_schema():
    # given
    schema = {"type": "dict", "name": "testing"}

    # then
    with raises(exceptions.SchemaError) as exc:
        validate_schema(schema)


def test_list_schema_must_have_child_schema():
    # given
    schema = {"type": "list", "name": "testing"}

    # then
    with raises(exceptions.SchemaError) as exc:
        validate_schema(schema)


def test_defn_schema_nested_error_has_correct_path():
    # given
    schema = {
        "type": "dict",
        "schema": {"foo": {"type": "dict", "schema": {"bar": {"type": "nothing"},}}},
    }

    # then
    with raises(exceptions.SchemaError) as exc:
        validate_schema(schema)

    assert exc.value.path == tuple(["foo", "bar"])
