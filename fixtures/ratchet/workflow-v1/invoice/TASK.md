# Repair invoice arithmetic

Two failed attempts are recorded in the supplied history. Repair product.py;
keep the existing tests unchanged and run them.

invoice_total(lines, discount_bps=0, shipping_cents=0) returns an integer number
of cents. Each line is a dictionary with quantity and unit_price. Quantity must
be a positive integer (not bool), or a nonempty ASCII digit string representing
a positive integer. unit_price must be a string representing a finite,
nonnegative Decimal. Decimal strings may include fractional cents. Reject invalid
values with ValueError, including missing fields or a non-dictionary line.

discount_bps must be an integer from 0 through 10000, excluding bool.
shipping_cents must be a nonnegative integer, excluding bool. Sum exact line
amounts, apply the discount to that subtotal, add shipping, and round the final
total to cents with ROUND_HALF_UP. Do not round individual lines or use binary
floating point for money. Empty lines produce the shipping total. Do not modify
the input list or dictionaries. Python's standard library is sufficient.

Example: two items at "10.00" plus one at "3.50" cost 2350 cents. A 1000-basis-point
discount and 125 cents shipping change that total to 2240 cents.
