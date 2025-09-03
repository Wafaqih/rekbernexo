import os
import psycopg2
import psycopg2.extras
import psycopg2.pool
import random
from datetime import datetime
from typing import Optional, Dict, Any, List
import logging
import asyncio
from functools import wraps

logger = logging.getLogger(__name__)

# Connection pool untuk performa yang lebih baik
_connection_pool = None

def init_connection_pool():
    """Initialize connection pool untuk PostgreSQL"""
    global _connection_pool
    if _connection_pool is None:
        try:
            _connection_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=2,
                maxconn=20,
                dsn=os.getenv("DATABASE_URL"),
                cursor_factory=psycopg2.extras.RealDictCursor
            )
            logger.info("Database connection pool initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database connection pool: {e}")
            _connection_pool = None
    return _connection_pool

def get_connection():
    """Mendapatkan koneksi dari pool, fallback to SQLite if PostgreSQL unavailable"""
    global _connection_pool
    if _connection_pool is None:
        init_connection_pool()
    if _connection_pool is None:
        # Use SQLite fallback
        logger.warning("PostgreSQL unavailable, using SQLite fallback")
        from db_sqlite_fallback import get_sqlite_connection
        return get_sqlite_connection()
    try:
        return _connection_pool.getconn()
    except psycopg2.pool.PoolError as e:
        logger.error(f"Connection pool exhausted: {e}")
        # Try to reinitialize pool if exhausted
        _connection_pool = None
        init_connection_pool()
        if _connection_pool is None:
            # Fallback to SQLite
            logger.warning("PostgreSQL connection failed, using SQLite fallback")
            from db_sqlite_fallback import get_sqlite_connection
            return get_sqlite_connection()
        return _connection_pool.getconn()
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        # Fallback to SQLite instead of raising exception
        logger.warning("PostgreSQL error, using SQLite fallback")
        from db_sqlite_fallback import get_sqlite_connection
        return get_sqlite_connection()

def return_connection(conn):
    """Mengembalikan koneksi ke pool"""
    if _connection_pool:
        try:
            _connection_pool.putconn(conn)
        except:
            # If it's SQLite connection, just close it
            try:
                conn.close()
            except:
                pass
    else:
        # SQLite connection, just close it
        try:
            conn.close()
        except:
            pass

