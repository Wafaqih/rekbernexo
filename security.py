
import hashlib
import secrets
import time
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
import config

# Rate limiting storage
user_last_action = {}
RATE_LIMIT_SECONDS = 30

def rate_limit(func):
    """Decorator untuk rate limiting"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        current_time = time.time()
        
        if user_id in user_last_action:
            if current_time - user_last_action[user_id] < RATE_LIMIT_SECONDS:
                if update.message:
                    await update.message.reply_text("⚠️ Mohon tunggu sebelum melakukan aksi berikutnya.")
                elif update.callback_query:
                    await update.callback_query.answer("⚠️ Mohon tunggu sebelum melakukan aksi berikutnya.", show_alert=True)
                return
        
        user_last_action[user_id] = current_time
        return await func(update, context, *args, **kwargs)
    return wrapper

def validate_amount(amount_str: str) -> tuple[bool, int]:
    """Validasi amount dengan keamanan ekstra"""
    try:
        # Hapus karakter non-digit kecuali koma dan titik
        cleaned = ''.join(c for c in amount_str if c.isdigit() or c in '.,')
        cleaned = cleaned.replace('.', '').replace(',', '')
        
        amount = int(cleaned)
        
        # Validasi range
        if amount < 1000:  # Minimal Rp 1.000
            return False, 0
        if amount > 100_000_000:  # Maksimal Rp 100 juta
            return False, 0
            
        return True, amount
    except ValueError:
        return False, 0

def sanitize_input(text: str, max_length: int = 500) -> str:
    """Sanitasi input text untuk mencegah injection"""
    if not text:
        return ""
    
    # Hapus karakter berbahaya
    dangerous_chars = ['<', '>', '{', '}', '[', ']', '`', '|']
    for char in dangerous_chars:
        text = text.replace(char, '')
    
    # Batasi panjang
    return text[:max_length].strip()

def encrypt_sensitive_data(data: str) -> str:
    """Enkripsi sederhana untuk data sensitif"""
    if not data:
        return ""
    
    # Menggunakan hash untuk menyembunyikan data sensitif
    # Dalam implementasi nyata, gunakan proper encryption library
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256((data + salt).encode()).hexdigest()
    return f"{salt}:{hashed}"

def validate_bank_account(account_number: str) -> bool:
    """Validasi nomor rekening"""
    if not account_number:
        return False
    
    # Hapus spasi dan karakter non-digit
    cleaned = ''.join(c for c in account_number if c.isdigit())
    
    # Validasi panjang (6-20 digit untuk rekening bank Indonesia)
    if len(cleaned) < 6 or len(cleaned) > 20:
        return False
        
    return True

def validate_phone_number(phone: str) -> bool:
    """Validasi nomor telepon untuk e-wallet"""
    if not phone:
        return False
    
    # Hapus karakter non-digit
    cleaned = ''.join(c for c in phone if c.isdigit())
    
    # Format Indonesia: 08xxx atau 628xxx
    if cleaned.startswith('08') and len(cleaned) >= 10 and len(cleaned) <= 13:
        return True
    if cleaned.startswith('628') and len(cleaned) >= 11 and len(cleaned) <= 14:
        return True
        
    return False

def generate_secure_deal_id() -> str:
    """Generate secure deal ID dengan collision resistance"""
    timestamp = int(time.time())
    random_part = secrets.token_hex(4).upper()
    return f"RB-{timestamp}-{random_part}"

def log_security_event(event_type: str, user_id: int, details: str):
    """Log security events untuk monitoring"""
    from db_sqlite import get_connection
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        # Buat tabel security_logs jika belum ada (PostgreSQL syntax)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS security_logs (
            id SERIAL PRIMARY KEY,
            event_type TEXT NOT NULL,
            user_id BIGINT NOT NULL,
            details TEXT,
            ip_address TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        cur.execute(
            "INSERT INTO security_logs (event_type, user_id, details) VALUES (%s, %s, %s)",
            (event_type, user_id, details)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        # Log ke console jika database gagal
        print(f"Failed to log security event: {e}")
    finally:
        conn.close()

def check_admin_permission(user_id: int, action: str) -> bool:
    """Cek permission admin untuk aksi tertentu"""
    if user_id not in config.ADMIN_IDS:
        return False
    
    # Log admin actions
    log_security_event("ADMIN_ACTION", user_id, f"Attempted action: {action}")
    return True

def validate_deal_access(deal_id: str, user_id: int) -> tuple[bool, str]:
    """Validasi apakah user berhak akses deal tertentu"""
    from db_sqlite import get_connection
    
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT buyer_id, seller_id FROM deals WHERE id = %s", (deal_id,))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        return False, "Deal tidak ditemukan"
    
    buyer_id, seller_id = row
    if user_id not in [buyer_id, seller_id] and user_id not in config.ADMIN_IDS:
        log_security_event("UNAUTHORIZED_ACCESS", user_id, f"Attempted access to deal: {deal_id}")
        return False, "Akses tidak diizinkan"
    
    return True, "OK"
