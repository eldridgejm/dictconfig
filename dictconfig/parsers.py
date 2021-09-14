import datetime
import ast
import operator as op

# supported operators


DEFAULT_PARSERS = {
    'integer': int,
    'float': float,
    'string': str,
    'boolean': bool
}

# from: https://stackoverflow.com/questions/2371436/evaluating-a-mathematical-expression-in-a-string
def _eval_expr(expr):
    """
    >>> eval_expr('2^6')
    4
    >>> eval_expr('2**6')
    64
    >>> eval_expr('1 + 2*3**(4^5) / (6 + -7)')
    -5.0
    """
    return _eval(ast.parse(expr, mode='eval').body)

def _eval(node):

    operators = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul,
                 ast.Div: op.truediv, ast.Pow: op.pow, ast.BitXor: op.xor,
                 ast.USub: op.neg, ast.Or: op.or_, ast.And: op.and_,
                 ast.Not: op.not_}

    if isinstance(node, ast.Num): # <number>
        return node.n
    elif isinstance(node, ast.NameConstant):
        return node.value
    elif isinstance(node, ast.BinOp): # <left> <operator> <right>
        return operators[type(node.op)](_eval(node.left), _eval(node.right))
    elif isinstance(node, ast.UnaryOp): # <operator> <operand> e.g., -1
        return operators[type(node.op)](_eval(node.operand))
    elif isinstance(node, ast.BoolOp):
        return operators[type(node.op)](*[_eval(v) for v in node.values])
    else:
        raise TypeError(node)

def arithmetic(type_):

    def parser(s):
        if isinstance(s, type_):
            return s
        number = _eval_expr(s)
        return type_(number)

    return parser


def logic(s):
    if isinstance(s, bool):
        return s
    return bool(_eval_expr(s))
