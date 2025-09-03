import sqlite3
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

def get_sqlite_connection():
    """Get SQLite connection as fallback"""
    try:
        conn = sqlite3.connect('rekber_backup.db', check_same_thread=False)
        conn.row_factory = sqlite3.Row  # Make results dict-like
        return conn
    except Exception as e:
        logger.error(f"SQLite connection error: {e}")
        return None

def init_sqlite_db():
    """Initialize SQLite database with all required tables"""
    try:
        conn = get_sqlite_connection()
        if not conn:
            return False
            
        cur = conn.cursor()
        
        # Create deals table
        cur.execute('''
        CREATE TABLE IF NOT EXISTS deals (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            amount INTEGER NOT NULL,
            buyer_id INTEGER,
            seller_id INTEGER,
            status TEXT DEFAULT 'PENDING_JOIN',
            admin_fee INTEGER DEFAULT 0,
            admin_fee_payer TEXT DEFAULT 'BUYER',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Create logs table
        cur.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deal_id TEXT,
            actor_id INTEGER,
            role TEXT,
            action TEXT,
            detail TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (deal_id) REFERENCES deals (id)
        )
        ''')

        # Create ratings table
        cur.execute('''
        CREATE TABLE IF NOT EXISTS ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deal_id TEXT,
            user_id INTEGER,
            rating INTEGER CHECK (rating >= 1 AND rating <= 5),
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (deal_id) REFERENCES deals (id)
        )
        ''')

        # Create payouts table
        cur.execute('''
        CREATE TABLE IF NOT EXISTS payouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deal_id TEXT,
            seller_id INTEGER,
            method TEXT,
            account_details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (deal_id) REFERENCES deals (id)
        )
        ''')

        # Create shipments table
        cur.execute('''
        CREATE TABLE IF NOT EXISTS shipments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deal_id TEXT,
            tracking_info TEXT,
            shipping_method TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (deal_id) REFERENCES deals (id)
        )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("SQLite database initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize SQLite database: {e}")
        return False

def sqlite_execute(query: str, params: tuple = (), fetch_one: bool = False, fetch_all: bool = False):
    """Execute SQLite query with proper error handling"""
    try:
        conn = get_sqlite_connection()
        if not conn:
            return None
            
        cur = conn.cursor()
        cur.execute(query, params)
        
        if fetch_one:
            result = cur.fetchone()
        elif fetch_all:
            result = cur.fetchall()
        else:
            result = cur.rowcount
            
        conn.commit()
        conn.close()
        return result
        
    except Exception as e:
        logger.error(f"SQLite query error: {e}")
        return None

# Initialize database on module load
init_sqlite_db()