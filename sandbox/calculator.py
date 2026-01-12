_history = []
MAX_HISTORY = 10


def _record(operation, a, b, result):
    """Record operation to history, maintaining max 10 entries."""
    _history.append({
        "operation": operation,
        "operands": (a, b),
        "result": result
    })
    if len(_history) > MAX_HISTORY:
        _history.pop(0)
    return result


def add(a, b):
    return _record("add", a, b, a + b)


def subtract(a, b):
    return _record("subtract", a, b, a - b)


def multiply(a, b):
    return _record("multiply", a, b, a * b)


def divide(a, b):
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return _record("divide", a, b, a / b)


def power(base, exponent):
    return _record("power", base, exponent, base ** exponent)


def get_history():
    """Return copy of history (most recent last)."""
    return list(_history)


def clear_history():
    """Clear all history."""
    _history.clear()
