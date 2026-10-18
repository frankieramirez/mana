"""Invoice totals in integer cents."""


def line_total_cents(quantity, unit_cents):
    return quantity * unit_cents


def invoice_total_cents(lines, discount_percent=0):
    subtotal = sum(line_total_cents(quantity, unit) for quantity, unit in lines)
    discount = (subtotal * discount_percent + 50) // 100
    return subtotal - discount
