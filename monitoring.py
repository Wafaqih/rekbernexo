
from datetime import datetime, timedelta
from db import get_connection
import config

def check_suspicious_activity():
    """Monitor aktivitas mencurigakan"""
    conn = get_connection()
    cur = conn.cursor()
    
    # Cek transaksi yang terlalu cepat dari user yang sama
    cur.execute("""
    SELECT user_id, COUNT(*) as count
    FROM (
        SELECT buyer_id as user_id FROM deals WHERE created_at > datetime('now', '-1 hour')
        UNION ALL
        SELECT seller_id as user_id FROM deals WHERE created_at > datetime('now', '-1 hour')
    )
    WHERE user_id IS NOT NULL
    GROUP BY user_id
    HAVING count > 5
    """)
    
    suspicious_users = cur.fetchall()
    
    for user in suspicious_users:
        alert_admin(f"⚠️ User {user['user_id']} membuat {user['count']} transaksi dalam 1 jam terakhir")
    
    # Cek transaksi dengan nominal mencurigakan
    cur.execute("""
    SELECT id, amount, buyer_id, seller_id
    FROM deals
    WHERE amount > 50000000 AND created_at > datetime('now', '-24 hours')
    """)
    
    high_value_deals = cur.fetchall()
    
    for deal in high_value_deals:
        alert_admin(f"🚨 Transaksi bernilai tinggi: {deal['id']} - Rp {deal['amount']:,}")
    
    conn.close()

def check_stuck_transactions():
    """Cek transaksi yang macet terlalu lama"""
    conn = get_connection()
    cur = conn.cursor()
    
    # Transaksi pending lebih dari 24 jam
    cur.execute("""
    SELECT id, title, amount, status, created_at
    FROM deals
    WHERE status IN ('PENDING_JOIN', 'PENDING_FUNDING', 'WAITING_VERIFICATION')
    AND created_at < datetime('now', '-24 hours')
    """)
    
    stuck_deals = cur.fetchall()
    
    for deal in stuck_deals:
        alert_admin(f"⏰ Transaksi macet: {deal['id']} - Status: {deal['status']} sejak {deal['created_at']}")
    
    conn.close()

async def alert_admin(message: str):
    """Kirim alert ke admin"""
    # Import di sini untuk menghindari circular import
    from telegram import Bot
    
    bot = Bot(token=config.BOT_TOKEN)
    
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, f"🔔 SECURITY ALERT\n\n{message}")
        except Exception as e:
            print(f"Failed to send alert to admin {admin_id}: {e}")

def generate_security_report():
    """Generate laporan keamanan harian"""
    conn = get_connection()
    cur = conn.cursor()
    
    # Statistik 24 jam terakhir
    cur.execute("""
    SELECT 
        COUNT(*) as total_transactions,
        SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) as completed,
        SUM(CASE WHEN status = 'DISPUTED' THEN 1 ELSE 0 END) as disputed,
        SUM(CASE WHEN status = 'CANCELLED' THEN 1 ELSE 0 END) as cancelled,
        AVG(amount) as avg_amount
    FROM deals
    WHERE created_at > datetime('now', '-24 hours')
    """)
    
    stats = cur.fetchone()
    
    # Cek security events
    cur.execute("""
    SELECT event_type, COUNT(*) as count
    FROM security_logs
    WHERE timestamp > datetime('now', '-24 hours')
    GROUP BY event_type
    """)
    
    security_events = cur.fetchall()
    
    report = f"""
📊 LAPORAN KEAMANAN HARIAN

📈 Statistik Transaksi (24 jam):
• Total: {stats['total_transactions']}
• Selesai: {stats['completed']}
• Sengketa: {stats['disputed']} 
• Dibatalkan: {stats['cancelled']}
• Rata-rata nilai: Rp {stats['avg_amount']:,.0f}

🔒 Security Events:
"""
    
    for event in security_events:
        report += f"• {event['event_type']}: {event['count']} kali\n"
    
    conn.close()
    return report
