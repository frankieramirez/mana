# Shipping contract

`ship(store, order, carrier, attempts=3)` reserves stock for one order and returns its carrier label. `store` holds three maps: `stock` (units on hand per SKU), `reservations` (order id to reserved quantity) and `labels` (order id to label).

## Reservations

An order takes stock once. The `reservations` map records every order that already holds stock. An order listed there never takes stock again, including when the queue re-delivers it after a worker restart.

Different orders for the same SKU each take their own stock.

When stock is short, `ship` raises `OutOfStock` before contacting the carrier and leaves the store unchanged.

`ship` never releases a reservation. The nightly cancel job releases reservations for orders that never got a label.

## Carrier calls

A carrier timeout (`TransientCarrierError`) is safe to retry. `ship` sends at most `attempts` label requests in total. After the last timeout it raises `TransientCarrierError`, and the order keeps its reservation for the next delivery.

A rejection (`CarrierRejected`) is final. Raise it after one request.

An order that already has a label returns that label without contacting the carrier.

Any other exception means a bug in our code or in the carrier client. It must propagate unchanged the first time it happens, without a retry.
