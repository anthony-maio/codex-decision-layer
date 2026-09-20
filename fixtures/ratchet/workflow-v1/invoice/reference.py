from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext


def invoice_total(lines, discount_bps=0, shipping_cents=0):
    if type(discount_bps) is not int or not 0 <= discount_bps <= 10000:
        raise ValueError("invalid discount")
    if type(shipping_cents) is not int or shipping_cents < 0:
        raise ValueError("invalid shipping")
    amounts = []
    for line in lines:
        if not isinstance(line, dict) or not {"quantity", "unit_price"} <= line.keys():
            raise ValueError("invalid line")
        q, raw = line["quantity"], line["unit_price"]
        if isinstance(q, str) and q and q.isascii() and q.isdigit():
            q = int(q)
        if type(q) is not int or q <= 0 or not isinstance(raw, str):
            raise ValueError("invalid line values")
        try:
            price = Decimal(raw)
        except InvalidOperation as exc:
            raise ValueError("invalid price") from exc
        if not price.is_finite() or price < 0:
            raise ValueError("invalid price")
        amounts.append((q, price))
    with localcontext() as ctx:
        # Keep enough coefficient precision for the authored finite test values.
        ctx.prec = max(50, len(str(shipping_cents)) + 2, sum(len(str(q)) + len(p.as_tuple().digits)
                              + abs(p.as_tuple().exponent) for q, p in amounts) + 20)
        subtotal = sum((Decimal(q) * p for q, p in amounts), Decimal(0))
        cents = subtotal * (Decimal(10000 - discount_bps) / 100) + shipping_cents
        return int(cents.quantize(Decimal(1), rounding=ROUND_HALF_UP))
