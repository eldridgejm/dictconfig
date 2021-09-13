from dictconfig import validate_key_schema, exceptions

from pytest import raises, mark


def test_smoke_1():
    # given
    schema = {"name": {"type": "string"}, "number": {"type": "integer"}}

    # when / then
    validate_key_schema(schema)


def test_smoke_2():
    # given
    schema = {
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

def test_must_be_a_dictionary():
    # given
    schema = "testing"

    # then
    with raises(exceptions.SchemaError) as exc:
        validate_key_schema(schema)

    assert exc.value.path == tuple()


def test_keys_must_be_strings():
    # given
    schema = {1: {"type": "string"}}

    # then
    with raises(exceptions.SchemaError) as exc:
        validate_key_schema(schema)

    assert exc.value.path == tuple()


def test_must_be_at_least_one_key():
    # given
    schema = {}

    # when / then
    with raises(exceptions.SchemaError) as exc:
        validate_key_schema(schema)


def test_defn_must_be_a_dictionary():
    # given
    schema = {"name": "testing"}

    # then
    with raises(exceptions.SchemaError) as exc:
        validate_key_schema(schema)

    assert exc.value.path == tuple(['name'])


# defn type
# --------------------------------------------------------------------------------


def test_defn_type_smoke():
    # given
    schema = {"name": {"type": "string"}}

    validate_key_schema(schema)


def test_defn_type_is_required():
    # given
    schema = {"name": {"type": "string"}, "number": {}}

    # when / then
    with raises(exceptions.SchemaError) as exc:
        validate_key_schema(schema)

    assert exc.value.path == tuple(['number'])


def test_defn_type_must_be_valid():
    # given
    schema = {"name": {"type": "foo"}}

    # when / then
    with raises(exceptions.SchemaError) as exc:
        validate_key_schema(schema)

    assert exc.value.path == tuple(['name'])


# defn schema
# --------------------------------------------------------------------------------


@mark.parametrize("type_", ["dict", "list"])
def test_defn_schema_required_if_list_or_dict(type_):
    # given
    schema = {"name": {"type": type_}}

    # when / then
    with raises(exceptions.SchemaError) as exc:
        validate_key_schema(schema)

    assert exc.value.path == tuple(['name'])


@mark.parametrize("type_", ["boolean", "string", "integer"])
def test_defn_schema_disallowed_if_not_dict_or_list(type_):
    # given
    schema = {"name": {"type": type_, "schema": {}}}

    # when / then
    with raises(exceptions.SchemaError) as exc:
        validate_key_schema(schema)

    assert exc.value.path == tuple(['name'])


def test_defn_schema_dict_smoke():
    # given
    schema = {
        'name': {
            'type': 'dict',
            'schema': {
                'first': {'type': 'string'},
                'last': {'type': 'string'},
            }
        }
    }

    # when / then
    validate_key_schema(schema)


def test_defn_schema_list_smoke():
    # given
    schema = {
        'name': {
            'type': 'list',
            'schema': {'type': 'string'}
            }
        }

    # when / then
    validate_key_schema(schema)


def test_defn_schema_list_with_DICT_SCHEMA_raises():
    """If we provide a DICT_SCHEMA for a list, it should fail."""
    # given
    schema = {
        'name': {
            'type': 'list',
            'schema': {
                'first': {'type': 'string'},
                'last': {'type': 'string'},
            }
        }
    }

    # when / then
    with raises(exceptions.SchemaError) as exc:
        validate_key_schema(schema)

    assert exc.value.path == tuple(['name'])


def test_defn_schema_dict_with_VALUE_SPECIFICATION_raises():
    # given
    schema = {
        'name': {
            'type': 'dict',
            'schema': {'type': 'string'}
            }
        }

    # when / then
    with raises(exceptions.SchemaError) as exc:
        validate_key_schema(schema)

    assert exc.value.path == tuple(['name', 'type'])


def test_defn_schema_nested_error():
    # given
    schema = {
        'name': {
            'type': 'dict',
            'schema': {
                'foo': {
                    'type': 'dict',
                    'schema': {
                        'bar': {'type': 'nothing'},
                    }
                }
            }
        }
    }

    # then
    with raises(exceptions.SchemaError) as exc:
        validate_key_schema(schema)

    assert exc.value.path == tuple(['name', 'foo', 'bar'])
