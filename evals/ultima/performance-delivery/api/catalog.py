def catalog_page(store, render):
    products = store.all_products()
    visible = [product for product in products if product.public]
    return render(visible[:20])
