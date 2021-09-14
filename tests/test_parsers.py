from dictconfig import resolve, exceptions, parsers


def test_parse_integer_arithmetic():
    # given
    schema = {
        "type": "dict",
        "schema": {
            "x": {"type": "integer"},
            "y": {"type": "integer"},
            "z": {"type": "integer"},
        },
    }

    dct = {"x": 10, "y": 20, "z": "${self.x} + ${self.y}"}

    # when
    result = resolve(dct, schema)

    # then
    assert result == {"x": 10, "y": 20, "z": 30}


def test_parse_boolean_logic():
    # given
    schema = {
        "type": "dict",
        "schema": {
            "x": {"type": "boolean"},
            "y": {"type": "boolean"},
            "z": {"type": "boolean"},
        },
    }

    dct = {"x": True, "y": False, "z": "(${self.x} or ${self.y}) and not ${self.x}"}

    # when
    result = resolve(dct, schema)

    # then
    assert result == {"x": True, "y": False, "z": False}
