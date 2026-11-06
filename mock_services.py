import threading

from flask import Flask, jsonify, request

# Faux Catalog (8082), Inventory (8083) et Shipping (8086), pour tester seul.
PRODUCTS = {
    1: {"id": 1, "name": "Laptop", "price": 5000},
    2: {"id": 2, "name": "Wireless Mouse", "price": 199},
    3: {"id": 3, "name": "Keyboard", "price": 350},
}
STOCK = {1: 5, 2: 3, 3: 10}

catalog = Flask("catalog")
inventory = Flask("inventory")
shipping = Flask("shipping")


@catalog.get("/products/<int:pid>")
def get_product(pid):
    if pid not in PRODUCTS:
        return jsonify({"message": "Product not found."}), 404
    return jsonify(PRODUCTS[pid])


@inventory.get("/api/inventory/<int:pid>")
def get_stock(pid):
    return jsonify({"stock": STOCK.get(pid, 0)})


@inventory.post("/api/inventory/reserve")
def reserve():
    items = (request.get_json(silent=True) or {}).get("items", [])
    for it in items:
        if STOCK.get(it["productId"], 0) < it["quantity"]:
            return jsonify({"message": f"Insufficient stock for product {it['productId']}."}), 409
    for it in items:
        STOCK[it["productId"]] -= it["quantity"]
    print("STOCK:", STOCK)
    return jsonify({"success": True})


@inventory.post("/api/inventory/release")
def release():
    items = (request.get_json(silent=True) or {}).get("items", [])
    for it in items:
        STOCK[it["productId"]] = STOCK.get(it["productId"], 0) + it["quantity"]
    print("STOCK:", STOCK)
    return jsonify({"success": True})


@shipping.get("/api/shipments/order/<order_id>")
def shipment_by_order(order_id):
    # Aucune livraison creee : le front attend un 404 dans ce cas
    return jsonify({"message": "Shipment not found."}), 404


def run(app, port):
    app.run(host="0.0.0.0", port=port, use_reloader=False)


if __name__ == "__main__":
    threading.Thread(target=run, args=(catalog, 8082), daemon=True).start()
    threading.Thread(target=run, args=(shipping, 8086), daemon=True).start()
    run(inventory, 8083)