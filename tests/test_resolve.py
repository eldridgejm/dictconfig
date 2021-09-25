import datetime

from dictconfig import resolve, exceptions, parsers

from pytest import raises

# 1. are defaults used?
# 2. are missing values reported?
# 3. does interpolation occur?
# 4. are types checked?
# 5. is nullible enforced?
# 6. is parsing done as expected?

# dictionaries
# ============


def test_raises_if_required_keys_are_missing():
    # given
    schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "any"}, "bar": {"type": "any"},},
    }

    dct = {"foo": 42}

    # when
    with raises(exceptions.ResolutionError) as excinfo:
        resolve(dct, schema)

    assert excinfo.value.keypath == ("bar",)


def test_raises_if_extra_keys_without_extra_keys_schema():
    # given
    schema = {"type": "dict", "required_keys": {}}

    dct = {"foo": 42}

    # when
    with raises(exceptions.ResolutionError):
        resolve(dct, schema)


def test_allows_extra_keys_with_extra_keys_schema():
    # given
    schema = {"type": "dict", "extra_keys_schema": {"type": "any"}}

    dct = {"foo": 42}

    # when
    result = resolve(dct, schema)

    # then
    assert result["foo"] == 42


def test_fills_in_missing_value_with_default_if_provided():
    # given
    schema = {
        "type": "dict",
        "optional_keys": {"foo": {"default": 42, "type": "integer"}},
    }

    dct = {}

    # when
    result = resolve(dct, schema)

    # then
    assert result["foo"] == 42


def test_allows_missing_keys_if_required_is_false():
    # given
    schema = {
        "type": "dict",
        "optional_keys": {"foo": {"type": "integer"}, "bar": {"type": "integer",},},
    }

    dct = {"bar": 42}

    # when
    result = resolve(dct, schema)

    # then
    assert result["bar"] == 42
    assert "foo" not in result


# non-dictionary roots
# ====================


def test_lists_are_permitted_as_root_node():
    # given
    schema = {"type": "list", "element_schema": {"type": "integer"}}

    lst = [1, 2, 3]

    # when
    result = resolve(lst, schema)

    # then
    assert result == [1, 2, 3]


def test_leafs_are_permitted_as_root_node():
    # given
    schema = {
        "type": "integer",
    }

    x = 42

    # when
    result = resolve(x, schema)

    # then
    assert result == 42


# interpolation
# =============


def test_interpolation_of_other_dictionary_entries_same_level():
    # given
    schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "string"}, "bar": {"type": "string"},},
    }

    dct = {"foo": "this", "bar": "testing ${this.foo}"}

    # when
    result = resolve(dct, schema)

    # then
    assert result["bar"] == "testing this"


def test_interpolation_of_other_dictionary_entries_different_level():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {"type": "dict", "required_keys": {"baz": {"type": "string"}},},
        },
    }

    dct = {"foo": "testing ${this.bar.baz}", "bar": {"baz": "this"}}

    # when
    result = resolve(dct, schema)

    # then
    assert result["foo"] == "testing this"


def test_interpolation_can_reference_list_elements():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {"type": "list", "element_schema": {"type": "string"},},
        },
    }

    dct = {"foo": "testing ${this.bar.1}", "bar": ["this", "that", "the other"]}

    # when
    result = resolve(dct, schema)

    # then
    assert result["foo"] == "testing that"


def test_interpolation_can_use_external_variables():
    # given
    schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "string"},},
    }

    dct = {"foo": "testing ${a.b.c}"}
    external_variables = {"a": {"b": {"c": "this"}}}

    # when
    result = resolve(dct, schema, external_variables)

    # then
    assert result["foo"] == "testing this"


def test_chain_of_multiple_interpolations():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {"type": "string"},
            "baz": {"type": "string"},
        },
    }

    dct = {
        "foo": "this",
        "bar": "testing ${this.foo}",
        "baz": "now ${this.bar}",
    }

    # when
    result = resolve(dct, schema)

    # then
    assert result["foo"] == "this"
    assert result["bar"] == "testing this"
    assert result["baz"] == "now testing this"


def test_raises_if_this_reference_detected():
    # given
    schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "string"},},
    }

    dct = {
        "foo": "${this.foo}",
    }

    # when
    with raises(exceptions.ResolutionError):
        resolve(dct, schema)


def test_raises_if_cyclical_reference_detected():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {"type": "string"},
            "baz": {"type": "string"},
        },
    }

    dct = {
        "foo": "${this.baz}",
        "bar": "${this.foo}",
        "baz": "${this.bar}",
    }

    # when
    with raises(exceptions.ResolutionError):
        resolve(dct, schema)


