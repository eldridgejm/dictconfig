from dictconfig import resolve, exceptions

from pytest import raises


def test_if_path_not_in_schema_type_inferred_to_be_string():
    schema = {
        "type": "dict",
        "schema": {"foo": {"type": "string"}, "bar": {"type": "string"},},
    }

    dct = {"foo": "hi", "bar": "this is ${self.foo}", "baz": "testing"}

    result = resolve(dct, schema)

    # then
    assert result["bar"] == "this is hi"
    assert result["baz"] == "testing"


def test_with_dicts():
    # given
    schema = {
        "type": "dict",
        "schema": {
            "foo": {"type": "string"},
            "bar": {"type": "string"},
            "quux": {
                "type": "dict",
                "schema": {"a": {"type": "string"}, "b": {"type": "string"},},
            },
        },
    }

    dct = {
        "foo": "hello",
        "bar": "${self.quux.b}",
        "quux": {"a": "${self.foo}", "b": "hi",},
    }

    # when
    result = resolve(dct, schema)

    # then
    assert result["bar"] == "hi"
    assert result["quux"]["a"] == "hello"


def test_top_level_list():
    # given
    schema = {"type": "list", "schema": {"type": "string"}}

    data = ["foo", "bar", "baz"]

    # when
    result = resolve(data, schema)

    # then
    assert result[0] == "foo"
    assert result[1] == "bar"
    assert result[2] == "baz"


def test_top_level_leaf():
    # given
    schema = {"type": "integer"}

    data = "42"

    # when
    result = resolve(data, schema)

    # then
    assert result == "42"


def test_with_list():
    # given
    schema = {
        "type": "dict",
        "schema": {
            "foo": {"type": "string"},
            "bar": {"type": "string"},
            "baz": {"type": "list", "schema": {"type": "string"}},
        },
    }

    dct = {
        "foo": "hello",
        "bar": "${self.baz.2}",
        "baz": ["${self.foo}", "${self.bar}", "something",],
    }

    # when
    result = resolve(dct, schema)

    # then
    assert result["bar"] == "something"


def test_with_multiple_redirections():
    # given
    schema = {
        "type": "dict",
        "schema": {
            "foo": {"type": "string"},
            "bar": {"type": "string"},
            "baz": {"type": "list", "schema": {"type": "string"}},
        },
    }

    dct = {
        "foo": "hello",
        "bar": "${self.foo}",
        "baz": ["${self.bar}", "${self.baz.0}", "${self.baz.1}",],
    }

    # when
    result = resolve(dct, schema)

    # then
    assert result["baz"][2] == "hello"


def test_with_external_context():
    # given
    schema = {
        "type": "dict",
        "schema": {"foo": {"type": "string"}, "bar": {"type": "string"},},
    }

    dct = {
        "foo": "hello",
        "bar": "${vars.foo}",
    }

    # when
    result = resolve(dct, schema, context={"vars": {"foo": "testing"}})

    # then
    assert result["bar"] == "testing"


def test_self_reference_raises():
    # given
    schema = {
        "type": "dict",
        "schema": {"foo": {"type": "string"}, "bar": {"type": "string"},},
    }

    dct = {
        "foo": "hello",
        "bar": "${self.bar}",
    }

    # when
    with raises(exceptions.ResolutionError):
        resolve(dct, schema)


def test_circular_reference_raises():
    # given
    schema = {
        "type": "dict",
        "schema": {"foo": {"type": "string"}, "bar": {"type": "string"},},
    }

    dct = {
        "foo": "${self.bar}",
        "bar": "${self.foo}",
    }

    # when
    with raises(exceptions.ResolutionError):
        resolve(dct, schema)


def test_undefined_placeholder_raises():
    # given
    schema = {
        "type": "dict",
        "schema": {"foo": {"type": "string"}, "bar": {"type": "string"},},
    }

    dct = {
        "foo": "${self.bar}",
        "bar": "${self.baz}",
    }

    # when
    with raises(exceptions.ResolutionError):
        resolve(dct, schema)
