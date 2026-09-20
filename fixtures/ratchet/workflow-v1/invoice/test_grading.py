from copy import deepcopy
import pytest
from product import invoice_total


@pytest.mark.parametrize("lines,discount,shipping,expected", [
    ([], 0, 123, 123),
    ([], 0, 10**60, 10**60),
    ([{"quantity": "2", "unit_price": "10.00"}, {"quantity": 1, "unit_price": "3.50"}], 1000, 125, 2240),
    ([{"quantity": 1, "unit_price": "0.005"}], 0, 0, 1),
    ([{"quantity": 1, "unit_price": "0.004"}, {"quantity": 1, "unit_price": "0.004"}], 0, 0, 1),
    ([{"quantity": "003", "unit_price": "0.10"}], 0, 0, 30),
    ([{"quantity": 3, "unit_price": "12.34"}], 10000, 42, 42),
    ([{"quantity": 1, "unit_price": "9999999999999999.99"}], 0, 0, 999999999999999999),
    ([{"quantity": 1, "unit_price": "1.005"}], 5000, 0, 50),
])
def test_totals(lines, discount, shipping, expected):
    before = deepcopy(lines)
    result = invoice_total(lines, discount, shipping)
    assert type(result) is int and result == expected
    assert lines == before


@pytest.mark.parametrize("quantity", [True, False, 0, -1, 1.5, "", "1.5", "-1", " 1", "\u0661", None])
def test_invalid_quantity(quantity):
    with pytest.raises(ValueError):
        invoice_total([{"quantity": quantity, "unit_price": "1.00"}])


@pytest.mark.parametrize("price", [None, 1.0, "", "NaN", "Infinity", "-0.01", "abc"])
def test_invalid_price(price):
    with pytest.raises(ValueError):
        invoice_total([{"quantity": 1, "unit_price": price}])


@pytest.mark.parametrize("line", [{}, {"quantity": 1}, {"unit_price": "1"}, None])
def test_invalid_line(line):
    with pytest.raises(ValueError):
        invoice_total([line])


@pytest.mark.parametrize("discount,shipping", [(-1, 0), (10001, 0), (True, 0), (1.5, 0), (0, -1), (0, True), (0, 1.5)])
def test_invalid_options(discount, shipping):
    with pytest.raises(ValueError):
        invoice_total([], discount, shipping)
