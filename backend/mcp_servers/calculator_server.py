"""MCP server exposing a single safe `calculate` tool.

Runs as a stdio MCP server (spawned as a subprocess by the backend's
MCPToolManager). Uses a restricted AST-based evaluator instead of `eval`
to avoid arbitrary code execution.
"""
import ast
import math
import operator

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("calculator")

_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_ALLOWED_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
_ALLOWED_FUNCS = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "exp": math.exp,
    "factorial": math.factorial,
    "abs": abs,
    "round": round,
    "pow": pow,
    "floor": math.floor,
    "ceil": math.ceil,
    "gcd": math.gcd,
}
_ALLOWED_NAMES = {
    "pi": math.pi,
    "e": math.e,
}


def _eval(node: ast.AST):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Unsupported constant: {node.value!r}")
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _ALLOWED_BINOPS:
            raise ValueError(f"Operator not allowed: {op_type.__name__}")
        return _ALLOWED_BINOPS[op_type](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _ALLOWED_UNARYOPS:
            raise ValueError(f"Operator not allowed: {op_type.__name__}")
        return _ALLOWED_UNARYOPS[op_type](_eval(node.operand))
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_FUNCS:
            raise ValueError("Function not allowed")
        if node.keywords:
            raise ValueError("Keyword arguments not allowed")
        args = [_eval(arg) for arg in node.args]
        return _ALLOWED_FUNCS[node.func.id](*args)
    if isinstance(node, ast.Name):
        if node.id in _ALLOWED_NAMES:
            return _ALLOWED_NAMES[node.id]
        raise ValueError(f"Name not allowed: {node.id}")
    raise ValueError(f"Expression not allowed: {type(node).__name__}")


def safe_eval(expression: str):
    tree = ast.parse(expression, mode="eval")
    return _eval(tree.body)


@mcp.tool()
def calculate(expression: str) -> str:
    """Evaluate a math expression (arithmetic, powers, roots, trig, logs,
    factorials, etc.) and return the numeric result as a string. Supports
    +, -, *, /, //, %, **, parentheses, and functions like sqrt, sin, cos,
    tan, log, log10, log2, exp, factorial, abs, round, floor, ceil, gcd,
    and constants pi, e.

    Args:
        expression: The math expression to evaluate, e.g. "2 * (3 + 4) ** 2".
    """
    try:
        result = safe_eval(expression)
    except ZeroDivisionError:
        return "Error: division by zero."
    except Exception as exc:  # noqa: BLE001 - surface a clean message to the LLM
        return f"Error: could not evaluate expression ({exc})."
    return str(result)


if __name__ == "__main__":
    mcp.run(transport="stdio")
