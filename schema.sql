PRAGMA foreign_keys = ON;
CREATE TABLE orders (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, customer_name TEXT NOT NULL, customer_address TEXT NOT NULL, customer_city TEXT NOT NULL, total REAL NOT NULL CHECK(total >= 0), status TEXT NOT NULL CHECK(status IN ('PENDING_PAYMENT','PAID','SHIPPED','DELIVERED','CANCELLED')), created_at TEXT NOT NULL);
CREATE TABLE order_items (id INTEGER PRIMARY KEY AUTOINCREMENT, order_id TEXT NOT NULL REFERENCES orders(id), product_id INTEGER NOT NULL, name TEXT NOT NULL, price REAL NOT NULL CHECK(price >= 0), quantity INTEGER NOT NULL CHECK(quantity > 0));
