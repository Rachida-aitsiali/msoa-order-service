import sqlite3

conn = sqlite3.connect("orders.db")
with open("schema.sql", encoding="utf-8") as f:
    conn.executescript(f.read())
conn.commit()
conn.close()
print("Base orders.db créée")