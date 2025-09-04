import sqlite3

conn = sqlite3.connect("rekber.db")
cur = conn.cursor()

# Tambah kolom admin_fee
try:
    cur.execute("ALTER TABLE deals ADD COLUMN admin_fee INTEGER DEFAULT 0")
    print("Kolom admin_fee ditambahkan")
except sqlite3.OperationalError:
    print("Kolom admin_fee sudah ada")

# Tambah kolom total
try:
    cur.execute("ALTER TABLE deals ADD COLUMN total INTEGER DEFAULT 0")
    print("Kolom total ditambahkan")
except sqlite3.OperationalError:
    print("Kolom total sudah ada")

# Tambah kolom admin_fee_payer
try:
    cur.execute("ALTER TABLE deals ADD COLUMN admin_fee_payer TEXT")
    print("Kolom admin_fee_payer ditambahkan")
except sqlite3.OperationalError:
    print("Kolom admin_fee_payer sudah ada")

# Tambah kolom joined_by
try:
    cur.execute("ALTER TABLE deals ADD COLUMN joined_by INTEGER")
    print("Kolom joined_by ditambahkan")
except sqlite3.OperationalError:
    print("Kolom joined_by sudah ada")

# Tambah kolom payment_proof_file_id untuk menyimpan file_id bukti pembayaran
try:
    cur.execute("ALTER TABLE deals ADD COLUMN payment_proof_file_id TEXT")
    print("Kolom payment_proof_file_id ditambahkan")
except sqlite3.OperationalError:
    print("Kolom payment_proof_file_id sudah ada")

conn.commit()
conn.close()
print("Migrasi selesai ✅")
