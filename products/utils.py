def calculate_discount(product):
    product.current_price_display = f"${product.current_price:,.2f}"
    if product.sale_price and product.sale_price < product.base_price:
        product.discount_percentage = int(((product.base_price - product.sale_price) / product.base_price) * 100)
    else:
        product.discount_percentage = 0
    return product