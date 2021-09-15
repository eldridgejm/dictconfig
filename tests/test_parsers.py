from dictconfig import exceptions, parsers

import datetime

from pytest import raises

# arithmetic


def test_integer_arithmetic():
    # given
    parser = parsers.arithmetic(int)

    # when
    result = parser("(42 - 10) * 3 + 2")

    # then
    assert result == 98


def test_float_arithmetic():
    # given
    parser = parsers.arithmetic(float)

    # when
    result = parser("9 / 2")

    # then
    assert result == 4.5


# logic


def test_logic():
    assert parsers.logic("True and (False or True)") is True


# smartdate
# ---------


def test_smartdate_from_explicit_date():
    assert parsers.smartdate("2021-10-05") == datetime.date(2021, 10, 5)


def test_smartdate_from_explicit_datetime():
    assert parsers.smartdate("2021-10-05 23:59:10") == datetime.date(2021, 10, 5)


def test_smartdate_delta_days_before():
    assert parsers.smartdate("3 days before 2021-10-05") == datetime.date(2021, 10, 2)


def test_smartdate_delta_days_after():
    assert parsers.smartdate("3 days after 2021-10-05") == datetime.date(2021, 10, 8)


def test_smartdate_delta_days_simplifies_datetimes_to_dates():
    assert parsers.smartdate("3 days before 2021-10-05 23:59:00") == datetime.date(
        2021, 10, 2
    )


def test_smartdate_first_date_before():
    assert parsers.smartdate("first monday before 2021-09-17") == datetime.date(
        2021, 9, 13
    )


def test_smartdate_first_date_after():
    assert parsers.smartdate("first monday after 2021-09-10") == datetime.date(
        2021, 9, 13
    )


def test_smartdate_first_date_after_multiple_choices():
    assert parsers.smartdate("first monday, friday after 2021-09-14") == datetime.date(
        2021, 9, 17
    )


def test_smartdate_first_date_before_simplifies_datetimes_to_dates():
    assert parsers.smartdate(
        "first monday before 2021-09-14 23:59:00"
    ) == datetime.date(2021, 9, 13)


# smartdatetime
# -------------


def test_smartdatetime_from_explicit_date():
    assert parsers.smartdatetime("2021-10-05") == datetime.datetime(2021, 10, 5)


def test_smartdatetime_from_explicit_datetime():
    assert parsers.smartdatetime("2021-10-05 23:59:10") == datetime.datetime(
        2021, 10, 5, 23, 59, 10
    )


def test_smartdatetime_delta_days_before():
    assert parsers.smartdatetime(
        "3 days before 2021-10-05 23:59:15"
    ) == datetime.datetime(2021, 10, 2, 23, 59, 15)


def test_smartdatetime_delta_days_after():
    assert parsers.smartdatetime(
        "3 days after 2021-10-05 23:59:15"
    ) == datetime.datetime(2021, 10, 8, 23, 59, 15)


def test_smartdatetime_delta_hours_before():
    assert parsers.smartdatetime(
        "3 hours before 2021-10-05 23:59:15"
    ) == datetime.datetime(2021, 10, 5, 20, 59, 15)


def test_smartdatetime_delta_hours_after():
    assert parsers.smartdatetime(
        "3 hours after 2021-10-05 23:59:15"
    ) == datetime.datetime(2021, 10, 6, 2, 59, 15)


def test_smartdatetime_first_date_before():
    assert parsers.smartdatetime("first monday before 2021-09-17") == datetime.datetime(
        2021, 9, 13
    )


def test_smartdatetime_first_date_after():
    assert parsers.smartdatetime("first monday after 2021-09-10") == datetime.datetime(
        2021, 9, 13
    )


def test_smartdatetime_first_date_after_multiple_choices():
    assert parsers.smartdatetime(
        "first monday, friday after 2021-09-14"
    ) == datetime.datetime(2021, 9, 17)
