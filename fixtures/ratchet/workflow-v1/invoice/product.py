def line_amount(line):
    return line["quantity"] * line["unit_price"]


def invoice_total(lines, discount_bps=0, shipping_cents=0):
    subtotal = sum(line_amount(line) for line in lines)
    return round(subtotal * (1 - discount_bps / 10000) * 100) + shipping_cents
