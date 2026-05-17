import sqlite3
conn = sqlite3.connect("pos_inventory.db")
cur = conn.cursor()
cur.execute("SELECT username, role, is_active FROM master_user")
print(cur.fetchall())
conn.close()
