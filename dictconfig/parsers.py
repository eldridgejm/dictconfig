"""
A parser is a function that accepts a raw value -- often, but not necessarily a
string -- and returns a resolved value with the appropriate type.
"""
import ast
import enum
import operator as op
import datetime as datetimelib
import re

from . import exceptions

# the AST code in this module is based on:
# https://stackoverflow.com/questions/2371436/evaluating-a-mathematical-expression-in-a-string

# arithmetic
# ----------


def arithmetic(type_):
    """A factory that creates an arithmetic expression parser.

    The resulting function parses things like "(7 + 3) / 5" into the specified
    numeric type.

    Parameters
    ----------
    type_
        The end type that the resulting value should be converted to.

    Example
    -------

    >>> parser = arithmetic(int)
    >>> parser('(7 + 3) / 5')
    2
    >>> parser(42)
    42

    """

    def _eval(node):
        operators = {
            ast.Add: op.add,
            ast.Sub: op.sub,
            ast.Mult: op.mul,
            ast.Div: op.truediv,
            ast.Pow: op.pow,
            ast.BitXor: op.xor,
            ast.USub: op.neg,
        }

        if isinstance(node, ast.Num):  # <number>
            return node.n
        elif isinstance(node, ast.BinOp):  # <left> <operator> <right>
            return operators[type(node.op)](_eval(node.left), _eval(node.right))
        elif isinstance(node, ast.UnaryOp):  # <operator> <operand> e.g., -1
            return operators[type(node.op)](_eval(node.operand))
        else:
            raise TypeError(node)

    def parser(s):
        if isinstance(s, type_):
            return s
        number = _eval(ast.parse(s, mode="eval").body)
        return type_(number)

    return parser


# logical
# -------


def logic(s):
    """Parses boolean logic expressions.

    Example
    -------

    >>> logic('True and (False or True)')
    True

    """

    def _eval(node):

        operators = {ast.Or: op.or_, ast.And: op.and_, ast.Not: op.not_}

        if isinstance(node, ast.NameConstant):
            return node.value
        elif isinstance(node, ast.UnaryOp):  # <operator> <operand> e.g., -1
            return operators[type(node.op)](_eval(node.operand))
        elif isinstance(node, ast.BoolOp):
            return operators[type(node.op)](*[_eval(v) for v in node.values])
        else:
            raise TypeError(node)

    if isinstance(s, bool):
        return s

    return bool(_eval(ast.parse(s, mode="eval").body))


# dates / datetimes
# -----------------


class _DateMatchError(Exception):
    """Raised if a parse fails because the string does not match."""


def smartdate(s):
    """Parses natural language relative dates into date objects.

    Input strings can be in one of three forms:

        1. Dates in ISO format, e.g.: "2021-10-1".
        2. Relative dates of the form :code:`"<n> days (before|after) <ISO date>"`,
           e.g., "3 days before 2021-10-10"
        3. Relative dates of the form :code:`"first
           <day_of_week>[,<day_of_week>,...,<day_of_week>] (before|after) <ISO date>"`, 
           e.g., "first monday, wednesday after 2021-10-10"

    Example
    -------

    >>> smartdate('2021-10-1')
    datetime.date(2021, 10, 1)
    >>> smartdate('3 days after 2021-10-1')
    datetime.date(2021, 10, 4)
    >>> smartdate('3 days before 2021-10-5')
    datetime.date(2021, 10, 2)
    >>> smartdate('first monday after 2021-09-10')
    datetime.date(2021, 9, 13)

    """
    if isinstance(s, datetimelib.date):
        return s

    if isinstance(s, datetimelib.datetime):
        return s.date()

    try:
        return datetimelib.datetime.fromisoformat(s).date()
    except ValueError:
        # the date was not in ISO format
        pass

    try:
        return _parse_timedelta_before_or_after(s).date()
    except _DateMatchError:
        pass

    try:
        return _parse_first_available_day(s).date()
    except _DateMatchError:
        pass

    raise exceptions.ParseError(f"Cannot parse into date: '{s}'.")


def smartdatetime(s):
    """Parses natural language relative dates into datetime objects.

    The forms of the input are the same as for :func:`smartdate`, except ISO times
    are permitted. For instance: :code:`3 days after 2021-10-05 23:59:00`.

    """
    if isinstance(s, datetimelib.date):
        return datetimelib.datetime(s)

    if isinstance(s, datetimelib.datetime):
        return s

    try:
        return datetimelib.datetime.fromisoformat(s)
    except ValueError:
        # the date was not in ISO format
        pass

    try:
        return _parse_timedelta_before_or_after(s)
    except _DateMatchError:
        pass

    try:
        return _parse_first_available_day(s)
    except _DateMatchError:
        pass

    raise exceptions.ParseError(f"Cannot parse datetime: '{s}'.")


def _parse_timedelta_before_or_after(s):
    """Helper that parses a string of the form "<n> days (before|after) <date(time)>".

    This will always return a datetime object.

    """
    match = re.match(
        r"^(\d+) (day|hour)[s]{0,1} (after|before) (.*)$", s, flags=re.IGNORECASE,
    )

    if not match:
        raise _DateMatchError("Did not match.")

    number, hours_or_days, before_or_after, reference_date = match.groups()
    factor = -1 if before_or_after.lower() == "before" else 1

    if hours_or_days.lower() == "hour":
        timedelta_kwargs = {"hours": factor * int(number)}
    else:
        timedelta_kwargs = {"days": factor * int(number)}

    try:
        reference_date = datetimelib.datetime.fromisoformat(reference_date.strip())
    except ValueError:
        raise _DateMatchError(f"Reference date {reference_date} not in ISO format.")

    delta = datetimelib.timedelta(**timedelta_kwargs)

    return reference_date + delta


class _DaysOfTheWeek(enum.IntEnum):
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6


def _get_day_of_the_week(s):
    """Take a day of the week string, like "Monday", and turn it into a _DaysOfTheWeek.

    Parameters
    ----------
    s : str
        Day of the week as a string. Must be the full name, e.g., "Wednesday". Case
        insensitive.

    Returns
    -------
    _DaysOfTheWeek
        The day of the week.

    Raises
    ------
    ValidationError
        If ``s`` was not a valid day name.

    """
    try:
        return getattr(_DaysOfTheWeek, s.upper())
    except AttributeError:
        raise _DateMatchError(f"Invalid day of week: {s}")


def _parse_first_available_day(s):
    """Parse a string of the form "first monday before 2021-10-01".

    Always returns a datetime object.

    """
    s = s.replace(",", " ")
    s = s.replace(" or ", " ")

    match = re.match(r"^first ([\w ]+) (after|before) (.*)$", s, flags=re.IGNORECASE)

    if not match:
        raise _DateMatchError("Did not match.")

    day_of_the_week_raw, before_or_after, relative_to = match.groups()
    day_of_the_week = {_get_day_of_the_week(x) for x in day_of_the_week_raw.split()}

    relative_to = datetimelib.datetime.fromisoformat(relative_to)

    sign = 1 if before_or_after.lower() == "after" else -1
    delta = datetimelib.timedelta(days=sign)

    cursor_date = relative_to + delta

    while cursor_date.weekday() not in day_of_the_week:
        cursor_date += delta

    return cursor_date
