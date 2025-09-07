from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from db_sqlite import get_admin_dashboard_stats, get_connection
from utils import format_rupiah
from security import check_admin_permission
import config
import logging

logger = logging.getLogger(__name__)

async def admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Dashboard statistik untuk admin"""
    user_id = update.effective_user.id
    
    # Cek permission admin
    if not check_admin_permission(user_id, "view_dashboard"):
        await update.message.reply_text("❌ Akses ditolak. Hanya admin yang dapat melihat dashboard.")
        return
    
    try:
        stats = get_admin_dashboard_stats()
        
        # Format pesan statistik
        dashboard_text = f"""
📊 **DASHBOARD ADMIN NEXOREKBER**
━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 **STATISTIK UMUM**
• Total Transaksi: {stats.get('total_deals', 0)}
• Transaksi Hari Ini: {stats.get('deals_today', 0)}
• Volume Total: {format_rupiah(stats.get('total_volume', 0))}
• User Aktif (30 hari): {stats.get('active_users', 0)}

⚠️ **PERLU PERHATIAN**
• Menunggu Verifikasi: {stats.get('pending_verifications', 0)}
• Dispute Terbuka: {stats.get('open_disputes', 0)}

📊 **STATUS TRANSAKSI**
"""
        
        # Tambahkan breakdown status
        status_counts = stats.get('status_counts', {})
        for status, count in status_counts.items():
            status_emoji = {
                'CREATED': '🆕',
                'WAITING_VERIFICATION': '⏳',
                'FUNDED': '💰',
                'SHIPPED': '📦',
                'COMPLETED': '✅',
                'CANCELLED': '❌',
                'DISPUTED': '⚖️',
                'REFUNDED': '↩️'
            }.get(status, '📋')
            dashboard_text += f"• {status_emoji} {status}: {count}\n"
        
        keyboard = [
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="admin_refresh_dashboard"),
                InlineKeyboardButton("👥 User Stats", callback_data="admin_user_stats")
            ],
            [
                InlineKeyboardButton("⚠️ Pending Actions", callback_data="admin_pending_actions"),
                InlineKeyboardButton("📊 Analytics", callback_data="admin_analytics")
            ],
            [InlineKeyboardButton("🏠 Back to Main", callback_data="rekber_main_menu")]
        ]
        
        await update.message.reply_text(
            dashboard_text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logger.error(f"Error in admin dashboard: {e}")
        await update.message.reply_text("❌ Terjadi error saat memuat dashboard.")

async def admin_pending_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tampilkan aksi yang perlu perhatian admin"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not check_admin_permission(user_id, "view_pending"):
        await query.edit_message_text("❌ Akses ditolak.")
        return
    
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        # Ambil transaksi yang menunggu verifikasi
        cur.execute("""
        SELECT id, title, amount, buyer_id, created_at 
        FROM deals 
        WHERE status = 'WAITING_VERIFICATION'
        ORDER BY created_at ASC
        LIMIT 10
        """)
        pending_deals = cur.fetchall()
        
        # Ambil dispute terbuka
        cur.execute("""
        SELECT d.deal_id, d.reason, d.created_at, deals.title
        FROM disputes d
        JOIN deals ON d.deal_id = deals.id
        WHERE d.status = 'OPEN'
        ORDER BY d.created_at ASC
        LIMIT 5
        """)
        open_disputes = cur.fetchall()
        
        cur.close()
        conn.close()
        
        pending_text = "⚠️ **AKSI YANG PERLU PERHATIAN**\n\n"
        
        if pending_deals:
            pending_text += "🔍 **MENUNGGU VERIFIKASI DANA:**\n"
            for deal in pending_deals:
                deal_id, title, amount, buyer_id, created_at = deal
                pending_text += f"• `{deal_id}` - {title}\n"
                pending_text += f"  💰 {format_rupiah(amount)} | 👤 User: {buyer_id}\n"
                pending_text += f"  📅 {created_at.strftime('%d/%m/%Y %H:%M')}\n\n"
        
        if open_disputes:
            pending_text += "⚖️ **DISPUTE TERBUKA:**\n"
            for dispute in open_disputes:
                deal_id, reason, created_at, title = dispute
                pending_text += f"• `{deal_id}` - {title}\n"
                pending_text += f"  📝 Alasan: {reason}\n"
                pending_text += f"  📅 {created_at.strftime('%d/%m/%Y %H:%M')}\n\n"
        
        if not pending_deals and not open_disputes:
            pending_text += "✅ Tidak ada aksi yang perlu perhatian saat ini."
        
        keyboard = [[
            InlineKeyboardButton("🔄 Refresh", callback_data="admin_pending_actions"),
            InlineKeyboardButton("🏠 Dashboard", callback_data="admin_dashboard_main")
        ]]
        
        await query.edit_message_text(
            pending_text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logger.error(f"Error in admin pending actions: {e}")
        await query.edit_message_text("❌ Terjadi error saat memuat data.")

async def admin_user_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Statistik pengguna untuk admin"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not check_admin_permission(user_id, "view_user_stats"):
        await query.edit_message_text("❌ Akses ditolak.")
        return
    
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        # Top users berdasarkan jumlah transaksi
        cur.execute("""
        SELECT 
            CASE 
                WHEN buyer_id IS NOT NULL THEN buyer_id 
                ELSE seller_id 
            END as user_id,
            COUNT(*) as deal_count,
            SUM(amount) as total_volume
        FROM deals 
        WHERE status = 'COMPLETED'
        GROUP BY user_id
        ORDER BY deal_count DESC
        LIMIT 10
        """)
        top_users = cur.fetchall()
        
        # Statistik user baru (registrasi dalam 7 hari terakhir)
        cur.execute("""
        SELECT COUNT(*) as new_users
        FROM users 
        WHERE created_at > CURRENT_TIMESTAMP - INTERVAL '7 days'
        """)
        new_users = cur.fetchone()
        
        cur.close()
        conn.close()
        
        stats_text = f"""
👥 **STATISTIK PENGGUNA**
━━━━━━━━━━━━━━━━━━━━

📊 **RINGKASAN:**
• User Baru (7 hari): {new_users['new_users'] if new_users else 0}

🏆 **TOP USERS (berdasarkan transaksi):**
"""
        
        for idx, user in enumerate(top_users, 1):
            user_id_val, deal_count, total_volume = user
            stats_text += f"{idx}. User `{user_id_val}`\n"
            stats_text += f"   📊 {deal_count} transaksi | 💰 {format_rupiah(total_volume or 0)}\n\n"
        
        keyboard = [[
            InlineKeyboardButton("🔄 Refresh", callback_data="admin_user_stats"),
            InlineKeyboardButton("🏠 Dashboard", callback_data="admin_dashboard_main")
        ]]
        
        await query.edit_message_text(
            stats_text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logger.error(f"Error in admin user stats: {e}")
        await query.edit_message_text("❌ Terjadi error saat memuat statistik user.")