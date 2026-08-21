"""ماشین‌حساب امن - بدون اجرای کد دلخواه."""
import ast
import math
import operator

_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.USub: operator.neg, ast.UAdd: operator.pos, ast.FloorDiv: operator.floordiv,
}

# توابع و ثابت‌های ریاضیِ مجاز توی ماشین‌حساب - فقط همین‌ها قابل‌فراخوانی‌ان
CALC_FUNCS = {
    "sqrt": math.sqrt, "abs": abs, "round": round,
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "log": math.log, "log10": math.log10, "log2": math.log2, "exp": math.exp,
    "floor": math.floor, "ceil": math.ceil, "factorial": math.factorial,
    "min": min, "max": max, "hypot": math.hypot, "degrees": math.degrees, "radians": math.radians,
}
CALC_CONSTS = {"pi": math.pi, "e": math.e, "tau": math.tau, "inf": math.inf}


def safe_eval(expr):
    """ماشین‌حساب امن - عملیات ریاضی + توابع/ثابت‌های رایج، بدون اجرای کد دلخواه"""
    def _eval(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](_eval(node.operand))
        if isinstance(node, ast.Name) and node.id in CALC_CONSTS:
            return CALC_CONSTS[node.id]
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in CALC_FUNCS and not node.keywords):
            args = [_eval(a) for a in node.args]
            return CALC_FUNCS[node.func.id](*args)
        raise ValueError("عبارت نامعتبر")
    tree = ast.parse(expr, mode="eval")
    result = _eval(tree.body)
    if isinstance(result, float):
        result = round(result, 10)
        if result.is_integer() and abs(result) < 1e15:
            result = int(result)
    return result
