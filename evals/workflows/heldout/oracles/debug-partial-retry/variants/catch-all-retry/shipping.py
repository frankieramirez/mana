"""Order shipping: reserve stock for an order, then buy a carrier label."""


class OutOfStock(Exception):
    """Not enough stock to reserve the order."""


class TransientCarrierError(Exception):
    """The carrier timed out. The same label request may be sent again."""


class CarrierRejected(Exception):
    """The carrier refused the parcel. Sending it again will not help."""


def reserve(store, order):
    sku = order["sku"]
    if store["stock"][sku] < order["qty"]:
        raise OutOfStock(order["id"])
    store["stock"][sku] -= order["qty"]
    store["reservations"][order["id"]] = order["qty"]


def ship(store, order, carrier, attempts=3):
    """Reserve stock and return the carrier label for one order."""
    if order["id"] in store["labels"]:
        return store["labels"][order["id"]]
    if order["id"] not in store["reservations"]:
        reserve(store, order)
    for attempt in range(1, attempts + 1):
        try:
            label = carrier.create_label(order["id"])
        except Exception:
            if attempt == attempts:
                raise
            continue
        store["labels"][order["id"]] = label
        return label
