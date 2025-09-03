
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from db_postgres import get_connection
from utils import format_rupiah
import logging

logger = logging.getLogger(__name__)

async def rekber_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk cek status transaksi spesifik"""
    query = update.callback_query
    await query.answer()
    
    deal_id = query.data.split("|")[1]
    user_id = query.from_user.id
    
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, title, amount, admin_fee, admin_fee_payer, buyer_id, seller_id, status, created_at
        FROM deals WHERE id = %s
    """, (deal_id,))
    
    row = cur.fetchone()
    conn.close()
    
    if not row:
        await query.edit_message_text("❌ Transaksi tidak ditemukan.")
        return
    
    title = row['title']
    amount = int(row['amount'])
    admin_fee = int(row['admin_fee'])
    admin_fee_payer = row['admin_fee_payer']
    buyer_id = row['buyer_id']
    seller_id = row['seller_id']
    status = row['status']
    created_at = row['created_at']
    
    # Determine user role
    user_role = None
    if user_id == buyer_id:
        user_role = "BUYER"
    elif user_id == seller_id:
        user_role = "SELLER"
    
    # Calculate amounts
    buyer_total = amount + admin_fee if admin_fee_payer == "BUYER" else amount
    seller_receive = amount if admin_fee_payer == "BUYER" else amount - admin_fee
    
    # Status descriptions
    status_descriptions = {
        "PENDING_JOIN": "⏳ Menunggu pihak lain bergabung",
        "PENDING_FUNDING": "💰 Menunggu pembayaran dari pembeli", 
        "WAITING_VERIFICATION": "🔍 Menunggu verifikasi dana oleh admin",
        "FUNDED": "✅ Dana sudah terverifikasi, menunggu pengiriman",
        "AWAITING_CONFIRM": "📦 Barang sudah dikirim, menunggu konfirmasi pembeli",
        "AWAITING_PAYOUT": "💳 Menunggu admin memproses pencairan",
        "COMPLETED": "🎉 Transaksi selesai",
        "CANCELLED": "❌ Transaksi dibatalkan",
        "DISPUTED": "⚖️ Dalam sengketa",
        "REFUNDED": "💸 Dana dikembalikan"
    }
    
    status_text = (
        f"📋 **STATUS TRANSAKSI**\n\n"
        f"🆔 **ID:** `{deal_id}`\n"
        f"📦 **Produk:** {title}\n"
        f"💰 **Harga:** {format_rupiah(amount)}\n"
        f"💸 **Biaya Admin:** {format_rupiah(admin_fee)} *(ditanggung {admin_fee_payer.lower()})*\n"
        f"📊 **Total Pembeli:** {format_rupiah(buyer_total)}\n"
        f"💵 **Penjual Terima:** {format_rupiah(seller_receive)}\n\n"
        f"👤 **Pembeli:** {'✅ Terdaftar' if buyer_id else '❌ Belum ada'}\n"
        f"👨 **Penjual:** {'✅ Terdaftar' if seller_id else '❌ Belum ada'}\n\n"
        f"📊 **Status:** {status_descriptions.get(status, status)}\n"
        f"📅 **Dibuat:** {created_at.strftime('%d/%m/%Y %H:%M')}\n\n"
    )
    
    # Add role-specific information
    if user_role == "BUYER":
        status_text += f"🔄 **Peran Anda:** Pembeli\n"
    elif user_role == "SELLER":
        status_text += f"🔄 **Peran Anda:** Penjual\n"
    else:
        status_text += f"👀 **Anda bukan bagian dari transaksi ini**\n"
    
    # Dynamic buttons based on status and role
    keyboard = []
    
    if status == "PENDING_FUNDING" and user_role == "BUYER":
        keyboard.append([InlineKeyboardButton("💰 Lanjut Pembayaran", callback_data=f"start_payment|{deal_id}")])
    
    if status in ["FUNDED", "AWAITING_CONFIRM"] and user_role == "SELLER":
        from db_postgres import get_payout_info
        payout = get_payout_info(deal_id)
        if not payout:
            keyboard.append([InlineKeyboardButton("💳 Isi Data Pencairan", callback_data=f"payout_start|{deal_id}")])
    
    keyboard.append([InlineKeyboardButton("🔄 Refresh Status", callback_data=f"rekber_status|{deal_id}")])
    keyboard.append([InlineKeyboardButton("🏠 Menu Utama", callback_data="rekber_main_menu")])
    
    await query.edit_message_text(
        status_text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