def test_can_use_jinja_methods():
    # given
    schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "string"}, "bar": {"type": "string"},},
    }

    dct = {
        "foo": "this",
        "bar": "testing ${this.foo.upper()}",
    }

    # when
    result = resolve(dct, schema)

    # then
    assert result["foo"] == "this"
    assert result["bar"] == "testing THIS"


def test_interpolation_of_keys_with_dots():
    # given
    schema = {
        "type": "dict",
        "required_keys": {"foo.txt": {"type": "string"}, "bar": {"type": "string"},},
    }

    dct = {
        "foo.txt": "this",
        "bar": "testing ${this['foo.txt']}",
    }

    # when
    result = resolve(dct, schema)

    # then
    assert result["foo.txt"] == "this"
    assert result["bar"] == "testing this"


def test_interpolation_is_not_confused_by_default_jinja_syntax():
    # given
    schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "string"}, "bar": {"type": "string"},},
    }

    dct = {
        "foo": "this",
        "bar": "testing ${this.foo} {{ that }}",
    }

    # when
    result = resolve(dct, schema)

    # then
    assert result["foo"] == "this"
    assert result["bar"] == "testing this {{ that }}"


# parsing
# =======


def test_leafs_are_parsed_into_expected_types():
    # given
    schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "integer"}},
    }

    dct = {"foo": "42"}

    # when
    result = resolve(dct, schema)

    # then
    assert result["foo"] == 42


def test_parsing_occurs_after_interpolation():
    # given
    schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "integer"}, "bar": {"type": "integer"},},
    }

    dct = {"foo": "42", "bar": "${this.foo}"}

    # when
    result = resolve(dct, schema)

    # then
    assert result["foo"] == 42
    assert result["bar"] == 42


def test_parsing_of_extra_dictionary_keys():
    # given
    schema = {"type": "dict", "extra_keys_schema": {"type": "integer"}}

    dct = {"foo": "42", "bar": "10"}

    # when
    result = resolve(dct, schema)

    # then
    assert result["foo"] == 42
    assert result["bar"] == 10


def test_parsing_of_list_elements():
    # given
    schema = {"type": "list", "element_schema": {"type": "integer"}}

    dct = ["10", "25"]

    # when
    result = resolve(dct, schema)

    # then
    assert result == [10, 25]


# "any" type
# ==========


def test_all_types_preserved_when_any_is_used():
    # given
    schema = {
        "type": "any",
    }

    dct = {"foo": "testing", "bar": {"x": 1, "y": 2}, "baz": [1, 2, 3]}

    # when
    result = resolve(dct, schema)

    # then
    assert result == dct


def test_interpolation_occurs_when_any_is_used():
    # given
    schema = {
        "type": "any",
    }

    dct = {"foo": "testing", "bar": "${this.foo} this"}

    # when
    result = resolve(dct, schema)

    # then
    assert result["bar"] == "testing this"


# nullable
# ========


def test_dictionary_can_be_nullable():
    # given
    schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "dict", "nullable": True}},
    }

    dct = {"foo": None}

    # when
    result = resolve(dct, schema)

    # then
    assert result["foo"] is None


def test_list_can_be_nullable():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {
                "type": "list",
                "element_schema": {"type": "any"},
                "nullable": True,
            }
        },
    }

    dct = {"foo": None}

    # when
    result = resolve(dct, schema)

    # then
    assert result["foo"] is None


def test_leaf_can_be_nullable():
    # given
    schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "integer", "nullable": True}},
    }

    dct = {"foo": None}

    # when
    result = resolve(dct, schema)

    # then
    assert result["foo"] is None


# good exceptions
# ===============


def test_exception_has_correct_path_with_missing_key_in_nested_dict():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "dict", "required_keys": {"bar": {"type": "any"}},},
        },
    }

    dct = {"foo": {}}

    # when
    with raises(exceptions.ResolutionError) as excinfo:
        resolve(dct, schema)

    assert excinfo.value.keypath == ("foo", "bar",)


def test_exception_has_correct_path_with_missing_key_in_nested_dict_within_list():
    # given
    schema = {
        "type": "list",
        "element_schema": {
            "type": "dict",
            "required_keys": {"foo": {"type": "integer",},},
        },
    }

    lst = [{"foo": 10,}, {"bar": 42}]

    # when
    with raises(exceptions.ResolutionError) as excinfo:
        resolve(lst, schema)

    assert excinfo.value.keypath == (1, "foo")


def test_exception_when_cannot_resolve_external_variable():
    # given
    schema = {"type": "dict", "required_keys": {"foo": {"type": "string"}}}

    dct = {"foo": "${ext.bar}"}

    # when
    with raises(exceptions.ResolutionError) as excinfo:
        resolve(dct, schema)

    assert excinfo.value.keypath == ("foo",)
