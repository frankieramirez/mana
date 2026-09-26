def list_orders(db):
    orders = db.query('SELECT id FROM orders')
    return [{'id': order.id, 'items': db.query('SELECT * FROM items WHERE order_id = ?', order.id)} for order in orders]


def preview(db):
    orders = db.query('SELECT id FROM orders LIMIT 5')
    return [{'id': order.id, 'items': db.query('SELECT * FROM items WHERE order_id = ?', order.id)} for order in orders]


def export_orders(db, response):
    response.write(list_orders(db))
