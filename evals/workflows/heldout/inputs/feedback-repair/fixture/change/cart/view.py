from pricing.quote import line_total

MAX_CART_QUANTITY = 99


def cart_line(product, quantity):
    quantity = max(1, min(int(quantity), MAX_CART_QUANTITY))
    return line_total(product["price"], quantity)
