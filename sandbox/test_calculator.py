import pytest
from calculator import add, subtract, multiply, divide, power, get_history, clear_history


@pytest.fixture(autouse=True)
def clean_history():
    clear_history()
    yield
    clear_history()


def test_add():
    assert add(2, 3) == 5


def test_subtract():
    assert subtract(5, 3) == 2


def test_multiply():
    assert multiply(4, 3) == 12


def test_divide():
    assert divide(10, 2) == 5


def test_divide_by_zero():
    with pytest.raises(ValueError):
        divide(1, 0)


def test_power():
    assert power(2, 3) == 8


def test_power_zero_exponent():
    assert power(5, 0) == 1


def test_power_negative_exponent():
    assert power(2, -1) == 0.5


def test_power_records_history():
    power(2, 3)
    history = get_history()
    assert len(history) == 1
    assert history[0] == {"operation": "power", "operands": (2, 3), "result": 8}


def test_get_history_empty():
    assert get_history() == []


def test_history_records_operation():
    add(2, 3)
    history = get_history()
    assert len(history) == 1
    assert history[0] == {"operation": "add", "operands": (2, 3), "result": 5}


def test_history_records_all_operations():
    add(1, 2)
    subtract(5, 3)
    multiply(4, 2)
    divide(10, 2)

    history = get_history()
    assert len(history) == 4
    assert history[0]["operation"] == "add"
    assert history[1]["operation"] == "subtract"
    assert history[2]["operation"] == "multiply"
    assert history[3]["operation"] == "divide"


def test_history_max_10_entries():
    for i in range(15):
        add(i, 1)

    history = get_history()
    assert len(history) == 10
    assert history[0]["operands"] == (5, 1)


def test_clear_history():
    add(1, 2)
    add(3, 4)
    assert len(get_history()) == 2

    clear_history()
    assert get_history() == []


def test_history_is_copy():
    """Ensure get_history returns a copy, not the internal list."""
    add(1, 2)
    history = get_history()
    history.clear()
    assert len(get_history()) == 1


def test_divide_by_zero_not_recorded():
    """Failed operations should not be recorded."""
    with pytest.raises(ValueError):
        divide(1, 0)
    assert get_history() == []