def with_db_connection(func):
    """Decorator untuk auto-manage database connections"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            conn = get_connection()
            try:
                result = func(conn, *args, **kwargs)
                return result
            finally:
                return_connection(conn)
        except Exception as e:
            logger.warning(f"Database operation failed: {e}")
            # Return None or empty result for database failures
            return None
    return wrapper

def init_db():
    """Inisialisasi schema database PostgreSQL"""
    # Initialize connection pool first
    pool = init_connection_pool()
    if pool is None:
        logger.warning("Database connection pool failed to initialize. Bot will start without database.")
        return
    
    try:
        conn = get_connection()
        cur = conn.cursor()
    except Exception as e:
        logger.error(f"Failed to get database connection during init: {e}")
        logger.warning("Bot will start without database initialization.")
        return
    
    try:
        # Tabel deals (transaksi rekber)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS deals (
            id VARCHAR(50) PRIMARY KEY,
            title TEXT NOT NULL,
            amount INTEGER NOT NULL,
            buyer_id BIGINT,
            seller_id BIGINT,
            status VARCHAR(50) DEFAULT 'CREATED',
            fund_status VARCHAR(50) DEFAULT 'UNPAID',
            admin_fee INTEGER DEFAULT 0,
            admin_fee_payer VARCHAR(20) DEFAULT 'BUYER',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            CONSTRAINT deals_participants_check CHECK (buyer_id IS NOT NULL OR seller_id IS NOT NULL)
        )
        """)
        
        # Index untuk performa query
        cur.execute("CREATE INDEX IF NOT EXISTS idx_deals_buyer_id ON deals(buyer_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_deals_seller_id ON deals(seller_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_deals_status ON deals(status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_deals_created_at ON deals(created_at)")

        # Tabel logs (riwayat aktivitas)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id SERIAL PRIMARY KEY,
            deal_id VARCHAR(50) NOT NULL,
            actor_id BIGINT NOT NULL,
            role VARCHAR(20) NOT NULL,
            action VARCHAR(50) NOT NULL,
            detail TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (deal_id) REFERENCES deals(id) ON DELETE CASCADE
        )
        """)
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_logs_deal_id ON logs(deal_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_logs_created_at ON logs(created_at)")

        # Tabel disputes (sengketa)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS disputes (
            id SERIAL PRIMARY KEY,
            deal_id VARCHAR(50) NOT NULL,
            raised_by BIGINT NOT NULL,
            reason TEXT,
            evidence TEXT,
            status VARCHAR(20) DEFAULT 'OPEN',
            resolved_by BIGINT,
            resolution TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP,
            FOREIGN KEY (deal_id) REFERENCES deals(id) ON DELETE CASCADE
        )
        """)

        # Tabel shipments (pengiriman)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS shipments (
            id SERIAL PRIMARY KEY,
            deal_id VARCHAR(50) NOT NULL,
            seller_id BIGINT NOT NULL,
            tracking_no TEXT,
            courier TEXT,
            proof TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (deal_id) REFERENCES deals(id) ON DELETE CASCADE
        )
        """)

        # Tabel ratings (penilaian)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS ratings (
            id SERIAL PRIMARY KEY,
            deal_id VARCHAR(50) NOT NULL,
            user_id BIGINT NOT NULL,
            rating INTEGER CHECK (rating >= 1 AND rating <= 5),
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (deal_id) REFERENCES deals(id) ON DELETE CASCADE,
            UNIQUE(deal_id, user_id)
        )
        """)

        # Tabel payouts (pencairan dana)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS payouts (
            id SERIAL PRIMARY KEY,
            deal_id VARCHAR(50) UNIQUE NOT NULL,
            seller_id BIGINT NOT NULL,
            method VARCHAR(20) NOT NULL CHECK (method IN ('BANK', 'EWALLET')),
            bank_name TEXT,
            account_number TEXT,
            account_name TEXT,
            ewallet_provider TEXT,
            ewallet_number TEXT,
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (deal_id) REFERENCES deals(id) ON DELETE CASCADE
        )
        """)
        
        # Tabel users untuk statistik dan riwayat pengguna
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            total_deals INTEGER DEFAULT 0,
            successful_deals INTEGER DEFAULT 0,
            average_rating DECIMAL(2,1),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Tabel untuk rate limiting dan security
        cur.execute("""
        CREATE TABLE IF NOT EXISTS rate_limits (
            user_id BIGINT NOT NULL,
            action VARCHAR(50) NOT NULL,
            count INTEGER DEFAULT 1,
            reset_time TIMESTAMP DEFAULT (CURRENT_TIMESTAMP + INTERVAL '1 hour'),
            PRIMARY KEY (user_id, action)
        )
        """)

        conn.commit()
        logger.info("Database PostgreSQL berhasil diinisialisasi")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error saat inisialisasi database: {e}")
        raise
    finally:
        cur.close()
        conn.close()

@with_db_connection
def log_action(conn, deal_id: str, actor_id: int, role: str, action: str, detail: str = None):
    """Mencatat aktivitas ke tabel logs dengan connection pooling"""
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO logs (deal_id, actor_id, role, action, detail, created_at) VALUES (%s,%s,%s,%s,%s,%s)",
            (deal_id, actor_id, role, action, detail or "", datetime.now())
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error saat mencatat log: {e}")
        raise
    finally:
        cur.close()

def log_action_bulk(logs_data: List[Dict]):
    """Bulk insert untuk multiple logs sekaligus"""
    if not logs_data:
        return
        
    conn = get_connection()
    cur = conn.cursor()
    try:
        values = [(log['deal_id'], log['actor_id'], log['role'], 
                  log['action'], log.get('detail'), datetime.now()) 
                 for log in logs_data]
        
        cur.executemany(
            "INSERT INTO logs (deal_id, actor_id, role, action, detail, created_at) VALUES (%s,%s,%s,%s,%s,%s)",
            values
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error saat bulk insert logs: {e}")
        raise
    finally:
        cur.close()
        return_connection(conn)

def save_payout_info(deal_id: str, seller_id: int, method: str,
                    bank_name=None, account_number=None, account_name=None,
                    ewallet_provider=None, ewallet_number=None, note=None):
    """Menyimpan informasi pencairan dana"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
        INSERT INTO payouts (deal_id, seller_id, method, bank_name, account_number, 
                           account_name, ewallet_provider, ewallet_number, note)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT(deal_id) DO UPDATE SET
            seller_id = EXCLUDED.seller_id,
            method = EXCLUDED.method,
            bank_name = EXCLUDED.bank_name,
            account_number = EXCLUDED.account_number,
            account_name = EXCLUDED.account_name,
            ewallet_provider = EXCLUDED.ewallet_provider,
            ewallet_number = EXCLUDED.ewallet_number,
            note = EXCLUDED.note
        """, (deal_id, seller_id, method, bank_name, account_number, 
              account_name, ewallet_provider, ewallet_number, note))
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error saat menyimpan info payout: {e}")
        raise
    finally:
        cur.close()
        conn.close()

def get_payout_info(deal_id: str) -> Optional[Dict[str, Any]]:
    """Mendapatkan informasi pencairan dana"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM payouts WHERE deal_id=%s", (deal_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error saat mengambil info payout: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def generate_deal_id() -> str:
    """Generate ID unik untuk transaksi Rekber"""
    now = datetime.now().strftime("%y%m%d%H%M%S")
    rand = random.randint(100, 999)
    return f"RB-{now}{rand}"

def get_user_stats(user_id: int) -> Dict[str, Any]:
    """Mendapatkan statistik pengguna"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Statistik deal
        cur.execute("""
        SELECT 
            COUNT(*) as total_deals,
            COUNT(CASE WHEN status = 'COMPLETED' THEN 1 END) as completed_deals,
            COUNT(CASE WHEN status = 'CANCELLED' OR status = 'REFUNDED' THEN 1 END) as cancelled_deals
        FROM deals 
        WHERE buyer_id = %s OR seller_id = %s
        """, (user_id, user_id))
        
        stats = cur.fetchone()
        
        # Rating rata-rata
        cur.execute("""
        SELECT AVG(rating)::DECIMAL(2,1) as avg_rating, COUNT(*) as total_ratings
        FROM ratings r
        JOIN deals d ON r.deal_id = d.id
        WHERE (d.buyer_id = %s OR d.seller_id = %s) AND r.user_id != %s
        """, (user_id, user_id, user_id))
        
        rating_stats = cur.fetchone()
        
        return {
            'total_deals': stats['total_deals'] or 0,
            'completed_deals': stats['completed_deals'] or 0,
            'cancelled_deals': stats['cancelled_deals'] or 0,
            'success_rate': round((stats['completed_deals'] or 0) / max(stats['total_deals'] or 1, 1) * 100, 1),
            'average_rating': float(rating_stats['avg_rating']) if rating_stats['avg_rating'] else 0.0,
            'total_ratings': rating_stats['total_ratings'] or 0
        }
        
    except Exception as e:
        logger.error(f"Error saat mengambil statistik user: {e}")
        return {
            'total_deals': 0,
            'completed_deals': 0, 
            'cancelled_deals': 0,
            'success_rate': 0.0,
            'average_rating': 0.0,
            'total_ratings': 0
        }
    finally:
        cur.close()
        conn.close()

def check_rate_limit(user_id: int, action: str, max_count: int = 5) -> bool:
    """Mengecek rate limiting untuk mencegah spam"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Hapus record yang sudah expired
        cur.execute("DELETE FROM rate_limits WHERE reset_time < CURRENT_TIMESTAMP")
        
        # Cek current count
        cur.execute("SELECT count FROM rate_limits WHERE user_id = %s AND action = %s", (user_id, action))
        row = cur.fetchone()
        
        if not row:
            # Insert new record
            cur.execute("""
            INSERT INTO rate_limits (user_id, action, count, reset_time) 
            VALUES (%s, %s, 1, CURRENT_TIMESTAMP + INTERVAL '1 hour')
            """, (user_id, action))
            conn.commit()
            return True
        
        if row['count'] >= max_count:
            return False
        
        # Increment count
        cur.execute("""
        UPDATE rate_limits SET count = count + 1 
        WHERE user_id = %s AND action = %s
        """, (user_id, action))
        conn.commit()
        return True
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error saat cek rate limit: {e}")
        return True  # Allow on error to prevent blocking legitimate users
    finally:
        cur.close()
        conn.close()

def update_user_activity(user_id: int, username: str = None, first_name: str = None, last_name: str = None):
    """Update aktivitas terakhir pengguna"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
        INSERT INTO users (user_id, username, first_name, last_name, last_activity)
        VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (user_id) DO UPDATE SET
            username = EXCLUDED.username,
            first_name = EXCLUDED.first_name,
            last_name = EXCLUDED.last_name,
            last_activity = CURRENT_TIMESTAMP
        """, (user_id, username or "", first_name or "", last_name or ""))
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error saat update aktivitas user: {e}")
    finally:
        cur.close()
        conn.close()

