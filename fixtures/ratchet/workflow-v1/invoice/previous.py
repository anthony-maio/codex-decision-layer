def invoice_total(lines, discount_bps=0, shipping_cents=0):
    subtotal = sum(line["quantity"] * line["unit_price"] for line in lines)
    return round(subtotal * (1 - discount_bps / 10000) * 100) + shipping_cents
