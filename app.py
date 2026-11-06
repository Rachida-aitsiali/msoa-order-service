import os
import sqlite3
import uuid
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "orders.db")

# STANDALONE=1 : le service marche seul (prix = 0, pas d'appel aux autres services)
# STANDALONE=0 : appelle Catalog, Inventory et Shipping
STANDALONE = os.getenv("STANDALONE", "1") == "1"
CATALOG_URL = os.getenv("CATALOG_URL", "http://localhost:8082")
INVENTORY_URL = os.getenv("INVENTORY_URL", "http://localhost:8083")
SHIPPING_URL = os.getenv("SHIPPING_URL", "http://localhost:8086")

TRANSITIONS = {
    "PENDING_PAYMENT": ["PAID", "CANCELLED"],
    "PAID": ["SHIPPED", "CANCELLED"],
    "SHIPPED": ["DELIVERED"],
    "DELIVERED": [],
    "CANCELLED": [],
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def error(message, status):
    return jsonify({"message": message, "error": message}), status


def load_order(conn, order_id):
    row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if row is None:
        return None
    items = conn.execute(
        "SELECT product_id, name, price, quantity FROM order_items WHERE order_id = ? ORDER BY id",
        (order_id,),
    ).fetchall()
    return {
        "id": row["id"],
        "userId": row["user_id"],
        "customer": {
            "name": row["customer_name"],
            "address": row["customer_address"],
            "city": row["customer_city"],
        },
        "items": [
            {
                "productId": i["product_id"],
                "name": i["name"],
                "price": i["price"],
                "quantity": i["quantity"],
            }
            for i in items
        ],
        "total": row["total"],
        "status": row["status"],
        "createdAt": row["created_at"],
    }


# ---- Appels vers les autres services (contrats lus dans le front) ----
def _error_message(r, default):
    try:
        return r.json().get("message", default)
    except ValueError:
        return default


def fetch_product(product_id):
    """Catalog : GET /products/{id}  (sans /api)"""
    if STANDALONE:
        return {"name": f"Product {product_id}", "price": 0}
    r = requests.get(f"{CATALOG_URL}/products/{product_id}", timeout=5)
    if r.status_code == 404:
        raise ValueError(f"Product {product_id} not found.")
    r.raise_for_status()
    d = r.json()
    return {"name": d["name"], "price": d["price"]}


def reserve_stock(items):
    """Inventory : POST /api/inventory/reserve"""
    if STANDALONE:
        return
    r = requests.post(f"{INVENTORY_URL}/api/inventory/reserve", json={"items": items}, timeout=5)
    if 400 <= r.status_code < 500:
        raise ValueError(_error_message(r, "Insufficient stock."))
    r.raise_for_status()


def release_stock(items):
    """Inventory : POST /api/inventory/release (compensation)"""
    if STANDALONE:
        return
    r = requests.post(f"{INVENTORY_URL}/api/inventory/release", json={"items": items}, timeout=5)
    r.raise_for_status()


def get_shipment_status(order_id):
    """Shipping : GET /api/shipments/order/{orderId}"""
    if STANDALONE:
        return None
    r = requests.get(f"{SHIPPING_URL}/api/shipments/order/{order_id}", timeout=5)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json().get("status")


# ---- Routes ----
@app.get("/health")
def health():
    return jsonify({"status": "UP", "service": "order", "standalone": STANDALONE})


@app.get("/api/orders")
def list_orders():
    user_id = request.args.get("userId")
    if not user_id:
        return error("userId is required.", 400)
    conn = get_db()
    ids = conn.execute(
        "SELECT id FROM orders WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
    ).fetchall()
    result = [load_order(conn, r["id"]) for r in ids]
    conn.close()
    return jsonify(result)


@app.get("/api/orders/<order_id>")
def get_order(order_id):
    conn = get_db()
    order = load_order(conn, order_id)
    conn.close()
    if order is None:
        return error("Order not found.", 404)
    return jsonify(order)


@app.post("/api/orders")
def create_order():
    data = request.get_json(silent=True) or {}
    user_id = data.get("userId")
    customer = data.get("customer") or {}
    raw_items = data.get("items") or []

    if not user_id:
        return error("Authentication required.", 401)
    if not raw_items:
        return error("Cannot create an empty order.", 400)
    name, address, city = customer.get("name"), customer.get("address"), customer.get("city")
    if not (name and address and city):
        return error("Customer name, address and city are required.", 400)

    # 1) Nom et prix de chaque produit (Catalog)
    items = []
    try:
        for it in raw_items:
            qty = int(it["quantity"])
            pid = int(it["productId"])
            if qty <= 0:
                return error("Quantity must be positive.", 400)
            p = fetch_product(pid)
            items.append({"productId": pid, "name": p["name"], "price": p["price"], "quantity": qty})
    except (KeyError, TypeError, ValueError) as e:
        return error(str(e) or "Invalid items.", 400)
    except requests.RequestException:
        return error("Catalog service unavailable.", 503)

    # 2) Reservation du stock (Inventory) : si refus, aucune commande n'est creee
    stock_items = [{"productId": i["productId"], "quantity": i["quantity"]} for i in items]
    try:
        reserve_stock(stock_items)
    except ValueError as e:
        return error(str(e), 409)
    except requests.RequestException:
        return error("Inventory service unavailable.", 503)

    # 3) Enregistrement de la commande
    order_id = str(uuid.uuid4())
    total = sum(i["price"] * i["quantity"] for i in items)
    created_at = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    try:
        with conn:
            conn.execute(
                "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (order_id, user_id, name, address, city, total, "PENDING_PAYMENT", created_at),
            )
            for i in items:
                conn.execute(
                    "INSERT INTO order_items (order_id, product_id, name, price, quantity) VALUES (?, ?, ?, ?, ?)",
                    (order_id, i["productId"], i["name"], i["price"], i["quantity"]),
                )
    except sqlite3.Error:
        conn.close()
        try:
            release_stock(stock_items)  # compensation
        except requests.RequestException:
            pass
        return error("Could not save the order.", 500)
    order = load_order(conn, order_id)
    conn.close()
    return jsonify(order), 201


@app.patch("/api/orders/<order_id>/status")
def update_status(order_id):
    new_status = (request.get_json(silent=True) or {}).get("status")
    conn = get_db()
    order = load_order(conn, order_id)
    if order is None:
        conn.close()
        return error("Order not found.", 404)
    if new_status not in TRANSITIONS.get(order["status"], []):
        conn.close()
        return error(f"Invalid transition: {order['status']} -> {new_status}", 400)
    with conn:
        conn.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
    order = load_order(conn, order_id)
    conn.close()
    return jsonify(order)


@app.post("/api/orders/<order_id>/cancel")
def cancel_order(order_id):
    conn = get_db()
    order = load_order(conn, order_id)
    if order is None:
        conn.close()
        return error("Order not found.", 404)
    if order["status"] not in ("PENDING_PAYMENT", "PAID"):
        conn.close()
        return error("This order cannot be cancelled.", 400)
    try:
        shipment = get_shipment_status(order_id)
        if shipment and shipment not in ("PREPARING", "CANCELLED"):
            conn.close()
            return error("Cannot cancel an order that has already been shipped.", 400)
        release_stock([{"productId": i["productId"], "quantity": i["quantity"]} for i in order["items"]])
    except requests.RequestException:
        conn.close()
        return error("A dependent service is unavailable.", 503)
    with conn:
        conn.execute("UPDATE orders SET status = 'CANCELLED' WHERE id = ?", (order_id,))
    order = load_order(conn, order_id)
    conn.close()
    return jsonify(order)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8084, debug=True)