def get_admin_dashboard_stats() -> Dict[str, Any]:
    """Mendapatkan statistik untuk dashboard admin"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Total deals
        cur.execute("SELECT COUNT(*) as total FROM deals")
        total_deals = cur.fetchone()['total']
        
        # Deals by status  
        cur.execute("""
        SELECT status, COUNT(*) as count 
        FROM deals 
        GROUP BY status
        ORDER BY count DESC
        """)
        status_counts = {row['status']: row['count'] for row in cur.fetchall()}
        
        # Total volume transaksi
        cur.execute("SELECT COALESCE(SUM(amount), 0) as total_volume FROM deals WHERE status = 'COMPLETED'")
        total_volume = cur.fetchone()['total_volume']
        
        # Deals hari ini
        cur.execute("SELECT COUNT(*) as today FROM deals WHERE DATE(created_at) = CURRENT_DATE")
        deals_today = cur.fetchone()['today']
        
        # Active users (activity dalam 30 hari)
        cur.execute("SELECT COUNT(*) as active FROM users WHERE last_activity > CURRENT_TIMESTAMP - INTERVAL '30 days'")
        active_users = cur.fetchone()['active']
        
        # Pending verifications
        cur.execute("SELECT COUNT(*) as pending FROM deals WHERE status = 'WAITING_VERIFICATION'")
        pending_verifications = cur.fetchone()['pending']
        
        # Open disputes
        cur.execute("SELECT COUNT(*) as open FROM disputes WHERE status = 'OPEN'")
        open_disputes = cur.fetchone()['open']
        
        return {
            'total_deals': total_deals,
            'status_counts': status_counts,
            'total_volume': total_volume,
            'deals_today': deals_today,
            'active_users': active_users,
            'pending_verifications': pending_verifications,
            'open_disputes': open_disputes
        }
        
    except Exception as e:
        logger.error(f"Error saat mengambil statistik dashboard: {e}")
        return {}
    finally:
        cur.close()
        conn.close()