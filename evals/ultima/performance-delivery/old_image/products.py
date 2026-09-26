def product_names(db):
    return db.query('SELECT legacy_name FROM products')
