import ast
import operator as op

# the AST code in this module is based on:
# https://stackoverflow.com/questions/2371436/evaluating-a-mathematical-expression-in-a-string

# arithmetic expressions
# ----------------------


def arithmetic(type_):
    """Create an arithmetic expression parser.

    Parses things like (7 + 3) / 5

    Parameters
    ----------
    type_
        The end type that the resulting value should be converted to.

    Example
    -------

    >>> parser = arithmetic(int)
    >>> parser('(7 + 3) / 5')
    2

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


# logical expressions
# -------------------


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
