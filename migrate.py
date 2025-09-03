import sqlite3

conn = sqlite3.connect("rekber.db")
cur = conn.cursor()

# Tambah kolom admin_fee
try:
    cur.execute("ALTER TABLE deals ADD COLUMN admin_fee INTEGER DEFAULT 0")
except sqlite3.OperationalError:
    print("Kolom admin_fee sudah ada")

# Tambah kolom total
try:
    cur.execute("ALTER TABLE deals ADD COLUMN total INTEGER DEFAULT 0")
except sqlite3.OperationalError:
    print("Kolom total sudah ada")

# Tambah kolom admin_fee_payer
try:
    cur.execute("ALTER TABLE deals ADD COLUMN admin_fee_payer TEXT")
except sqlite3.OperationalError:
    print("Kolom admin_fee_payer sudah ada")

conn.commit()
conn.close()
print("Migrasi selesai ✅")
