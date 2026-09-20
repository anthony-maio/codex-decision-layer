from product import invoice_total


def test_invoice():
    lines = [{"quantity": "2", "unit_price": "10.00"},
             {"quantity": "1", "unit_price": "3.50"}]
    assert invoice_total(lines) == 2350
