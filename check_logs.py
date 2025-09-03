import sqlite3

conn = sqlite3.connect("rekber.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

rows = cur.execute("SELECT * FROM logs ORDER BY created_at DESC").fetchall()
for row in rows:
    print(dict(row))

conn.close()
