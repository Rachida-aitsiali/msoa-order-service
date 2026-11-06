import sqlite3

conn = sqlite3.connect("orders.db")
print("TABLES:", [r[0] for r in conn.execute("select name from sqlite_master where type='table'")])
print("\n--- orders ---")
for row in conn.execute("select * from orders"):
    print(row)
print("\n--- order_items ---")
for row in conn.execute("select * from order_items"):
    print(row)