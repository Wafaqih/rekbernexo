import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CommandHandler, CallbackQueryHandler, filters
from utils import generate_deal_id, format_rupiah, calculate_admin_fee
from db_sqlite import get_connection, return_connection, log_action, save_payout_info, get_payout_info, check_rate_limit, update_user_activity
from config import BOT_USERNAME, ADMIN_ID
from datetime import datetime
import random
from telegram.helpers import escape_markdown
import html
import config

ASK_TITLE, ASK_AMOUNT, ASK_FEE_PAYER, ASK_CONFIRMATION = range(4)
ASK_GROUP_LINK = range(4, 5)
# Setup logging for debugging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def is_chat_accessible(context, chat_id):
    """Check if bot can access the chat"""
    try:
        await context.bot.get_chat(chat_id)
        return True
    except Exception as e:
        logger.error(f"Cannot access chat {chat_id}: {e}")
        return False

def debug_transaction_state(deal_id: str, action: str, user_id: int):
    """Helper function to debug transaction states"""
    from db_sqlite import get_connection
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, title, status, buyer_id, seller_id FROM deals WHERE id = ?", (deal_id,))
        row = cur.fetchone()
        if row:
            logger.info(f"🔍 Transaction Debug - Action: {action}, Deal: {deal_id}, Status: {row['status']}, Buyer: {row['buyer_id']}, Seller: {row['seller_id']}, Current User: {user_id}")
        else:
            logger.warning(f"⚠️ Transaction Debug - Action: {action}, Deal: {deal_id} NOT FOUND, User: {user_id}")
    except Exception as e:
        logger.error(f"❌ Error in debug_transaction_state: {e}")
    finally:
        conn.close()





# --- Pilih Role Penjual ---
async def rekber_create_role_seller(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["role"] = "SELLER"

    title_instruction = (
        "📝 **LANGKAH 1/3: JUDUL TRANSAKSI**\n\n"
        "Tulis judul yang jelas dan detail untuk barang/jasa yang akan Anda jual:\n\n"
        "✅ **Contoh yang baik:**\n"
        "• Akun Mobile Legends 1000 Diamond + Skin Epic\n"
        "• Jasa Design Logo + 3 Revisi\n"
        "• iPhone 13 Pro 128GB Fullset\n\n"
        "❌ **Hindari judul seperti:**\n"
        "• Akun game (terlalu umum)\n"
        "• Jasa design (tidak spesifik)\n\n"
        "💡 *Tips: Judul yang detail menghindari kesalahpahaman*"
    )

    await query.edit_message_text(
        title_instruction,
        parse_mode="Markdown"
    )
    return ASK_TITLE

# --- Pilih Role Pembeli ---
async def rekber_create_role_buyer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["role"] = "BUYER"

    title_instruction = (
        "📝 **LANGKAH 1/3: JUDUL TRANSAKSI**\n\n"
        "Tulis judul yang jelas untuk barang/jasa yang ingin Anda beli:\n\n"
        "✅ **Contoh yang baik:**\n"
        "• Jasa Pembuatan Website E-commerce\n"
        "• Laptop Gaming ROG Strix Series\n"
        "• Akun Netflix Premium 1 Tahun\n\n"
        "❌ **Hindari judul seperti:**\n"
        "• Jasa website (tidak detail)\n"
        "• Laptop bekas (terlalu umum)\n\n"
        "💡 *Tips: Semakin spesifik, semakin mudah untuk seller memahami kebutuhan Anda*"
    )

    await query.edit_message_text(
        title_instruction,
        parse_mode="Markdown"
    )
    return ASK_TITLE

# --- Step 1: Input Judul ---
async def rekber_create_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    title = update.message.text.strip()

    # Validasi judul
    if len(title) < 10:
        await update.message.reply_text(
            "❌ **Judul terlalu pendek!**\n\n"
            "Minimum 10 karakter agar transaksi jelas.\n"
            "Contoh: *iPhone 13 Pro 128GB*\n\n"
            "Silakan tulis ulang judul yang lebih detail:",
            parse_mode="Markdown"
        )
        return ASK_TITLE

    if len(title) > 100:
        await update.message.reply_text(
            "❌ **Judul terlalu panjang!**\n\n"
            "Maximum 100 karakter. Buat yang ringkas tapi jelas.\n"
            "Silakan tulis ulang judul yang lebih singkat:",
            parse_mode="Markdown"
        )
        return ASK_TITLE

    context.user_data["title"] = title

    amount_instruction = (
        "💰 **LANGKAH 2/3: NOMINAL TRANSAKSI**\n\n"
        "Masukkan harga dalam Rupiah (hanya angka):\n\n"
        "💡 **Format yang benar:**\n"
        "• `150000` (untuk Rp 150.000)\n"
        "• `1500000` (untuk Rp 1.500.000)\n"
        "• `50000` (untuk Rp 50.000)\n\n"
        "📊 **Estimasi Biaya Admin:**\n"
        "• Rp 1k-100k → Biaya Rp 2k-5k\n"
        "• Rp 100k-500k → Biaya Rp 5k\n"
        "• Rp 500k+ → Biaya 0.5-1%\n\n"
        "⚠️ *Minimum transaksi: Rp 1.000*"
    )

    await update.message.reply_text(
        amount_instruction,
        parse_mode="Markdown"
    )
    return ASK_AMOUNT

# --- Step 2: Input Nominal ---
async def rekber_create_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip().replace(",", "").replace(".", "")

    try:
        amount = int(user_input)
        if amount < 1000:
            await update.message.reply_text(
                "❌ **Nominal terlalu kecil!**\n\n"
                "Minimum transaksi adalah **Rp 1.000**\n"
                "Silakan masukkan nominal yang lebih besar:",
                parse_mode="Markdown"
            )
            return ASK_AMOUNT

        if amount > 100000000:  # 100 juta
            await update.message.reply_text(
                "❌ **Nominal terlalu besar!**\n\n"
                "Maximum transaksi adalah **Rp 100.000.000** per deal\n"
                "Untuk nominal lebih besar, silakan hubungi admin atau bagi menjadi beberapa transaksi.",
                parse_mode="Markdown"
            )
            return ASK_AMOUNT

    except ValueError:
        await update.message.reply_text(
            "❌ **Format nominal tidak valid!**\n\n"
            "Gunakan format yang benar:\n"
            "✅ `150000` (untuk Rp 150.000)\n"
            "❌ `Rp 150.000` atau `150,000`\n\n"
            "Masukkan hanya angka tanpa simbol:",
            parse_mode="Markdown"
        )
        return ASK_AMOUNT

    context.user_data["amount"] = amount

    # Hitung biaya admin dengan aturan yang diperbaiki
    admin_fee = calculate_admin_fee(amount)
    context.user_data["admin_fee"] = admin_fee
    context.user_data["total"] = amount + admin_fee

    # Preview biaya dengan tampilan yang menarik
    fee_preview = (
        "💰 **LANGKAH 3/3: PREVIEW BIAYA**\n\n"
        f"📦 **Barang/Jasa:** {context.user_data['title']}\n"
        f"💵 **Harga:** {format_rupiah(amount)}\n"
        f"💸 **Biaya Admin:** {format_rupiah(admin_fee)}\n"
        f"📊 **Total:** {format_rupiah(amount + admin_fee)}\n\n"

        "👤 **Siapa yang akan menanggung biaya admin?**\n\n"

        "🔹 **Ditanggung Pembeli:**\n"
        f"   • Pembeli transfer: {format_rupiah(amount + admin_fee)}\n"
        f"   • Penjual terima: {format_rupiah(amount)}\n\n"

        "🔹 **Ditanggung Penjual:**\n"
        f"   • Pembeli transfer: {format_rupiah(amount)}\n"
        f"   • Penjual terima: {format_rupiah(amount - admin_fee)}\n\n"

        "💡 *Tips: Umumnya biaya admin ditanggung pembeli*"
    )

    # Pilih siapa yang bayar fee
    keyboard = [
        [InlineKeyboardButton("🛒 Fee ditanggung Pembeli", callback_data="fee_payer|BUYER")],
        [InlineKeyboardButton("📦 Fee ditanggung Penjual", callback_data="fee_payer|SELLER")],
        [InlineKeyboardButton("🔄 Ubah Nominal", callback_data="change_amount"),
         InlineKeyboardButton("❌ Batalkan", callback_data="cancel_create")]
    ]

    await update.message.reply_text(
        fee_preview,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ASK_FEE_PAYER

# --- Step 2B: Ringkasan berdasarkan pilihan Fee Payer ---
async def rekber_pick_fee_payer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "change_amount":
        await query.edit_message_text(
            "💰 **UBAH NOMINAL**\n\n"
            "Masukkan nominal baru (hanya angka):",
            parse_mode="Markdown"
        )
        return ASK_AMOUNT

    if query.data == "cancel_create":
        from handlers.start import rekber_main_menu
        await rekber_main_menu(update, context)
        return ConversationHandler.END

    _, payer = query.data.split("|")
    context.user_data["admin_fee_payer"] = payer

    title = context.user_data["title"]
    amount = context.user_data["amount"]
    admin_fee = context.user_data["admin_fee"]
    role = context.user_data.get("role", "BUYER")

    if payer == "BUYER":
        buyer_pay = amount + admin_fee
        seller_receive = amount
        confirmation_text = (
            f"✅ **KONFIRMASI TRANSAKSI**\n\n"
            f"📦 **Barang/Jasa:** {title}\n"
            f"💵 **Harga:** {format_rupiah(amount)}\n"
            f"💸 **Biaya Admin:** {format_rupiah(admin_fee)} *(ditanggung pembeli)*\n\n"
            f"📊 **DETAIL PEMBAYARAN:**\n"
            f"• Pembeli transfer: **{format_rupiah(buyer_pay)}**\n"
            f"• Penjual terima: **{format_rupiah(seller_receive)}**\n\n"
            f"🔄 **Peran Anda:** {'Penjual' if role == 'SELLER' else 'Pembeli'}\n\n"
            f"⚠️ **Setelah membuat transaksi:**\n"
            f"{'• Bagikan link ke pembeli untuk join' if role == 'SELLER' else '• Bagikan link ke penjual untuk join'}\n"
            f"{'• Pembeli akan transfer dana ke admin' if role == 'SELLER' else '• Anda perlu transfer dana ke admin'}\n"
            f"{'• Kirim barang setelah dana terverifikasi' if role == 'SELLER' else '• Tunggu penjual kirim barang'}\n\n"
            f"Apakah semua sudah benar?"
        )
    else:  # SELLER
        buyer_pay = amount
        seller_receive = amount - admin_fee
        confirmation_text = (
            f"✅ **KONFIRMASI TRANSAKSI**\n\n"
            f"📦 **Barang/Jasa:** {title}\n"
            f"💵 **Harga:** {format_rupiah(amount)}\n"
            f"💸 **Biaya Admin:** {format_rupiah(admin_fee)} *(ditanggung penjual)*\n\n"
            f"📊 **DETAIL PEMBAYARAN:**\n"
            f"• Pembeli transfer: **{format_rupiah(buyer_pay)}**\n"
            f"• Penjual terima: **{format_rupiah(seller_receive)}**\n\n"
            f"🔄 **Peran Anda:** {'Penjual' if role == 'SELLER' else 'Pembeli'}\n\n"
            f"⚠️ **Setelah membuat transaksi:**\n"
            f"{'• Bagikan link ke pembeli untuk join' if role == 'SELLER' else '• Bagikan link ke penjual untuk join'}\n"
            f"{'• Pembeli akan transfer dana ke admin' if role == 'SELLER' else '• Anda perlu transfer dana ke admin'}\n"
            f"{'• Kirim barang setelah dana terverifikasi' if role == 'SELLER' else '• Tunggu penjual kirim barang'}\n\n"
            f"Apakah semua sudah benar?"
        )

    keyboard = [
        [InlineKeyboardButton("✅ Ya, Buat Transaksi", callback_data="confirm_create")],
        [InlineKeyboardButton("🔄 Ubah Biaya", callback_data="change_fee_payer"),
         InlineKeyboardButton("❌ Batalkan", callback_data="cancel_create")]
    ]

    await query.edit_message_text(
        confirmation_text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ASK_CONFIRMATION



#======= NEW REKBER SELLER =======
async def rekber_new_seller(update, context, title, amount, admin_fee):
    user_id = update.effective_user.id
    username = "@" + update.effective_user.username if update.effective_user.username else update.effective_user.first_name

    deal_id = generate_deal_id()
    total = amount + admin_fee

    # Optimized database operation dengan transaction
    try:
        conn = get_connection()
        cur = conn.cursor()
        try:
            # Insert deal dan log dalam satu transaction
            cur.execute(
                "INSERT INTO deals (id, title, amount, admin_fee, admin_fee_payer, seller_id, buyer_id, status) VALUES (?,?,?,?,?,?,?,?)",
                (
                    deal_id,
                    title,
                    amount,
                    admin_fee,
                    context.user_data.get("admin_fee_payer"),
                    user_id,
                    None,
                    "PENDING_JOIN"
                )
            )
            
            # Insert log dalam transaction yang sama
            cur.execute(
                "INSERT INTO logs (deal_id, actor_id, role, action, detail, created_at) VALUES (?,?,?,?,?,?)",
                (deal_id, user_id, "SELLER", "CREATE", f"Penjual {username} buat transaksi {title} Rp {amount:,}", datetime.now())
            )
            
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Error creating seller transaction: {e}")
            raise
        finally:
            cur.close()
            from db_sqlite import return_connection
            return_connection(conn)
    except Exception as e:
        logger.error(f"Database error in rekber_new_seller: {e}")
        error_message = (
            "❌ **MAAF, SISTEM SEDANG BERMASALAH**\n\n"
            "🔧 Database sedang dalam perbaikan dan transaksi tidak dapat dibuat saat ini.\n\n"
            "📞 **Alternatif:**\n"
            "• Hubungi admin manual: @Nexoitsme\n"
            "• Coba lagi dalam beberapa menit\n"
            "• Gunakan chat group untuk koordinasi sementara\n\n"
            "🙏 Mohon maaf atas ketidaknyamanan ini."
        )
        
        if update.callback_query:
            await update.callback_query.edit_message_text(error_message, parse_mode="Markdown")
        else:
            await update.message.reply_text(error_message, parse_mode="Markdown")
        return

    invite_link = f"https://t.me/{BOT_USERNAME}?start=rekber_{deal_id}"

    # Buat pesan yang lebih menarik dan informatif
    admin_fee_payer = context.user_data.get("admin_fee_payer", "BUYER")
    buyer_total = amount + admin_fee if admin_fee_payer == "BUYER" else amount
    seller_receive = amount if admin_fee_payer == "BUYER" else amount - admin_fee

    success_message = (
        f"🎉 **TRANSAKSI BERHASIL DIBUAT!**\n\n"
        f"📋 **ID Transaksi:** `{deal_id}`\n"
        f"📦 **Barang/Jasa:** {title}\n"
        f"💰 **Harga:** {format_rupiah(amount)}\n"
        f"💸 **Biaya Admin:** {format_rupiah(admin_fee)} *(ditanggung {'pembeli' if admin_fee_payer == 'BUYER' else 'penjual'})*\n\n"
        f"📊 **RINGKASAN PEMBAYARAN:**\n"
        f"• Pembeli transfer: **{format_rupiah(buyer_total)}**\n"
        f"• Penjual terima: **{format_rupiah(seller_receive)}**\n\n"
        f"📌 **LANGKAH SELANJUTNYA:**\n"
        f"1️⃣ Bagikan link di bawah ke **PEMBELI** untuk join\n"
        f"2️⃣ Setelah pembeli join, mereka akan transfer dana\n"
        f"3️⃣ Admin akan verifikasi pembayaran\n"
        f"4️⃣ Anda kirim barang setelah dana terverifikasi\n"
        f"5️⃣ Pembeli konfirmasi → Dana dilepas ke Anda\n\n"
        f"⏰ **Timeline:** Pembeli harus transfer dalam 24 jam"
    )

    keyboard = [
        [InlineKeyboardButton("📱 Bagikan via WhatsApp", url=f"https://wa.me/?text={invite_link}")],
        [InlineKeyboardButton("📋 Lihat Status", callback_data=f"rekber_status|{deal_id}"),
         InlineKeyboardButton("🏠 Menu Utama", callback_data="rekber_main_menu")]
    ]

    # Send success message
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(
            success_message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            success_message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # Kirim invite link secara async untuk response yang lebih cepat
    import asyncio
    
    async def send_invite_template():
        try:
            invite_template = (
                f"🔗 LINK UNDANGAN UNTUK PEMBELI:\n\n"
                f"{invite_link}\n\n"
                f"📝 Template pesan untuk pembeli:\n\n"
                f"Halo! Saya sudah buat transaksi rekber untuk:\n"
                f"📦 {title}\n"
                f"💰 {format_rupiah(buyer_total)}\n\n"
                f"Klik link ini untuk join transaksi:\n"
                f"{invite_link}\n\n"
                f"Transaksi aman dengan jaminan rekber bot! ✅"
            )

            await context.bot.send_message(
                chat_id=user_id,
                text=invite_template
            )
        except Exception as e:
            logger.error(f"Error sending invite template to seller {user_id}: {e}")
            # Fallback message tanpa format
            simple_invite = f"🔗 LINK UNDANGAN PEMBELI:\n{invite_link}\n\nBagikan link ini ke pembeli untuk bergabung!"
            await context.bot.send_message(
                chat_id=user_id,
                text=simple_invite
            )
    
    # Jalankan pengiriman template secara background
    asyncio.create_task(send_invite_template())


# Wrapper functions for callback handlers
async def rekber_new_seller_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback wrapper for rekber_new_seller - triggers conversation"""
    query = update.callback_query
    await query.answer()
    context.user_data["role"] = "SELLER"
    await query.edit_message_text("📝 Masukkan *judul* barang/jasa untuk rekber:", parse_mode="Markdown")
    return ASK_TITLE

async def rekber_new_buyer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback wrapper for rekber_new_buyer - triggers conversation"""
    query = update.callback_query
    await query.answer()
    context.user_data["role"] = "BUYER"
    await query.edit_message_text("📝 Masukkan *judul* barang/jasa untuk rekber:", parse_mode="Markdown")
    return ASK_TITLE

#============= NEW REKBER BUYER ==============
#============= NEW REKBER BUYER ==============
async def rekber_new_buyer(update, context, title, amount, admin_fee):
    user_id = update.effective_user.id
    username = "@" + update.effective_user.username if update.effective_user.username else update.effective_user.first_name

    deal_id = generate_deal_id()   # 🔥 ID unik
    total = amount + admin_fee

    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO deals (id, title, amount, admin_fee, admin_fee_payer, buyer_id, seller_id, status) VALUES (?,?,?,?,?,?,?,?)",
            (
                deal_id,
                title,
                amount,
                admin_fee,
                context.user_data.get("admin_fee_payer"),
                user_id,
                None,  # seller_id is NULL initially for buyer-created transactions
                "PENDING_JOIN"
            )
        )

        conn.commit()
        conn.close()

        log_action(deal_id, user_id, "BUYER", "CREATE", f"Pembeli {username} buat transaksi {title} Rp {amount:,}")
        
    except Exception as e:
        logger.error(f"Database error in rekber_new_buyer: {e}")
        error_message = (
            "❌ **MAAF, SISTEM SEDANG BERMASALAH**\n\n"
            "🔧 Database sedang dalam perbaikan dan transaksi tidak dapat dibuat saat ini.\n\n"
            "📞 **Alternatif:**\n"
            "• Hubungi admin manual: @Nexoitsme\n"
            "• Coba lagi dalam beberapa menit\n"
            "• Gunakan chat group untuk koordinasi sementara\n\n"
            "🙏 Mohon maaf atas ketidaknyamanan ini."
        )
        
        if update.callback_query:
            await update.callback_query.edit_message_text(error_message, parse_mode="Markdown")
        else:
            await update.message.reply_text(error_message, parse_mode="Markdown")
        return

    invite_link = f"https://t.me/{BOT_USERNAME}?start=rekber_{deal_id}"

    # Buat pesan yang konsisten dengan seller
    admin_fee_payer = context.user_data.get("admin_fee_payer", "BUYER")
    buyer_total = amount + admin_fee if admin_fee_payer == "BUYER" else amount
    seller_receive = amount if admin_fee_payer == "BUYER" else amount - admin_fee

    success_message = (
        f"🎉 **TRANSAKSI BERHASIL DIBUAT!**\n\n"
        f"📋 **ID Transaksi:** `{deal_id}`\n"
        f"📦 **Barang/Jasa:** {title}\n"
        f"💰 **Harga:** {format_rupiah(amount)}\n"
        f"💸 **Biaya Admin:** {format_rupiah(admin_fee)} *(ditanggung {'pembeli' if admin_fee_payer == 'BUYER' else 'penjual'})*\n\n"
        f"📊 **RINGKASAN PEMBAYARAN:**\n"
        f"• Pembeli transfer: **{format_rupiah(buyer_total)}**\n"
        f"• Penjual terima: **{format_rupiah(seller_receive)}**\n\n"
        f"📌 **LANGKAH SELANJUTNYA:**\n"
        f"1️⃣ Bagikan link di bawah ke **PENJUAL** untuk join\n"
        f"2️⃣ Setelah penjual join, Anda akan transfer dana\n"
        f"3️⃣ Admin akan verifikasi pembayaran Anda\n"
        f"4️⃣ Penjual kirim barang setelah dana terverifikasi\n"
        f"5️⃣ Anda konfirmasi penerimaan → Dana dilepas ke penjual\n\n"
        f"⏰ **Timeline:** Anda harus transfer dalam 24 jam setelah penjual join"
    )

    keyboard = [
        [InlineKeyboardButton("📱 Bagikan via WhatsApp", url=f"https://wa.me/?text={invite_link}")],
        [InlineKeyboardButton("📋 Lihat Status", callback_data=f"rekber_status|{deal_id}"),
         InlineKeyboardButton("🏠 Menu Utama", callback_data="rekber_main_menu")]
    ]

    if update.callback_query:
        await update.callback_query.edit_message_text(
            success_message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            success_message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # Send invite link dengan template untuk penjual yang aman
    try:
        invite_template = (
            f"🔗 LINK UNDANGAN UNTUK PENJUAL:\n\n"
            f"{invite_link}\n\n"
            f"📝 Template pesan untuk penjual:\n\n"
            f"Halo! Saya ingin membeli:\n"
            f"📦 {title}\n"
            f"💰 {format_rupiah(amount)}\n\n"
            f"Saya sudah buat transaksi rekber. Klik link ini untuk join:\n"
            f"{invite_link}\n\n"
            f"Transaksi aman dengan jaminan rekber bot! ✅"
        )

        await context.bot.send_message(
            chat_id=user_id,
            text=invite_template
        )
    except Exception as e:
        logger.error(f"Error sending invite template to buyer {user_id}: {e}")
        # Fallback message tanpa format
        simple_invite = f"🔗 LINK UNDANGAN PENJUAL:\n{invite_link}\n\nBagikan link ini ke penjual untuk bergabung!"
        await context.bot.send_message(
            chat_id=user_id,
            text=simple_invite
        )

##=== REKBER JOIN ===
async def rekber_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle join attempt dari user - bisa dari /start command atau callback query"""

    # Check if called from /start command with args
    if context.args and context.args[0].startswith("rekber_"):
        deal_id = context.args[0].replace("rekber_", "")
        user_id = update.effective_user.id
        username = update.effective_user.username or update.effective_user.first_name

        logger.info(f"🔍 Transaction Debug - Action: JOIN_ATTEMPT, Deal: {deal_id}, Current User: {user_id}")

        # Get transaction details
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT id, title, amount, buyer_id, seller_id, status FROM deals WHERE id = ?", (deal_id,))
            row = cur.fetchone()
            conn.close()
        except Exception as e:
            logger.error(f"Database error in rekber_join: {e}")
            await update.message.reply_text(
                "❌ **SISTEM BERMASALAH**\n\n"
                "Database tidak tersedia. Hubungi admin @Nexoitsme atau coba lagi nanti.",
                parse_mode="Markdown"
            )
            return

        if not row:
            await update.message.reply_text("❌ Transaksi tidak ditemukan.")
            return

        title = row['title']
        amount = int(row['amount']) if row['amount'] else 0
        buyer_id = row['buyer_id']
        seller_id = row['seller_id']
        status = row['status']

        # ⛔ Cek: jangan biarkan pembuat join sendiri
        if user_id == buyer_id or user_id == seller_id:
            await update.message.reply_text("⚠️ Kamu tidak bisa join transaksi yang kamu buat sendiri, bagikan link ini ke lawan transaksimu!")
            return

        # ⛔ SECURITY: Cek apakah user sudah pernah join transaksi ini sebagai joined_by
        # Mencegah double-joining vulnerability
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT joined_by FROM deals WHERE id = ? AND joined_by = ?", (deal_id, user_id))
            already_joined = cur.fetchone()
            conn.close()
            
            if already_joined:
                await update.message.reply_text("❌ Anda sudah pernah mencoba bergabung dalam transaksi ini. Setiap user hanya bisa join sekali.")
                return
        except Exception as e:
            logger.error(f"Error checking joined_by: {e}")

        # Check if transaction is still open for joining
        if status != "PENDING_JOIN":
            if status in ["PENDING_FUNDING", "FUNDED", "AWAITING_CONFIRM"]:
                await update.message.reply_text("⚠️ Transaksi ini sudah berjalan, kedua pihak sudah bergabung.")
            elif status in ["RELEASED", "COMPLETED", "CANCELLED", "DISPUTED"]:
                await update.message.reply_text("⚠️ Transaksi ini sudah selesai atau dibatalkan.")
            else:
                await update.message.reply_text(f"⚠️ Status transaksi: {status}. Tidak bisa bergabung saat ini.")
            return

        # Tentukan role berdasarkan siapa yang kosong
        role = None
        role_indo = ""

        if buyer_id is None:
            role = "BUYER"
            role_indo = "Pembeli"
        elif seller_id is None:
            role = "SELLER"
            role_indo = "Penjual"
        else:
            await update.message.reply_text("⚠️ Transaksi ini sudah lengkap (pembeli & penjual sudah ada).")
            return

        # Tampilkan detail yang lebih informatif
        join_message = (
            f"🤝 **UNDANGAN JOIN TRANSAKSI**\n\n"
            f"📋 **ID:** `{deal_id}`\n"
            f"📦 **Barang/Jasa:** {title}\n"
            f"💰 **Nilai:** {format_rupiah(amount)}\n\n"
            f"🔄 **Anda akan bergabung sebagai:** **{role_indo}**\n\n"
            f"📌 **Tanggung jawab {role_indo}:**\n"
        )

        if role == "BUYER":
            join_message += (
                f"• Transfer dana ke admin untuk keamanan\n"
                f"• Tunggu penjual kirim barang/jasa\n"
                f"• Konfirmasi penerimaan jika sesuai\n"
                f"• Dana akan dilepas ke penjual setelah konfirmasi\n\n"
            )
        else:  # SELLER
            join_message += (
                f"• Tunggu pembeli transfer dana ke admin\n"
                f"• Kirim barang/jasa setelah dana terverifikasi\n"
                f"• Upload bukti pengiriman jika diperlukan\n"
                f"• Terima dana setelah pembeli konfirmasi\n\n"
            )

        join_message += (
            f"✅ **Keuntungan rekber:**\n"
            f"• Dana aman di tangan admin\n"
            f"• Dispute resolution jika ada masalah\n"
            f"• Transparansi penuh proses transaksi\n\n"
            f"⚠️ **Dengan bergabung, Anda menyetujui syarat & ketentuan rekber**"
        )

        keyboard = [
            [InlineKeyboardButton(f"✅ Setuju & Join sebagai {role_indo}", callback_data=f"rekber_join_confirm|{deal_id}|{role}")],
            [InlineKeyboardButton("❓ Apa itu Rekber?", callback_data="help_what_is_rekber"),
             InlineKeyboardButton("❌ Tidak Jadi", callback_data="join_cancel")]
        ]

        await update.message.reply_text(
            join_message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Handle callback query case
    query = update.callback_query
    if query:
        await query.answer()

        if not query.data or not query.data.startswith("rekber_join_"):
            await query.edit_message_text("❌ ID Rekber tidak valid.")
            return

        deal_id = query.data.split("|")[1]
        await rekber_join_confirm(update, context)
    else:
        await update.message.reply_text("❌ Terjadi kesalahan dalam memproses permintaan join.")

async def rekber_join_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User konfirmasi bergabung ke transaksi"""
    query = update.callback_query
    await query.answer()

    # Extract deal_id and role from callback data
    if not query.data or not query.data.startswith("rekber_join_confirm|"):
        await query.edit_message_text("❌ Data tidak valid untuk konfirmasi bergabung.")
        return ConversationHandler.END

    parts = query.data.split("|")
    if len(parts) < 3:
        await query.edit_message_text("❌ Format data tidak lengkap.")
        return ConversationHandler.END

    deal_id = parts[1]
    role = parts[2]
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name

    logger.debug(f"Processing join confirmation - Deal: {deal_id}, Role: {role}, User: {user_id}")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, title, amount, admin_fee, admin_fee_payer, buyer_id, seller_id, status "
        "FROM deals WHERE id = ?",
        (deal_id,)
    )
    row = cur.fetchone()

    if not row:
        await query.edit_message_text("❌ Transaksi tidak ditemukan.")
        conn.close()
        return ConversationHandler.END

    title = row['title']
    amount = int(row['amount'])  # Convert to integer
    admin_fee = int(row['admin_fee'])  # Convert to integer
    admin_fee_payer = row['admin_fee_payer']
    buyer_id = row['buyer_id']
    seller_id = row['seller_id']
    status = row['status']

    # Validate that transaction can still accept joins
    if status not in ["PENDING_JOIN"]:
        await query.edit_message_text("❌ Transaksi ini tidak bisa diikuti lagi.")
        conn.close()
        return ConversationHandler.END

    # Validate user is not already in this transaction
    if user_id == buyer_id or user_id == seller_id:
        await query.edit_message_text("❌ Anda sudah terdaftar dalam transaksi ini.")
        conn.close()
        return ConversationHandler.END

    # Update database with the new participant
    updated_buyer_id = buyer_id
    updated_seller_id = seller_id

    if role == "BUYER":
        cur.execute("UPDATE deals SET buyer_id = ?, joined_by = ? WHERE id = ?", (user_id, user_id, deal_id))
        updated_buyer_id = user_id
        logger.debug(f"Updated buyer_id to {user_id} for deal {deal_id}")
    elif role == "SELLER":
        cur.execute("UPDATE deals SET seller_id = ?, joined_by = ? WHERE id = ?", (user_id, user_id, deal_id))
        updated_seller_id = user_id
        logger.debug(f"Updated seller_id to {user_id} for deal {deal_id}")
    else:
        await query.edit_message_text("❌ Peran tidak valid.")
        conn.close()
        return ConversationHandler.END

    conn.commit()

    # Re-fetch to ensure correct IDs are used
    cur.execute("SELECT buyer_id, seller_id FROM deals WHERE id = ?", (deal_id,))
    verification_row = cur.fetchone()
    if verification_row:
        updated_buyer_id = verification_row['buyer_id']
        updated_seller_id = verification_row['seller_id']
    else:
        logger.error(f"Failed to re-fetch deal details after update for {deal_id}")
        conn.close()
        return ConversationHandler.END

    # Check if both roles are now filled and update status
    if updated_buyer_id and updated_seller_id:
        cur.execute("UPDATE deals SET status = ? WHERE id = ?", ("PENDING_FUNDING", deal_id))
        conn.commit()

        logger.debug(f"Transaction {deal_id} complete - Buyer: {updated_buyer_id}, Seller: {updated_seller_id}, Status: PENDING_FUNDING")

        buyer_total = amount + admin_fee if admin_fee_payer == "BUYER" else amount
        seller_receive = amount if admin_fee_payer == "BUYER" else amount - admin_fee

        role_indo = "Penjual" if role == "SELLER" else "Pembeli"
        await query.edit_message_text(
            f"✅ **BERHASIL BERGABUNG!**\n\n"
            f"Anda telah bergabung sebagai **{role_indo}** untuk transaksi `{deal_id}`\n\n"
            f"📦 **Produk:** {title}\n"
            f"💰 **Nilai:** {format_rupiah(amount)}\n\n"
            f"Transaksi sekarang **LENGKAP** dan siap dimulai!",
            parse_mode="Markdown"
        )

        # Send detailed instructions to buyer
        buyer_confirmation = (
            f"🎉 **TRANSAKSI SIAP DIMULAI!**\n\n"
            f"📋 **ID:** `{deal_id}`\n"
            f"📦 **Barang/Jasa:** {title}\n"
            f"💰 **Harga:** {format_rupiah(amount)}\n"
            f"💸 **Biaya Admin:** {format_rupiah(admin_fee)} *(ditanggung {'Anda' if admin_fee_payer == 'BUYER' else 'penjual'})*\n"
            f"📊 **Total Anda Transfer:** **{format_rupiah(buyer_total)}**\n\n"
            f"👥 **Kedua pihak sudah bergabung!**\n\n"
            f"📌 **LANGKAH SELANJUTNYA:**\n"
            f"1️⃣ Transfer dana ke rekening admin\n"
            f"2️⃣ Konfirmasi pembayaran\n"
            f"3️⃣ Tunggu penjual kirim barang\n"
            f"4️⃣ Konfirmasi penerimaan\n"
            f"5️⃣ Dana dilepas ke penjual\n\n"
            f"⏰ **Batas waktu transfer:** 24 jam"
        )

        keyboard_buyer = [
            [InlineKeyboardButton("💰 Lanjut ke Pembayaran", callback_data=f"start_payment|{deal_id}")],
            [InlineKeyboardButton("📋 Lihat Status", callback_data=f"rekber_status|{deal_id}"),
             InlineKeyboardButton("❌ Batalkan", callback_data=f"rekber_funding_cancel|{deal_id}")]
        ]

        # Send instructions to seller
        seller_confirmation = (
            f"🎉 **TRANSAKSI SIAP DIMULAI!**\n\n"
            f"📋 **ID:** `{deal_id}`\n"
            f"📦 **Barang/Jasa:** {title}\n"
            f"💰 **Harga:** {format_rupiah(amount)}\n"
            f"💸 **Biaya Admin:** {format_rupiah(admin_fee)} *(ditanggung {'pembeli' if admin_fee_payer == 'BUYER' else 'Anda'})*\n"
            f"📊 **Anda Terima:** **{format_rupiah(seller_receive)}**\n\n"
            f"👥 **Kedua pihak sudah bergabung!**\n\n"
            f"📌 **LANGKAH SELANJUTNYA:**\n"
            f"1️⃣ Tunggu pembeli transfer dana\n"
            f"2️⃣ Admin verifikasi pembayaran\n"
            f"3️⃣ Anda kirim barang/jasa\n"
            f"4️⃣ Pembeli konfirmasi penerimaan\n"
            f"5️⃣ Dana dilepas ke Anda\n\n"
            f"📱 **Siap-siap kirim barang setelah dana terverifikasi!**"
        )

        keyboard_seller = [
            [InlineKeyboardButton("📋 Lihat Status", callback_data=f"rekber_status|{deal_id}")]
        ]

        # Send messages to both parties
        try:
            await context.bot.send_message(
                chat_id=updated_buyer_id,
                text=buyer_confirmation,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard_buyer)
            )
            logger.debug(f"Successfully sent payment instructions to buyer {updated_buyer_id}")
        except Exception as e:
            logger.error(f"Failed to send message to buyer {updated_buyer_id}: {e}")

        try:
            await context.bot.send_message(
                chat_id=updated_seller_id,
                text=seller_confirmation,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard_seller)
            )
            logger.debug(f"Successfully sent instructions to seller {updated_seller_id}")
        except Exception as e:
            logger.error(f"Failed to send message to seller {updated_seller_id}: {e}")

        # Notify admin
        admin_notif = (
            f"📢 <b>Transaksi Rekber Lengkap</b>\n\n"
            f"🏷️ ID: <code>{deal_id}</code>\n"
            f"📝 Judul: {title}\n"
            f"💰 Nominal: Rp {amount:,}\n"
            f"💸 Biaya Admin: Rp {admin_fee:,} (ditanggung {admin_fee_payer})\n"
            f"💵 Total Transfer Pembeli: Rp {buyer_total:,}\n\n"
            f"👤 Pembeli ID: {updated_buyer_id}\n"
            f"👨 Penjual ID: {updated_seller_id}\n\n"
            f"📦 Status: <b>PENDING_FUNDING</b>\n"
            f"⏳ Menunggu pembeli melakukan pembayaran..."
        )

        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_notif,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Gagal kirim notif admin: {e}")

        # Log the successful completion
        log_action(deal_id, user_id, role, "JOIN_COMPLETE", f"{role_indo} {username} bergabung - transaksi lengkap dan siap funding")

    else:
        # Only one party has joined so far
        role_indo = "Penjual" if role == "SELLER" else "Pembeli"
        await query.edit_message_text(
            f"✅ **BERHASIL BERGABUNG!**\n\n"
            f"Anda berhasil bergabung sebagai **{role_indo}** untuk transaksi `{deal_id}`\n\n"
            f"⏳ Menunggu {'penjual' if role == 'BUYER' else 'pembeli'} untuk bergabung...\n\n"
            f"📱 Bagikan link undangan untuk mempercepat proses!"
        )
        log_action(deal_id, user_id, role, "JOIN", f"{role_indo} {username} bergabung - menunggu pihak lain")

    conn.close()
    return ConversationHandler.END



## JOIN CONFIRM
async def rekber_join_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User konfirmasi bergabung ke transaksi"""
    query = update.callback_query
    await query.answer()

    # Extract deal_id and role from callback data
    if not query.data or not query.data.startswith("rekber_join_confirm|"):
        await query.edit_message_text("❌ Data tidak valid untuk konfirmasi bergabung.")
        return ConversationHandler.END

    parts = query.data.split("|")
    if len(parts) < 3:
        await query.edit_message_text("❌ Format data tidak lengkap.")
        return ConversationHandler.END

    deal_id = parts[1]
    role = parts[2]
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name

    logger.debug(f"Processing join confirmation - Deal: {deal_id}, Role: {role}, User: {user_id}")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, title, amount, admin_fee, admin_fee_payer, buyer_id, seller_id, status "
        "FROM deals WHERE id = ?",
        (deal_id,)
    )
    row = cur.fetchone()

    if not row:
        await query.edit_message_text("❌ Transaksi tidak ditemukan.")
        conn.close()
        return ConversationHandler.END

    title = row['title']
    amount = int(row['amount'])  # Convert to integer
    admin_fee = int(row['admin_fee'])  # Convert to integer
    admin_fee_payer = row['admin_fee_payer']
    buyer_id = row['buyer_id']
    seller_id = row['seller_id']
    status = row['status']

    # Validate that transaction can still accept joins
    if status not in ["PENDING_JOIN"]:
        await query.edit_message_text("❌ Transaksi ini tidak bisa diikuti lagi.")
        conn.close()
        return ConversationHandler.END

    # Validate user is not already in this transaction
    if user_id == buyer_id or user_id == seller_id:
        await query.edit_message_text("❌ Anda sudah terdaftar dalam transaksi ini.")
        conn.close()
        return ConversationHandler.END

    # Update database with the new participant
    updated_buyer_id = buyer_id
    updated_seller_id = seller_id

    if role == "BUYER":
        cur.execute("UPDATE deals SET buyer_id = ?, joined_by = ? WHERE id = ?", (user_id, user_id, deal_id))
        updated_buyer_id = user_id
        logger.debug(f"Updated buyer_id to {user_id} for deal {deal_id}")
    elif role == "SELLER":
        cur.execute("UPDATE deals SET seller_id = ?, joined_by = ? WHERE id = ?", (user_id, user_id, deal_id))
        updated_seller_id = user_id
        logger.debug(f"Updated seller_id to {user_id} for deal {deal_id}")
    else:
        await query.edit_message_text("❌ Peran tidak valid.")
        conn.close()
        return ConversationHandler.END

    conn.commit()

    # Re-fetch to ensure correct IDs are used
    cur.execute("SELECT buyer_id, seller_id FROM deals WHERE id = ?", (deal_id,))
    verification_row = cur.fetchone()
    if verification_row:
        updated_buyer_id = verification_row['buyer_id']
        updated_seller_id = verification_row['seller_id']
    else:
        logger.error(f"Failed to re-fetch deal details after update for {deal_id}")
        conn.close()
        return ConversationHandler.END

    # Check if both roles are now filled and update status
    if updated_buyer_id and updated_seller_id:
        cur.execute("UPDATE deals SET status = ? WHERE id = ?", ("PENDING_FUNDING", deal_id))
        conn.commit()

        logger.debug(f"Transaction {deal_id} complete - Buyer: {updated_buyer_id}, Seller: {updated_seller_id}, Status: PENDING_FUNDING")

        buyer_total = amount + admin_fee if admin_fee_payer == "BUYER" else amount
        seller_receive = amount if admin_fee_payer == "BUYER" else amount - admin_fee

        role_indo = "Penjual" if role == "SELLER" else "Pembeli"
        await query.edit_message_text(
            f"✅ **BERHASIL BERGABUNG!**\n\n"
            f"Anda telah bergabung sebagai **{role_indo}** untuk transaksi `{deal_id}`\n\n"
            f"📦 **Produk:** {title}\n"
            f"💰 **Nilai:** {format_rupiah(amount)}\n\n"
            f"Transaksi sekarang **LENGKAP** dan siap dimulai!",
            parse_mode="Markdown"
        )

        # Send detailed instructions to buyer
        buyer_confirmation = (
            f"🎉 **TRANSAKSI SIAP DIMULAI!**\n\n"
            f"📋 **ID:** `{deal_id}`\n"
            f"📦 **Barang/Jasa:** {title}\n"
            f"💰 **Harga:** {format_rupiah(amount)}\n"
            f"💸 **Biaya Admin:** {format_rupiah(admin_fee)} *(ditanggung {'Anda' if admin_fee_payer == 'BUYER' else 'penjual'})*\n"
            f"📊 **Total Anda Transfer:** **{format_rupiah(buyer_total)}**\n\n"
            f"👥 **Kedua pihak sudah bergabung!**\n\n"
            f"📌 **LANGKAH SELANJUTNYA:**\n"
            f"1️⃣ Transfer dana ke rekening admin\n"
            f"2️⃣ Konfirmasi pembayaran\n"
            f"3️⃣ Tunggu penjual kirim barang\n"
            f"4️⃣ Konfirmasi penerimaan\n"
            f"5️⃣ Dana dilepas ke penjual\n\n"
            f"⏰ **Batas waktu transfer:** 24 jam"
        )

        keyboard_buyer = [
            [InlineKeyboardButton("💰 Lanjut ke Pembayaran", callback_data=f"start_payment|{deal_id}")],
            [InlineKeyboardButton("📋 Lihat Status", callback_data=f"rekber_status|{deal_id}"),
             InlineKeyboardButton("❌ Batalkan", callback_data=f"rekber_funding_cancel|{deal_id}")]
        ]

        # Send instructions to seller
        seller_confirmation = (
            f"🎉 **TRANSAKSI SIAP DIMULAI!**\n\n"
            f"📋 **ID:** `{deal_id}`\n"
            f"📦 **Barang/Jasa:** {title}\n"
            f"💰 **Harga:** {format_rupiah(amount)}\n"
            f"💸 **Biaya Admin:** {format_rupiah(admin_fee)} *(ditanggung {'pembeli' if admin_fee_payer == 'BUYER' else 'Anda'})*\n"
            f"📊 **Anda Terima:** **{format_rupiah(seller_receive)}**\n\n"
            f"👥 **Kedua pihak sudah bergabung!**\n\n"
            f"📌 **LANGKAH SELANJUTNYA:**\n"
            f"1️⃣ Tunggu pembeli transfer dana\n"
            f"2️⃣ Admin verifikasi pembayaran\n"
            f"3️⃣ Anda kirim barang/jasa\n"
            f"4️⃣ Pembeli konfirmasi penerimaan\n"
            f"5️⃣ Dana dilepas ke Anda\n\n"
            f"📱 **Siap-siap kirim barang setelah dana terverifikasi!**"
        )

        keyboard_seller = [
            [InlineKeyboardButton("📋 Lihat Status", callback_data=f"rekber_status|{deal_id}")]
        ]

        # Send messages to both parties
        try:
            await context.bot.send_message(
                chat_id=updated_buyer_id,
                text=buyer_confirmation,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard_buyer)
            )
            logger.debug(f"Successfully sent payment instructions to buyer {updated_buyer_id}")
        except Exception as e:
            logger.error(f"Failed to send message to buyer {updated_buyer_id}: {e}")

        try:
            await context.bot.send_message(
                chat_id=updated_seller_id,
                text=seller_confirmation,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard_seller)
            )
            logger.debug(f"Successfully sent instructions to seller {updated_seller_id}")
        except Exception as e:
            logger.error(f"Failed to send message to seller {updated_seller_id}: {e}")

        # Notify admin
        admin_notif = (
            f"📢 <b>Transaksi Rekber Lengkap</b>\n\n"
            f"🏷️ ID: <code>{deal_id}</code>\n"
            f"📝 Judul: {title}\n"
            f"💰 Nominal: Rp {amount:,}\n"
            f"💸 Biaya Admin: Rp {admin_fee:,} (ditanggung {admin_fee_payer})\n"
            f"💵 Total Transfer Pembeli: Rp {buyer_total:,}\n\n"
            f"👤 Pembeli ID: {updated_buyer_id}\n"
            f"👨 Penjual ID: {updated_seller_id}\n\n"
            f"📦 Status: <b>PENDING_FUNDING</b>\n"
            f"⏳ Menunggu pembeli melakukan pembayaran..."
        )

        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_notif,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Gagal kirim notif admin: {e}")

        # Log the successful completion
        log_action(deal_id, user_id, role, "JOIN_COMPLETE", f"{role_indo} {username} bergabung - transaksi lengkap dan siap funding")

    else:
        # Only one party has joined so far
        role_indo = "Penjual" if role == "SELLER" else "Pembeli"
        await query.edit_message_text(
            f"✅ **BERHASIL BERGABUNG!**\n\n"
            f"Anda berhasil bergabung sebagai **{role_indo}** untuk transaksi `{deal_id}`\n\n"
            f"⏳ Menunggu {'penjual' if role == 'BUYER' else 'pembeli'} untuk bergabung...\n\n"
            f"📱 Bagikan link undangan untuk mempercepat proses!"
        )
        log_action(deal_id, user_id, role, "JOIN", f"{role_indo} {username} bergabung - menunggu pihak lain")

    conn.close()
    return ConversationHandler.END



# Handler untuk tombol "Lanjut ke Pembayaran"
async def start_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    deal_id = query.data.split("|")[1]
    user_id = query.from_user.id

    # Fetch complete transaction data
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT title, amount, buyer_id, status FROM deals WHERE id = ?", (deal_id,))
        row = cur.fetchone()
        conn.close()
    except Exception as e:
        logger.error(f"Database error in start_payment_handler: {e}")
        await query.edit_message_text(
            "❌ **SISTEM BERMASALAH**\n\n"
            "Database tidak tersedia. Hubungi admin @Nexoitsme atau coba lagi nanti.",
            parse_mode="Markdown"
        )
        return

    if not row:
        await query.edit_message_text("❌ Transaksi tidak ditemukan.")
        return

    title = row['title']
    amount = int(row['amount']) if row['amount'] else 0
    buyer_id = row['buyer_id']
    status = row['status']

    # Validate that user is the buyer
    if user_id != buyer_id:
        await query.edit_message_text("❌ Hanya pembeli yang dapat melakukan pembayaran.")
        return

    # Validate transaction status
    if status != "PENDING_FUNDING":
        await query.edit_message_text("⚠️ Transaksi tidak dalam tahap pembayaran.")
        return

    await rekber_funding_menu(context, user_id, deal_id, title, amount)
    await query.edit_message_text("📝 Instruksi pembayaran telah dikirim di pesan terpisah.")

# --- STEP 3: BUYER FUNDING ---
async def rekber_funding_menu(context: ContextTypes.DEFAULT_TYPE, user_id: int, deal_id: str, title: str, amount: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT buyer_id, seller_id, admin_fee, admin_fee_payer FROM deals WHERE id = ?",
        (deal_id,)
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        return

    # Properly unpack the row data
    buyer_id = row['buyer_id']
    seller_id = row['seller_id']
    admin_fee = row['admin_fee']
    admin_fee_payer = row['admin_fee_payer']

    # Ensure admin_fee is integer with proper validation
    try:
        admin_fee = int(admin_fee) if admin_fee is not None else 0
    except (ValueError, TypeError):
        admin_fee = 0
        logger.error(f"Invalid admin_fee value in deal {deal_id}: {admin_fee}")
        # Recalculate admin fee if invalid
        from utils import calculate_admin_fee
        admin_fee = calculate_admin_fee(amount)

    # --- Keyboard & metode pembayaran (untuk Buyer) ---
    keyboard_buyer = [
        [InlineKeyboardButton("💰 Saya Sudah Transfer", callback_data=f"rekber_fund_confirm|{deal_id}")],
        [InlineKeyboardButton("❌ Batalkan", callback_data=f"rekber_funding_cancel|{deal_id}")]
    ]

    # Hitung total yang harus dibayar
    if admin_fee_payer == "BUYER":
        total_to_pay = amount + admin_fee
        fee_note = f"💸 **Biaya Admin:** {format_rupiah(admin_fee)} *(ditanggung Anda)*"
    else:
        total_to_pay = amount
        fee_note = f"💸 **Biaya Admin:** {format_rupiah(admin_fee)} *(ditanggung penjual)*"

    payment_instruction = (
        f"💰 **INSTRUKSI PEMBAYARAN**\n\n"
        f"📦 **Transaksi:** {title}\n"
        f"💵 **Harga Barang:** {format_rupiah(amount)}\n"
        f"{fee_note}\n"
        f"📊 **TOTAL TRANSFER:** **{format_rupiah(total_to_pay)}**\n\n"

        f"🏦 **PILIHAN REKENING ADMIN:**\n\n"

        f"💳 **DANA**\n"
        f"📱 `082119299186`\n"
        f"📝 Muhammad Abdu Wafaqih\n\n"

        f"🔵 **GoPay**\n"
        f"📱 `082119299186`\n"
        f"📝 Wafaqih\n\n"

        f"🏦 **SeaBank**\n"
        f"💳 `901251081230`\n"
        f"📝 Muhammad Abdu Wafaqih\n\n"

        f"🏦 **Bank Jago**\n"
        f"💳 `103536428831`\n"
        f"📝 Muhammad Abdu Wafaqih\n\n"

        f"⚠️ **PENTING:**\n"
        f"• Transfer **TEPAT** sejumlah {format_rupiah(total_to_pay)}\n"
        f"• Jangan tambah atau kurang 1 rupiah pun\n"
        f"• Setelah transfer, segera konfirmasi dengan tombol di bawah\n"
        f"• Sertakan screenshot bukti transfer\n\n"

        f"⏰ **Batas waktu:** 24 jam dari sekarang\n"
        f"📞 **Bantuan:** @Nexoitsme\n\n"

        f"🔐 **Dana Anda aman** di rekening admin hingga transaksi selesai!"
    )

    keyboard_buyer = [
        [InlineKeyboardButton("✅ Saya Sudah Transfer", callback_data=f"rekber_fund_confirm|{deal_id}")],
        [InlineKeyboardButton("📋 Lihat Status", callback_data=f"rekber_status|{deal_id}"),
         InlineKeyboardButton("❓ Bantuan", callback_data="help_payment")],
        [InlineKeyboardButton("❌ Batalkan Transaksi", callback_data=f"rekber_funding_cancel|{deal_id}")]
    ]

    await context.bot.send_message(
        chat_id=user_id,
        text=payment_instruction,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard_buyer)
    )

    # Jika fee ditanggung seller, kirim instruksi terpisah ke seller
    if admin_fee_payer == "SELLER":
        seller_payment_instruction = (
            f"💸 **PEMBAYARAN BIAYA ADMIN**\n\n"
            f"📦 **Transaksi:** {title}\n"
            f"💰 **Biaya Admin:** {format_rupiah(admin_fee)}\n\n"
            f"Sebagai penjual, Anda perlu membayar biaya admin terlebih dahulu.\n\n"
            f"🏦 **Transfer ke rekening admin yang sama:**\n"
            f"💳 DANA: `082119299186`\n"
            f"🏦 SeaBank: `901251081230`\n"
            f"📝 A/n Muhammad Abdu Wafaqih\n\n"
            f"⚠️ Transfer tepat: **{format_rupiah(admin_fee)}**\n"
            f"📞 Konfirmasi ke: @Nexoitsme"
        )

        keyboard_seller = [[InlineKeyboardButton("✅ Sudah Transfer Biaya Admin", callback_data=f"seller_fee_confirm|{deal_id}")]]

        await context.bot.send_message(
            chat_id=seller_id,
            text=seller_payment_instruction,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard_seller)
        )

#============= BUYER FUND CONFIRM ==============
async def rekber_fund_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buyer klik 'Saya Sudah Transfer'"""
    query = update.callback_query
    await query.answer()

    deal_id = query.data.split("|")[1]
    user_id = query.from_user.id

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT buyer_id, seller_id, status, title, amount, admin_fee, admin_fee_payer FROM deals WHERE id=?", (deal_id,))
        row = cur.fetchone()

        if not row:
            await query.edit_message_text("❌ Transaksi tidak ditemukan.")
            return

        buyer_id = row['buyer_id']
        seller_id = row['seller_id']
        status = row['status']
        title = row['title']
        amount = int(row['amount'])  # Convert to integer
        admin_fee = int(row['admin_fee'])  # Convert to integer
        admin_fee_payer = row['admin_fee_payer']

        if user_id != buyer_id:
            await query.edit_message_text("❌ Hanya pembeli yang bisa melakukan pendanaan.")
            return

        if status != "PENDING_FUNDING":
            await query.edit_message_text("⚠️ Transaksi tidak dalam tahap pendanaan.")
            return

        # Update status transaksi ke WAITING_PAYMENT_PROOF
        cur.execute("UPDATE deals SET status='WAITING_PAYMENT_PROOF' WHERE id=?", (deal_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error in rekber_fund_confirm: {e}")
        await query.edit_message_text("❌ Terjadi kesalahan saat konfirmasi pembayaran.")
        return
    finally:
        cur.close()
        from db_sqlite import return_connection
        return_connection(conn)

    # Minta user upload bukti pembayaran
    proof_message = (
        "📸 **UPLOAD BUKTI PEMBAYARAN**\n\n"
        "Untuk keamanan transaksi, silakan upload foto/screenshot bukti transfer Anda:\n\n"
        "✅ **Yang perlu difoto:**\n"
        "• Screenshot bukti transfer dari aplikasi bank/e-wallet\n"
        "• Terlihat jelas nominal, waktu, dan tujuan transfer\n"
        "• Pastikan foto tidak blur atau terpotong\n\n"
        "⚠️ **Penting:** Admin akan verifikasi bukti ini sebelum melanjutkan transaksi."
    )
    
    # Simpan context untuk handler berikutnya
    context.user_data['awaiting_payment_proof'] = deal_id
    
    await query.edit_message_text(proof_message, parse_mode="Markdown")




async def rekber_fee_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    deal_id = query.data.split("|")[1]

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT seller_id, buyer_id, title, admin_fee FROM deals WHERE id = ?", (deal_id,))
    row = cur.fetchone()

    if not row:
        await query.edit_message_text("❌ Transaksi tidak ditemukan.")
        conn.close()
        return

    seller_id = row['seller_id']
    buyer_id = row['buyer_id'] 
    title = row['title']
    admin_fee = row['admin_fee']
    conn.close()

    # Debug log untuk troubleshooting
    logger.debug(f"Fee payment confirmation - Deal: {deal_id}, Seller in DB: {seller_id}, Current User: {user_id}")

    # Pastikan seller_id tidak None dan user adalah seller
    if seller_id is None:
        await query.edit_message_text("❌ Penjual belum terdaftar dalam transaksi ini.")
        return

    if user_id != seller_id:
        await query.edit_message_text("❌ Hanya penjual yang bisa konfirmasi pembayaran biaya admin.")
        return

    # --- Notif ke Admin ---
    keyboard = [[InlineKeyboardButton("✅ Verifikasi Fee Admin", callback_data=f"fee_verify|{deal_id}")]]
    notif_text = (
        f"📢 <b>Konfirmasi Pembayaran Fee Admin</b>\n\n"
        f"🏷️ Judul: {title}\n"
        f"💸 Biaya Admin: Rp {admin_fee:,}\n\n"
        f"👨 Penjual sudah menekan tombol <b>Sudah Bayar</b>.\n\n"
        f"Silakan verifikasi."
    )
    await context.bot.send_message(
        chat_id=config.ADMIN_ID,
        text=notif_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    await query.edit_message_text("✅ Konfirmasi terkirim ke admin, menunggu verifikasi.")

async def rekber_fee_verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    deal_id = query.data.split("|")[1]

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT seller_id, buyer_id, title FROM deals WHERE id = ?", (deal_id,))
    row = cur.fetchone()

    if not row:
        await query.edit_message_text("❌ Transaksi tidak ditemukan.")
        conn.close()
        return

    seller_id = row['seller_id']
    buyer_id = row['buyer_id']
    title = row['title']
    conn.close()

    # Notif ke Penjual
    await context.bot.send_message(
        chat_id=seller_id,
        text=f"✅ Fee admin untuk transaksi <b>{title}</b> sudah diverifikasi.",
        parse_mode="HTML"
    )

    # Notif ke Pembeli
    await context.bot.send_message(
        chat_id=buyer_id,
        text=(
            f"📢 Fee admin untuk transaksi <b>{title}</b> sudah diterima.\n\n"
            "Silakan lakukan pembayaran harga barang sesuai instruksi."
        ),
        parse_mode="HTML"
    )

    await query.edit_message_text("✅ Fee admin berhasil diverifikasi. Transaksi lanjut ke tahap pendanaan.")

async def rekber_fund_verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    deal_id = query.data.split("|")[1]

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT seller_id, buyer_id, title FROM deals WHERE id = ?", (deal_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        await query.edit_message_text("❌ Transaksi tidak ditemukan.")
        return

    buyer_id, seller_id, title = row

    # Update status transaksi
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE deals SET status = ? WHERE id = ?", ("FUNDED", deal_id))
    conn.commit()
    conn.close()

    # --- Dana yang dilepas ke penjual ---
    released_amount = amount

    # Notif ke Penjual
    await context.bot.send_message(
        chat_id=seller_id,
        text=f"📦 Pembayaran untuk transaksi <b>{title}</b> sudah diverifikasi.\n\nSilakan kirim barang/jasa ke pembeli.",
        parse_mode="HTML"
    )

    # Notif ke Pembeli
    await context.bot.send_message(
        chat_id=buyer_id,
        text=f"✅ Pembayaran kamu untuk transaksi <b>{title}</b> sudah diverifikasi.\n\nMenunggu barang/jasa dari penjual.",
        parse_mode="HTML"
    )

    await query.edit_message_text("✅ Pembayaran pembeli berhasil diverifikasi. Transaksi lanjut ke tahap pengiriman.")

    # Logging (opsional)
    try:
        log_action(deal_id, buyer_id, "BUYER", "FUND_VERIFY", "Admin verifikasi pembayaran pembeli")
    except Exception:
        pass




async def rekber_admin_verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin handler untuk verifikasi pembayaran"""
    query = update.callback_query
    await query.answer()
    deal_id = query.data.split("|")[1]

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT buyer_id, seller_id, title, amount, admin_fee, admin_fee_payer FROM deals WHERE id = ?", (deal_id,))
    row = cur.fetchone()

    if not row:
        await query.edit_message_text("❌ Transaksi tidak ditemukan.")
        conn.close()
        return

    buyer_id = row['buyer_id']
    seller_id = row['seller_id']
    title = row['title']
    amount = int(row['amount'])  # Convert to integer
    admin_fee = int(row['admin_fee'])
    admin_fee_payer = row['admin_fee_payer']

    # Update status ke FUNDED (dana sudah terverifikasi)
    cur.execute("UPDATE deals SET status = ? WHERE id = ?", ("FUNDED", deal_id))
    conn.commit()
    conn.close()

    # Notifikasi ke kedua belah pihak
    await context.bot.send_message(
        chat_id=buyer_id,
        text=f"✅ Pembayaran untuk transaksi <b>{title}</b> sudah diverifikasi. Menunggu pengiriman barang/jasa.",
        parse_mode="HTML"
    )

    keyboard_seller = [[InlineKeyboardButton("📦 Tandai Sudah Dikirim", callback_data=f"rekber_mark_shipped|{deal_id}")]]
    await context.bot.send_message(
        chat_id=seller_id,
        text=f"✅ Pembayaran untuk transaksi <b>{title}</b> sudah diverifikasi. Silakan kirim barang/jasa ke pembeli.",
        parse_mode="HTML",
        reply_markup=keyboard_seller
    )

    await query.edit_message_text("✅ Pembayaran berhasil diverifikasi.")

# === REKBER STATUS WITH CANCEL BUTTON ===
async def rekber_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk melihat status transaksi dengan tombol batalkan jika diperlukan"""
    query = update.callback_query
    await query.answer()
    
    deal_id = query.data.split("|")[1]
    user_id = query.from_user.id
    
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT buyer_id, seller_id, status, title, amount, admin_fee, admin_fee_payer FROM deals WHERE id = ?",
        (deal_id,)
    )
    row = cur.fetchone()
    conn.close()
    
    if not row:
        await query.edit_message_text("❌ Transaksi tidak ditemukan.")
        return
    
    buyer_id = row['buyer_id']
    seller_id = row['seller_id']
    status = row['status']
    title = row['title']
    amount = int(row['amount'])
    admin_fee = int(row['admin_fee'])
    admin_fee_payer = row['admin_fee_payer']
    
    # Tentukan total pembayaran
    buyer_total = amount + admin_fee if admin_fee_payer == "BUYER" else amount
    seller_receive = amount if admin_fee_payer == "BUYER" else amount - admin_fee
    
    # Status mapping
    status_text_map = {
        "PENDING_JOIN": "⏳ Menunggu pihak lain bergabung",
        "PENDING_FUNDING": "💰 Menunggu pembayaran pembeli", 
        "WAITING_VERIFICATION": "🔍 Menunggu verifikasi admin",
        "FUNDED": "✅ Dana terverifikasi, siap kirim barang",
        "AWAITING_CONFIRM": "📦 Menunggu konfirmasi penerimaan",
        "RELEASED": "💰 Dana dilepas ke penjual",
        "COMPLETED": "✅ Transaksi selesai",
        "CANCELLED": "❌ Transaksi dibatalkan",
        "DISPUTED": "⚠️ Dalam sengketa"
    }
    
    status_display = status_text_map.get(status, status)
    
    status_message = (
        f"📋 **STATUS TRANSAKSI**\n\n"
        f"🆔 **ID:** `{deal_id}`\n"
        f"📦 **Produk:** {title}\n"
        f"💰 **Harga:** {format_rupiah(amount)}\n"
        f"💸 **Biaya Admin:** {format_rupiah(admin_fee)} *(ditanggung {admin_fee_payer})*\n"
        f"📊 **Total Pembeli:** {format_rupiah(buyer_total)}\n"
        f"💵 **Penjual Terima:** {format_rupiah(seller_receive)}\n\n"
        f"📌 **Status:** {status_display}"
    )
    
    keyboard = []
    
    # Tambahkan tombol berdasarkan status dan user
    if status in ["PENDING_FUNDING", "FUNDED", "AWAITING_CONFIRM"] and (user_id == buyer_id or user_id == seller_id):
        if status == "AWAITING_CONFIRM":
            # ✅ BALANCED DISPUTE: Both buyer and seller can open dispute
            if user_id == buyer_id:
                keyboard.extend([
                    [InlineKeyboardButton("✅ Barang Diterima", callback_data=f"rekber_release|{deal_id}")],
                    [InlineKeyboardButton("⚠️ Ajukan Sengketa", callback_data=f"rekber_dispute|{deal_id}")],
                    [InlineKeyboardButton("🚫 Batalkan Transaksi", callback_data=f"rekber_cancel_request|{deal_id}")]
                ])
            else:  # seller - now can also open dispute
                keyboard.extend([
                    [InlineKeyboardButton("⚠️ Ajukan Sengketa", callback_data=f"rekber_dispute|{deal_id}")],
                    [InlineKeyboardButton("🚫 Batalkan Transaksi", callback_data=f"rekber_cancel_request|{deal_id}")]
                ])
        else:
            # Tombol batalkan dan dispute untuk status FUNDED/SHIPPED
            if status in ["FUNDED", "SHIPPED"]:
                keyboard.extend([
                    [InlineKeyboardButton("⚠️ Ajukan Sengketa", callback_data=f"rekber_dispute|{deal_id}")],
                    [InlineKeyboardButton("🚫 Batalkan Transaksi", callback_data=f"rekber_cancel_request|{deal_id}")]
                ])
            else:
                keyboard.append([InlineKeyboardButton("🚫 Batalkan Transaksi", callback_data=f"rekber_cancel_request|{deal_id}")])
    
    # Tombol kembali
    keyboard.append([InlineKeyboardButton("🏠 Kembali", callback_data="rekber_main_menu")])
    
    await query.edit_message_text(
        status_message,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# --- STEP 4: SELLER SHIP ITEM ---
async def rekber_mark_shipped(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    deal_id = query.data.split("|")[1]
    user_id = query.from_user.id

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT buyer_id, seller_id, status FROM deals WHERE id=?", (deal_id,))
    row = cur.fetchone()
    if not row:
        await query.edit_message_text("❌ Transaksi tidak ditemukan.")
        conn.close()
        return

    buyer_id = row['buyer_id']
    seller_id_db = row['seller_id']
    status = row['status']

    logger.debug(f"Mark shipped - Deal: {deal_id}, Seller in DB: {seller_id_db}, Current User: {user_id}, Status: {status}")

    if seller_id_db is None:
        await query.edit_message_text("❌ Penjual belum terdaftar dalam transaksi ini.")
        conn.close()
        return

    if user_id != seller_id_db:
        await query.edit_message_text("❌ Hanya penjual yang bisa tandai pengiriman.")
        conn.close()
        return

    if status != "FUNDED":
        await query.edit_message_text("⚠️ Transaksi belum siap dikirim.")
        conn.close()
        return

    # update status jadi AWAITING_CONFIRM
    cur.execute("UPDATE deals SET status='AWAITING_CONFIRM' WHERE id=?", (deal_id,))
    conn.commit()
    conn.close()

    await query.edit_message_text("📦 Kamu sudah menandai barang/jasa dikirim. Menunggu konfirmasi buyer.")

    # notif ke buyer
    keyboard = [
        [InlineKeyboardButton("✅ Barang Diterima", callback_data=f"rekber_release|{deal_id}")],
        [InlineKeyboardButton("⚠️ Ajukan Sengketa", callback_data=f"rekber_dispute|{deal_id}")]
    ]
    await context.bot.send_message(
        chat_id=buyer_id,
        text=f"📦 Penjual telah menandai barang/jasa sudah dikirim untuk Rekber {deal_id}.\n\n"
             f"Jika sudah diterima & sesuai, klik *Barang Diterima* untuk rilis dana.\n"
             f"Jika ada masalah, klik *Ajukan Sengketa*.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# --- STEP 5: BUYER RELEASE ---
async def rekber_release(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    deal_id = query.data.split("|")[1]

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT buyer_id, seller_id, title, amount, admin_fee, admin_fee_payer FROM deals WHERE id = ?",
        (deal_id,)
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        await query.edit_message_text("❌ Transaksi tidak ditemukan.")
        return

    buyer_id = row['buyer_id']
    seller_id = row['seller_id']
    title = row['title']
    amount = int(row['amount'])  # Convert to integer
    admin_fee = int(row['admin_fee'])  # Convert to integer
    admin_fee_payer = row['admin_fee_payer']

    # Update status transaksi
    cur.execute("UPDATE deals SET status = ? WHERE id = ?", ("RELEASED", deal_id))
    conn.commit()
    conn.close()

    # --- Dana yang dilepas ke penjual ---
    released_amount = amount

    # Notif ke Penjual dengan tombol isi data pencairan
    keyboard_seller = [
        [InlineKeyboardButton("💳 Isi Data Pencairan", callback_data=f"payout_start|{deal_id}")],
        [InlineKeyboardButton("📋 Lihat Status", callback_data=f"rekber_status|{deal_id}")]
    ]

    text_seller = (
        f"💰 <b>Dana Siap Dicairkan!</b>\n\n"
        f"Transaksi <b>{title}</b> sudah selesai ✅\n\n"
        f"📦 Nominal Barang: {format_rupiah(amount)}\n"
        f"💸 Biaya Admin: {format_rupiah(admin_fee)} (ditanggung {admin_fee_payer})\n"
        f"💵 Dana Siap Dicairkan: {format_rupiah(released_amount)}\n\n"
        f"🏦 <b>Langkah Selanjutnya:</b>\n"
        f"Silakan isi data pencairan (rekening/e-wallet) untuk menerima dana.\n\n"
        f"Terima kasih telah menggunakan layanan Rekber."
    )
    await context.bot.send_message(
        chat_id=seller_id,
        text=text_seller,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard_seller)
    )

    # Notif ke Pembeli
    text_buyer = (
        f"✅ Transaksi <b>{title}</b> sudah selesai.\n\n"
        f"📦 Nominal Barang: Rp {amount:,}\n"
        f"💸 Biaya Admin: Rp {admin_fee:,} (ditanggung {admin_fee_payer})\n"
        f"💵 Dana sudah dilepas ke Penjual: Rp {released_amount:,}\n\n"
        f"Terima kasih telah menggunakan layanan Rekber."
    )
    await context.bot.send_message(
        chat_id=buyer_id,
        text=text_buyer,
        parse_mode="HTML"
    )

    await query.edit_message_text("✅ Dana berhasil dilepas ke penjual. Transaksi selesai.")

    # Logging
    try:
        log_action(deal_id, seller_id, "SELLER", "RELEASE", f"Release dana Rp {released_amount:,}")
    except Exception:
        pass


# --- STEP 5B: BUYER DISPUTE ---
async def rekber_dispute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    deal_id = query.data.split("|")[1]
    user_id = query.from_user.id

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT buyer_id, seller_id, status FROM deals WHERE id=?", (deal_id,))
    row = cur.fetchone()
    if not row:
        await query.edit_message_text("❌ Transaksi tidak ditemukan.")
        return

    buyer_id, seller_id, status = row
    
    # ✅ SECURITY FIX: Allow both buyer and seller to open dispute
    if user_id != buyer_id and user_id != seller_id:
        await query.edit_message_text("❌ Anda tidak terdaftar dalam transaksi ini.")
        return
    
    # Determine who is opening the dispute
    dispute_opener = "BUYER" if user_id == buyer_id else "SELLER"
    opener_name = "Pembeli" if dispute_opener == "BUYER" else "Penjual"

    # Allow dispute in multiple states for better protection
    if status not in ["AWAITING_CONFIRM", "FUNDED", "SHIPPED"]:
        await query.edit_message_text("⚠️ Sengketa hanya bisa dibuka setelah pembayaran terverifikasi.")
        return

    # update status → DISPUTED
    cur.execute("UPDATE deals SET status='DISPUTED' WHERE id=?", (deal_id,))
    conn.commit()
    conn.close()

    await query.edit_message_text(f"⚠️ {opener_name} telah membuka sengketa untuk Rekber {deal_id}.")

    # Record dispute in database for audit trail
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO disputes (deal_id, raised_by, reason, status) VALUES (?, ?, ?, ?)",
            (deal_id, user_id, f"Dispute dibuka oleh {opener_name}", "OPEN")
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error recording dispute: {e}")

    # Send detailed notification to admin
    admin_message = (
        f"🚨 **SENGKETA DIBUKA**\n\n"
        f"📋 **ID:** `{deal_id}`\n"
        f"👤 **Dibuka oleh:** {opener_name} ({user_id})\n"
        f"📊 **Status saat ini:** {status}\n\n"
        f"⚖️ **Tindakan yang diperlukan:**\n"
        f"• Review detail transaksi\n"
        f"• Investigasi masalah\n"
        f"• Ambil keputusan yang adil\n\n"
        f"Silakan pilih tindakan:"
    )
    
    keyboard = [
        [InlineKeyboardButton("✅ Release ke Penjual", callback_data=f"rekber_admin_release|{deal_id}")],
        [InlineKeyboardButton("💸 Refund ke Pembeli", callback_data=f"rekber_admin_refund|{deal_id}")],
        [InlineKeyboardButton("🤝 Buat Mediasi", callback_data=f"mediasi|{deal_id}")]
    ]
    
    # Send to admin
    await context.bot.send_message(
        chat_id=config.ADMIN_ID,
        text=admin_message,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    # Notify the other party about the dispute
    other_party_id = seller_id if dispute_opener == "BUYER" else buyer_id
    other_party_name = "Penjual" if dispute_opener == "BUYER" else "Pembeli"
    
    other_party_message = (
        f"⚠️ **SENGKETA DIBUKA**\n\n"
        f"📋 **ID Transaksi:** `{deal_id}`\n"
        f"🚨 **{opener_name}** telah membuka sengketa untuk transaksi ini.\n\n"
        f"Admin akan meninjau kasus ini dan mengambil keputusan yang adil. "
        f"Anda akan mendapat notifikasi setelah admin memutuskan."
    )
    
    await context.bot.send_message(
        chat_id=other_party_id,
        text=other_party_message,
        parse_mode="Markdown"
    )

#================REKBER HISTORY=======================
async def rekber_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, title, amount, admin_fee, admin_fee_payer, status "
        "FROM deals WHERE buyer_id = ? OR seller_id = ? ORDER BY id DESC LIMIT 10",
        (user_id, user_id)
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("📭 Belum ada riwayat transaksi.")
        return

    messages = []
    for deal_id, title, amount, admin_fee, admin_fee_payer, status in rows:
        if admin_fee_payer == "BUYER":
            total = amount + admin_fee
        else:
            total = amount

        messages.append(
            f"🆔 <b>ID:</b> {deal_id}\n"
            f"🏷️ <b>Judul:</b> {title}\n"
            f"💵 <b>Nominal Barang:</b> Rp {amount:,}\n"
            f"💸 <b>Biaya Admin:</b> Rp {admin_fee:,} (ditanggung {admin_fee_payer})\n"
            f"📦 <b>Total Transfer Pembeli:</b> Rp {total:,}\n"
            f"📊 <b>Status:</b> {status}\n"
            "— — — — —"
        )

    await update.message.reply_text(
        "<b>📜 Riwayat Transaksi Terakhir</b>\n\n" + "\n\n".join(messages),
        parse_mode="HTML"
    )



#============== REKBER AKTIF ======================
async def rekber_active(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, title, amount, admin_fee, admin_fee_payer, status
        FROM deals
        WHERE (buyer_id = ? OR seller_id = ?)
          AND status NOT IN ('RELEASED', 'COMPLETED', 'CANCELED')
        ORDER BY id DESC
        """,
        (user_id, user_id)
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("📭 Tidak ada transaksi aktif saat ini.")
        return

    messages = []
    for deal_id, title, amount, admin_fee, admin_fee_payer, status in rows:
        if admin_fee_payer == "BUYER":
            total = amount + admin_fee
        else:
            total = amount

        messages.append(
            f"🆔 <b>ID:</b> {deal_id}\n"
            f"🏷️ <b>Judul:</b> {title}\n"
            f"💵 <b>Nominal Barang:</b> Rp {amount:,}\n"
            f"💸 <b>Biaya Admin:</b> Rp {admin_fee:,} (ditanggung {admin_fee_payer})\n"
            f"📦 <b>Total Transfer Pembeli:</b> Rp {total:,}\n"
            f"📊 <b>Status:</b> {status}\n"
            "— — — — —"
        )

    await update.message.reply_text(
        "<b>📂 Transaksi Aktif</b>\n\n" + "\n\n".join(messages),
        parse_mode="HTML"
    )


#================ REKBER DONE ======================
async def rekber_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, title, amount, admin_fee, admin_fee_payer, status
        FROM deals
        WHERE (buyer_id = ? OR seller_id = ?)
          AND status IN ('RELEASED', 'COMPLETED')
        ORDER BY id DESC LIMIT 10
        """,
        (user_id, user_id)
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("📭 Belum ada transaksi yang selesai.")
        return

    messages = []
    for deal_id, title, amount, admin_fee, admin_fee_payer, status in rows:
        if admin_fee_payer == "BUYER":
            total = amount + admin_fee
        else:
            total = amount

        messages.append(
            f"🆔 <b>ID:</b> {deal_id}\n"
            f"🏷️ <b>Judul:</b> {title}\n"
            f"💵 <b>Nominal Barang:</b> Rp {amount:,}\n"
            f"💸 <b>Biaya Admin:</b> Rp {admin_fee:,} (ditanggung {admin_fee_payer})\n"
            f"📦 <b>Total Transfer Pembeli:</b> Rp {total:,}\n"
            f"✅ <b>Status:</b> {status}\n"
            "— — — — —"
        )

    await update.message.reply_text(
        "<b>✅ Transaksi Selesai</b>\n\n" + "\n\n".join(messages),
        parse_mode="HTML"
    )


#============== REKBER STATS ====================
async def rekber_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Hanya admin yang boleh akses
    if user_id not in config.ADMIN_ID:
        await update.message.reply_text("❌ Kamu tidak punya akses ke perintah ini.")
        return

    # Default: semua data
    month_filter = None
    start_date = None
    end_date = None

    if context.args:
        try:
            month_filter = datetime.strptime(context.args[0], "%Y-%m")
            start_date = month_filter.replace(day=1)
            # Hitung akhir bulan
            if start_date.month == 12:
                end_date = start_date.replace(year=start_date.year + 1, month=1, day=1)
            else:
                end_date = start_date.replace(month=start_date.month + 1, day=1)
        except ValueError:
            await update.message.reply_text("⚠️ Format salah. Gunakan contoh: `/rekber_stats 2025-08`")
            return

    conn = get_connection()
    cur = conn.cursor()

    # Query filter (opsional by bulan)
    filter_sql = ""
    params = []
    if month_filter:
        filter_sql = "WHERE created_at >= ? AND created_at < ?"
        params = [start_date, end_date]

    # Total transaksi
    cur.execute(f"SELECT COUNT(*) AS total, COALESCE(SUM(amount),0) AS total_amount FROM deals {filter_sql}", params)
    total_row = cur.fetchone()

    # Aktif
    cur.execute(f"""
        SELECT COUNT(*) AS aktif FROM deals
        {filter_sql + (' AND' if filter_sql else 'WHERE')}
        status IN ('PENDING_JOIN','PENDING_FUNDING','FUNDED','AWAITING_CONFIRM','DISPUTED')
    """, params)
    aktif_row = cur.fetchone()

    # Selesai
    cur.execute(f"""
        SELECT COUNT(*) AS selesai FROM deals
        {filter_sql + (' AND' if filter_sql else 'WHERE')}
        status IN ('RELEASED','REFUNDED','CANCELLED')
    """, params)
    selesai_row = cur.fetchone()

    # Dispute
    cur.execute(f"""
        SELECT COUNT(*) AS dispute FROM deals
        {filter_sql + (' AND' if filter_sql else 'WHERE')}
        status='DISPUTED'
    """, params)
    dispute_row = cur.fetchone()

    conn.close()

    # Judul
    if month_filter:
        period = month_filter.strftime("%B %Y")
    else:
        period = "Semua Periode"

    text = (
        f"📊 Statistik Rekber ({period})\n\n"
        f"🔹 Total Transaksi: {total_row['total']} (Rp{total_row['total_amount']})\n"
        f"🟢 Aktif: {aktif_row['aktif']}\n"
        f"✅ Selesai: {selesai_row['selesai']}\n"
        f"⚠️ Sengketa: {dispute_row['dispute']}\n"
    )

    await update.message.reply_text(text)


#======= REKBER FUNDING CANCEL =======
# Buyer batalkan pendanaan
async def rekber_funding_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    deal_id = query.data.split("|")[1]
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT buyer_id, seller_id, status FROM deals WHERE id=?", (deal_id,))
    row = cur.fetchone()

    if not row:
        await query.edit_message_text("❌ Transaksi tidak ditemukan.")
        return

    buyer_id, seller_id, status = row

    if status not in ["PENDING_FUNDING", "PENDING_JOIN"]:
        await query.edit_message_text("⚠️ Transaksi ini tidak bisa dibatalkan lagi.")
        return

    # update DB → batal
    cur.execute("UPDATE deals SET status='CANCELLED' WHERE id=?", (deal_id,))
    conn.commit()
    conn.close()

    log_action(deal_id, user_id, "BUYER", "CANCEL", f"Pembeli @{username} batalkan transaksi")

    # edit pesan di chat buyer
    await query.edit_message_text(
        f"❌ Transaksi {deal_id} telah *dibatalkan* oleh Pembeli.",
        parse_mode="Markdown"
    )

    # notif seller
    if seller_id:
        await context.bot.send_message(
            seller_id,
            f"⚠️ Transaksi {deal_id} dibatalkan oleh pembeli @{username}."
        )

#======= USER HISTORY =======
async def rekber_user_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk melihat riwayat rekber user - support callback query dan message"""
    
    # Handle callback query dari tombol
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        is_callback = True
    else:
        # Handle command /riwayat
        user_id = update.effective_user.id
        is_callback = False

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, title, amount, admin_fee, admin_fee_payer, status, created_at
        FROM deals
        WHERE buyer_id = ? OR seller_id = ?
        ORDER BY created_at DESC LIMIT 10
        """,
        (user_id, user_id)
    )
    rows = cur.fetchall()
    conn.close()

    # Status mapping untuk tampilan yang lebih friendly
    status_map = {
        "PENDING_JOIN": "⏳ Menunggu bergabung",
        "PENDING_FUNDING": "💰 Menunggu pembayaran",
        "WAITING_VERIFICATION": "🔍 Menunggu verifikasi",
        "FUNDED": "✅ Dana terverifikasi",
        "AWAITING_CONFIRM": "📦 Menunggu konfirmasi",
        "AWAITING_PAYOUT": "💳 Menunggu pencairan",
        "COMPLETED": "🎉 Selesai",
        "RELEASED": "💰 Dana dilepas",
        "CANCELLED": "❌ Dibatalkan",
        "DISPUTED": "⚖️ Sengketa",
        "REFUNDED": "💸 Dikembalikan"
    }

    if not rows:
        message_text = "📭 **RIWAYAT KOSONG**\n\nAnda belum memiliki riwayat transaksi rekber."
        
        if is_callback:
            keyboard = [[InlineKeyboardButton("🏠 Kembali", callback_data="rekber_main_menu")]]
            await query.edit_message_text(
                message_text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text(message_text, parse_mode="Markdown")
        return

    # Format riwayat transaksi
    history_text = "📜 **RIWAYAT TRANSAKSI REKBER**\n\n"
    
    for i, row in enumerate(rows, 1):
        deal_id = row['id']
        title = row['title']
        amount = int(row['amount'])
        admin_fee = int(row['admin_fee'])
        admin_fee_payer = row['admin_fee_payer']
        status = row['status']
        created_at = row['created_at']
        
        # Hitung total transfer
        buyer_total = amount + admin_fee if admin_fee_payer == "BUYER" else amount
        seller_receive = amount if admin_fee_payer == "BUYER" else amount - admin_fee
        
        # Status display
        status_display = status_map.get(status, status)
        
        # Format tanggal - handle string datetime dari SQLite
        from datetime import datetime
        if isinstance(created_at, str):
            try:
                created_at_obj = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                formatted_date = created_at_obj.strftime('%d/%m/%Y %H:%M')
            except:
                formatted_date = created_at[:16]  # Fallback: ambil 16 karakter pertama
        else:
            formatted_date = created_at.strftime('%d/%m/%Y %H:%M')
        
        history_text += (
            f"**{i}. {title[:30]}{'...' if len(title) > 30 else ''}**\n"
            f"🆔 ID: `{deal_id}`\n"
            f"💰 Harga: {format_rupiah(amount)}\n"
            f"💸 Fee: {format_rupiah(admin_fee)} *(ditanggung {admin_fee_payer.lower()})*\n"
            f"📊 Status: {status_display}\n"
            f"📅 Tanggal: {formatted_date}\n"
        )
        
        # Tambahkan tombol detail jika callback
        if is_callback and i <= 5:  # Batasi 5 transaksi pertama untuk mencegah keyboard terlalu panjang
            history_text += f"📋 [Lihat Detail](callback:rekber_status|{deal_id})\n"
        
        history_text += "\n━━━━━━━━━━━━━━━━━━━━\n\n"

    # Tambahkan keyboard untuk callback
    if is_callback:
        keyboard = []
        
        # Tambahkan tombol quick action untuk transaksi aktif
        active_deals = [row for row in rows if row['status'] not in ['COMPLETED', 'RELEASED', 'CANCELLED', 'REFUNDED']]
        if active_deals:
            history_text += "🔍 **AKSI CEPAT:**\n"
            quick_buttons = []
            for deal in active_deals[:3]:  # Maksimal 3 tombol
                quick_buttons.append(InlineKeyboardButton(
                    f"📋 {deal['id'][:8]}", 
                    callback_data=f"rekber_status|{deal['id']}"
                ))
            
            # Bagi menjadi baris jika lebih dari 2 tombol
            if len(quick_buttons) <= 2:
                keyboard.append(quick_buttons)
            else:
                keyboard.append(quick_buttons[:2])
                keyboard.append(quick_buttons[2:])

        # Tombol navigasi
        nav_buttons = [
            InlineKeyboardButton("📂 Transaksi Aktif", callback_data="rekber_active_menu"),
            InlineKeyboardButton("✅ Selesai", callback_data="rekber_done_menu")
        ]
        keyboard.append(nav_buttons)
        keyboard.append([InlineKeyboardButton("🏠 Menu Utama", callback_data="rekber_main_menu")])
        
        await query.edit_message_text(
            history_text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        # Command response
        await update.message.reply_text(history_text, parse_mode="Markdown")

async def rekber_history_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler khusus untuk callback rekber_history_menu"""
    await rekber_user_history(update, context)


#================ REKBER STATUS MENU ======================
async def rekber_status_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk menu cek status transaksi"""
    query = update.callback_query
    await query.answer()

    status_text = (
        "📋 **MENU CEK STATUS TRANSAKSI**\n\n"
        "Pilih opsi untuk melihat status transaksi Anda:"
    )

    keyboard = [
        [InlineKeyboardButton("📂 Transaksi Aktif", callback_data="rekber_active_menu")],
        [InlineKeyboardButton("✅ Transaksi Selesai", callback_data="rekber_done_menu")],
        [InlineKeyboardButton("📜 Semua Riwayat", callback_data="rekber_user_history")],
        [InlineKeyboardButton("🏠 Kembali", callback_data="rekber_main_menu")]
    ]

    await query.edit_message_text(
        status_text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def rekber_active_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk callback menu aktif"""
    query = update.callback_query
    await query.answer()

    # Update context untuk compatibility dengan fungsi existing
    update.effective_user = query.from_user

    await rekber_active(update, context)

async def rekber_done_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk callback menu selesai"""
    query = update.callback_query
    await query.answer()

    # Update context untuk compatibility dengan fungsi existing
    update.effective_user = query.from_user

    await rekber_done(update, context)

#================ REKBER STATS ====================
# (Stats handler remains the same as it was not part of the changes)
# async def rekber_stats(update: Update, context: ContextTypes.DEFAULT_TYPE): ...


#================ REKBER PAYOUT ======================
# State khusus payout (angka bebas karena per-ConversationHandler)
PAY_METHOD, PAY_BANK_NAME, PAY_BANK_NUMBER, PAY_BANK_HOLDER, PAY_EW_PROVIDER, PAY_EW_NUMBER, PAY_NOTE = range(100, 107)

# Mulai: hanya SELLER dari deal itu yang boleh isi
async def payout_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    deal_id = query.data.split("|")[1]
    user_id = query.from_user.id

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT seller_id, status, title FROM deals WHERE id=?", (deal_id,))
    row = cur.fetchone()

    if not row:
        await query.edit_message_text("❌ Transaksi tidak ditemukan.")
        conn.close()
        return ConversationHandler.END

    seller_id_db = row['seller_id']
    status = row['status']
    title = row['title']
    conn.close()

    # Debug logging
    logger.debug(f"Payout start - Deal: {deal_id}, Seller in DB: {seller_id_db}, Current User: {user_id}, Status: {status}")

    # Pastikan user adalah penjual yang terdaftar di transaksi ini
    if seller_id_db is None:
        await query.edit_message_text("❌ Penjual belum terdaftar dalam transaksi ini.")
        return ConversationHandler.END

    if user_id != seller_id_db:
        await query.edit_message_text("❌ Hanya penjual pada transaksi ini yang dapat mengisi rekening pencairan.")
        return ConversationHandler.END

    # Check if payout info already exists
    from db_sqlite import get_payout_info
    existing_payout = get_payout_info(deal_id)

    if existing_payout:
        # Show existing payout info with option to update
        if existing_payout["method"] == "BANK":
            payout_summary = (
                f"🏦 *Bank:* {existing_payout['bank_name']}\n"
                f"🔢 *No. Rekening:* `{existing_payout['account_number']}`\n"
                f"👤 *Nama:* {existing_payout['account_name']}"
            )
        else:
            payout_summary = (
                f"📱 *E-Wallet:* {existing_payout['ewallet_provider']}\n"
                f"🔢 *No.:* `{existing_payout['ewallet_number']}`"
            )

        kb = [
            [InlineKeyboardButton("✏️ Update Data Pencairan", callback_data="payout_method|UPDATE")],
            [InlineKeyboardButton("❌ Batal", callback_data="payout_cancel")]
        ]

        await query.edit_message_text(
            f"💳 *Data Pencairan Sudah Ada*\n\n"
            f"📋 *Transaksi:* `{deal_id}`\n"
            f"📦 *Produk:* {title}\n\n"
            f"💰 *Data Pencairan Saat Ini:*\n{payout_summary}\n\n"
            f"Pilih aksi:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return PAY_METHOD

    # simpan deal_id di user_data
    context.user_data["payout_deal_id"] = deal_id

    kb = [
        [InlineKeyboardButton("🏦 Bank Transfer", callback_data="payout_method|BANK")],
        [InlineKeyboardButton("📱 E-Wallet", callback_data="payout_method|EWALLET")],
        [InlineKeyboardButton("❌ Batal", callback_data="payout_cancel")]
    ]
    await query.edit_message_text(
        f"💳 *Pencairan Dana Rekber* `{deal_id}`\n\n"
        f"📦 *Produk:* {title}\n\n"
        f"Pilih metode pencairan:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return PAY_METHOD

async def payout_pick_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, method = query.data.split("|")

    if method == "UPDATE":
        # User wants to update existing payout, show method selection again
        kb = [
            [InlineKeyboardButton("🏦 Bank Transfer", callback_data="payout_method|BANK")],
            [InlineKeyboardButton("📱 E-Wallet", callback_data="payout_method|EWALLET")],
            [InlineKeyboardButton("❌ Batal", callback_data="payout_cancel")]
        ]
        await query.edit_message_text(
            "💳 *Pilih Metode Pencairan Baru:*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return PAY_METHOD

    context.user_data["payout_method"] = method

    if method == "BANK":
        await query.edit_message_text("🏦 Masukkan *Nama Bank* (contoh: BCA, BRI, BNI, Mandiri, Jago, Seabank, dll):", parse_mode="Markdown")
        return PAY_BANK_NAME
    else:  # EWALLET
        await query.edit_message_text("📱 Masukkan *Nama E-Wallet* (contoh: DANA, OVO, GoPay, ShopeePay):", parse_mode="Markdown")
        return PAY_EW_PROVIDER

# --- BANK flow ---
async def payout_bank_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["bank_name"] = update.message.text.strip()
    await update.message.reply_text("🔢 Masukkan *Nomor Rekening*:")
    return PAY_BANK_NUMBER

async def payout_bank_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from security import validate_bank_account, sanitize_input, log_security_event

    account_number = sanitize_input(update.message.text.strip(), max_length=25)

    if not validate_bank_account(account_number):
        log_security_event("INVALID_BANK_ACCOUNT", update.effective_user.id, f"Invalid bank account: {account_number}")
        await update.message.reply_text(
            "❌ Nomor rekening tidak valid. Masukkan 6-20 digit angka.\n"
            "Contoh: <code>1234567890</code>",
            parse_mode="HTML"
        )
        return PAY_BANK_NUMBER

    context.user_data["account_number"] = account_number
    await update.message.reply_text("👤 Masukkan *Nama Pemilik Rekening* (sesuai buku/tabungan/aplikasi):")
    return PAY_BANK_HOLDER

async def payout_bank_holder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["account_name"] = update.message.text.strip()
    await update.message.reply_text("📝 Catatan tambahan (opsional). Ketik '-' jika tidak ada:")
    return PAY_NOTE

# --- EWALLET flow ---
async def payout_ew_provider(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["ewallet_provider"] = update.message.text.strip()
    await update.message.reply_text("🔢 Masukkan *Nomor E-Wallet*:")
    return PAY_EW_NUMBER

async def payout_ew_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from security import validate_phone_number, sanitize_input, log_security_event

    ewallet_number = sanitize_input(update.message.text.strip(), max_length=20)

    if not validate_phone_number(ewallet_number):
        log_security_event("INVALID_EWALLET", update.effective_user.id, f"Invalid e-wallet number: {ewallet_number}")
        await update.message.reply_text(
            "❌ Nomor e-wallet tidak valid. Gunakan format Indonesia.\n"
            "Contoh: <code>081234567890</code> atau <code>6281234567890</code>",
            parse_mode="HTML"
        )
        return PAY_EW_NUMBER

    context.user_data["ewallet_number"] = ewallet_number
    await update.message.reply_text("📝 Catatan tambahan (opsional). Ketik '-' jika tidak ada:")
    return PAY_NOTE

# --- FINAL SAVE (kedua flow masuk sini) ---
async def payout_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk membatalkan pengisian data payout"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text("❌ Pengisian data pencairan dibatalkan.")

    # Clear user data
    context.user_data.pop("payout_deal_id", None)
    context.user_data.pop("payout_method", None)

    return ConversationHandler.END

async def payout_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    note = update.message.text.strip()
    if note == "-":
        note = None

    deal_id = context.user_data.get("payout_deal_id")
    method = context.user_data.get("payout_method")
    seller_id = update.effective_user.id

    if method == "BANK":
        save_payout_info(
            deal_id, seller_id, "BANK",
            bank_name=context.user_data.get("bank_name"),
            account_number=context.user_data.get("account_number"),
            account_name=context.user_data.get("account_name"),
            note=note
        )
        summary = (
            f"🏦 *Bank:* {context.user_data.get('bank_name')}\n"
            f"🔢 *No. Rekening:* `{context.user_data.get('account_number')}`\n"
            f"👤 *Nama:* {context.user_data.get('account_name')}"
        )
    else:
        save_payout_info(
            deal_id, seller_id, "EWALLET",
            ewallet_provider=context.user_data.get("ewallet_provider"),
            ewallet_number=context.user_data.get("ewallet_number"),
            note=note
        )
        summary = (
            f"📱 *E-Wallet:* {context.user_data.get('ewallet_provider')}\n"
            f"🔢 *No.:* `{context.user_data.get('ewallet_number')}`"
        )

    # Update status ke AWAITING_PAYOUT setelah penjual isi rekening
    conn = get_connection()
    cur = conn.cursor()

    # Check current status first
    cur.execute("SELECT status FROM deals WHERE id=?", (deal_id,))
    current_status = cur.fetchone()

    if current_status and current_status['status'] in ['FUNDED', 'AWAITING_CONFIRM', 'RELEASED']:
        cur.execute("UPDATE deals SET status='AWAITING_PAYOUT' WHERE id=?", (deal_id,))
        conn.commit()

    conn.close()

    # Konfirmasi ke seller
    await update.message.reply_text(
        f"✅ *Data pencairan tersimpan untuk* `{deal_id}`\n\n{summary}\n"
        + (f"\n📝 *Catatan:* {note}" if note else ""),
        parse_mode="Markdown"
    )

    # Beri tahu admin (semua ADMIN_IDS) dengan tombol konfirmasi
    keyboard = [
        [InlineKeyboardButton("✅ Konfirmasi & Selesaikan Transaksi", callback_data=f"admin_confirm_payout|{deal_id}")]
    ]
    await context.bot.send_message(
        chat_id=config.ADMIN_ID,
        text=f"🔔 Penjual mengisi *rekening pencairan* untuk `{deal_id}`:\n\n{summary}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    # bersihkan context
    context.user_data.pop("payout_deal_id", None)
    context.user_data.pop("payout_method", None)
    return ConversationHandler.END


#============= MEDIASI ====================

async def handle_mediasi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    deal_id = query.data.split("|")[1]
    context.user_data['deal_id'] = deal_id  # Simpan deal_id untuk digunakan nanti

    await query.message.reply_text("🔗 Silakan masukkan link grup mediasi:")
    return ASK_GROUP_LINK

async def receive_group_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    group_link = update.message.text
    deal_id = context.user_data.get('deal_id')

    # Ambil buyer_id & seller_id dari database
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT buyer_id, seller_id FROM deals WHERE id=?", (deal_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        await update.message.reply_text("❌ Data transaksi tidak ditemukan.")
        return ConversationHandler.END

    buyer_id, seller_id = row

    # Kirim pesan ke Buyer dan Seller
    message = (
        f"📢 Mediasi telah dibentuk untuk transaksi {deal_id} antara Pembeli dan Penjual.\n\n"
        f"🔗 Silakan join grup mediasi untuk menyelesaikan masalah: {group_link}"
    )

    await context.bot.send_message(chat_id=buyer_id, text=message)
    await context.bot.send_message(chat_id=seller_id, text=message)


    await update.message.reply_text("✅ Link grup sudah dikirim kepada Pembeli dan Penjual.")

    return ConversationHandler.END

# === Konfirmasi & Batal ===
async def rekber_confirm_create(update, context):
    query = update.callback_query
    await query.answer()

    role = context.user_data.get("role")
    title = context.user_data.get("title")
    amount = context.user_data.get("amount")
    admin_fee = context.user_data.get("admin_fee")

    if not role or not title or not amount:
        await query.edit_message_text("❌ Data transaksi tidak lengkap, ulangi dari awal.")
        return ConversationHandler.END

    if role == "SELLER":
        await rekber_new_seller(update, context, title, amount, admin_fee)
    else:
        await rekber_new_buyer(update, context, title, amount, admin_fee)

    return ConversationHandler.END


async def rekber_cancel_create(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("❌ Pembuatan transaksi dibatalkan.")
    return ConversationHandler.END

# === CANCEL REQUEST FUNCTIONS ===
async def rekber_cancel_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk permintaan pembatalan transaksi"""
    query = update.callback_query
    await query.answer()
    
    deal_id = query.data.split("|")[1]
    user_id = query.from_user.id
    
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT buyer_id, seller_id, status, title FROM deals WHERE id = ?", (deal_id,))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        await query.edit_message_text("❌ Transaksi tidak ditemukan.")
        return
    
    buyer_id = row['buyer_id']
    seller_id = row['seller_id']
    status = row['status']
    title = row['title']
    
    # Tentukan siapa yang mengajukan dan siapa yang harus menyetujui
    if user_id == buyer_id:
        requester = "BUYER"
        approver_id = seller_id
        approver_name = "penjual"
    elif user_id == seller_id:
        requester = "SELLER"
        approver_id = buyer_id
        approver_name = "pembeli"
    else:
        await query.edit_message_text("❌ Anda tidak terdaftar dalam transaksi ini.")
        return
    
    # Cek status transaksi
    if status not in ["PENDING_FUNDING", "FUNDED", "AWAITING_CONFIRM"]:
        await query.edit_message_text("❌ Transaksi ini tidak dapat dibatalkan pada tahap saat ini.")
        return
    
    await query.edit_message_text("✅ Permintaan pembatalan telah dikirim ke pihak lain.")
    
    # Kirim notifikasi ke pihak yang harus menyetujui
    keyboard = [
        [InlineKeyboardButton("✅ Setuju Batalkan", callback_data=f"rekber_cancel_approve|{deal_id}")],
        [InlineKeyboardButton("❌ Tolak Pembatalan", callback_data=f"rekber_cancel_reject|{deal_id}")]
    ]
    
    cancel_message = (
        f"🚫 **PERMINTAAN PEMBATALAN TRANSAKSI**\n\n"
        f"📋 **ID:** `{deal_id}`\n"
        f"📦 **Produk:** {title}\n\n"
        f"Pihak lain meminta untuk membatalkan transaksi ini.\n\n"
        f"⚠️ **Jika disetujui:**\n"
        f"• Pembeli akan mendapat refund\n"
        f"• Transaksi akan ditutup\n\n"
        f"Apakah Anda setuju?"
    )
    
    await context.bot.send_message(
        chat_id=approver_id,
        text=cancel_message,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    log_action(deal_id, user_id, requester, "CANCEL_REQUEST", f"Mengajukan pembatalan transaksi")

async def rekber_cancel_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk menyetujui pembatalan transaksi"""
    query = update.callback_query
    await query.answer()
    
    deal_id = query.data.split("|")[1]
    user_id = query.from_user.id
    
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT buyer_id, seller_id, status, title FROM deals WHERE id = ?", (deal_id,))
    row = cur.fetchone()
    
    if not row:
        await query.edit_message_text("❌ Transaksi tidak ditemukan.")
        conn.close()
        return
    
    buyer_id = row['buyer_id']
    seller_id = row['seller_id']
    status = row['status']
    title = row['title']
    
    # Update status transaksi
    cur.execute("UPDATE deals SET status = 'CANCELLED' WHERE id = ?", (deal_id,))
    conn.commit()
    conn.close()
    
    await query.edit_message_text("✅ Transaksi berhasil dibatalkan atas persetujuan kedua belah pihak.")
    
    # Notifikasi ke kedua pihak
    cancel_notification = (
        f"✅ **TRANSAKSI DIBATALKAN**\n\n"
        f"📋 **ID:** `{deal_id}`\n"
        f"📦 **Produk:** {title}\n\n"
        f"Transaksi telah dibatalkan atas persetujuan kedua belah pihak.\n"
        f"Pembeli akan mendapat refund dari admin."
    )
    
    await context.bot.send_message(chat_id=buyer_id, text=cancel_notification, parse_mode="Markdown")
    await context.bot.send_message(chat_id=seller_id, text=cancel_notification, parse_mode="Markdown")
    
    # Notifikasi admin untuk proses refund
    admin_notification = (
        f"🚫 **TRANSAKSI DIBATALKAN**\n\n"
        f"📋 ID: <code>{deal_id}</code>\n"
        f"📦 Produk: {title}\n\n"
        f"Kedua pihak telah menyetujui pembatalan.\n"
        f"Silakan proses refund ke pembeli."
    )
    
    await context.bot.send_message(
        chat_id=config.ADMIN_ID,
        text=admin_notification,
        parse_mode="HTML"
    )
    
    log_action(deal_id, user_id, "BOTH", "CANCEL_APPROVED", "Pembatalan transaksi disetujui")

async def rekber_cancel_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk menolak pembatalan transaksi"""
    query = update.callback_query
    await query.answer()
    
    deal_id = query.data.split("|")[1]
    user_id = query.from_user.id
    
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT buyer_id, seller_id, title FROM deals WHERE id = ?", (deal_id,))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        await query.edit_message_text("❌ Transaksi tidak ditemukan.")
        return
    
    buyer_id = row['buyer_id']
    seller_id = row['seller_id']
    title = row['title']
    
    await query.edit_message_text("❌ Pembatalan transaksi ditolak. Transaksi akan dilanjutkan.")
    
    # Notifikasi ke pihak yang mengajukan pembatalan
    other_party_id = seller_id if user_id == buyer_id else buyer_id
    
    reject_notification = (
        f"❌ **PEMBATALAN DITOLAK**\n\n"
        f"📋 **ID:** `{deal_id}`\n"
        f"📦 **Produk:** {title}\n\n"
        f"Pihak lain menolak permintaan pembatalan Anda.\n"
        f"Transaksi akan dilanjutkan sesuai prosedur."
    )
    
    await context.bot.send_message(
        chat_id=other_party_id,
        text=reject_notification,
        parse_mode="Markdown"
    )
    
    log_action(deal_id, user_id, "USER", "CANCEL_REJECTED", "Pembatalan transaksi ditolak")

# ========== PAYMENT PROOF HANDLER ==========
async def handle_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk menerima bukti pembayaran dari user"""
    if not update.message or not update.message.photo:
        return  # Bukan foto, abaikan
    
    user_id = update.effective_user.id
    deal_id = context.user_data.get('awaiting_payment_proof')
    
    if not deal_id:
        return  # User tidak sedang dalam proses upload bukti
    
    # Validasi user adalah buyer dari transaksi ini
    conn = get_connection()
    if not conn:
        await update.message.reply_text("❌ Terjadi kesalahan koneksi database.")
        return
    
    cur = conn.cursor()
    try:
        cur.execute("SELECT buyer_id, title, amount, admin_fee, admin_fee_payer, status FROM deals WHERE id=?", (deal_id,))
        row = cur.fetchone()
        
        if not row or row['buyer_id'] != user_id or row['status'] != 'WAITING_PAYMENT_PROOF':
            await update.message.reply_text("❌ Bukti pembayaran tidak valid untuk transaksi ini.")
            return
        
        title = row['title']
        amount = int(row['amount'])
        admin_fee = int(row['admin_fee'])
        admin_fee_payer = row['admin_fee_payer']
        
        # Ambil file photo dengan resolusi tertinggi
        photo = update.message.photo[-1]
        file_id = photo.file_id
        
        # Simpan bukti pembayaran ke database
        cur.execute(
            "UPDATE deals SET payment_proof_file_id=?, status='WAITING_VERIFICATION' WHERE id=?", 
            (file_id, deal_id)
        )
        conn.commit()
        
        # Clear context
        context.user_data.pop('awaiting_payment_proof', None)
        
        # Send confirmation to user
        await update.message.reply_text(
            "✅ Bukti pembayaran berhasil diterima!\n\n"
            "Admin akan segera memverifikasi pembayaran Anda. "
            "Anda akan mendapat notifikasi setelah verifikasi selesai."
        )
        
        # Kirim ke admin untuk verifikasi dengan foto bukti
        total_amount = amount + admin_fee if admin_fee_payer == "BUYER" else amount
        
        admin_message = (
            f"💰 **VERIFIKASI PEMBAYARAN**\n\n"
            f"📋 **ID:** `{deal_id}`\n"
            f"📦 **Produk:** {title}\n"
            f"💵 **Total yang harus dibayar:** {format_rupiah(total_amount)}\n"
            f"👤 **Pembeli:** [{user_id}](tg://user?id={user_id})\n\n"
            f"⬇️ **Bukti pembayaran dari pembeli:**"
        )
        
        keyboard = [
            [InlineKeyboardButton("✅ Verifikasi", callback_data=f"verify_payment|{deal_id}")],
            [InlineKeyboardButton("❌ Tolak", callback_data=f"reject_payment|{deal_id}")]
        ]
        
        # Kirim foto bukti ke admin
        try:
            await context.bot.send_photo(
                chat_id=config.ADMIN_ID,
                photo=file_id,
                caption=admin_message,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            logger.info(f"Payment proof sent to admin for deal {deal_id}")
        except Exception as e:
            logger.error(f"Error sending payment proof to admin: {e}")
            await update.message.reply_text("⚠️ Bukti pembayaran diterima, namun gagal mengirim ke admin. Silakan hubungi @Nexoitsme")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error saving payment proof: {e}")
        await update.message.reply_text("❌ Terjadi kesalahan saat menyimpan bukti pembayaran.")
    finally:
        cur.close()
        return_connection(conn)

# ========== PAYMENT VERIFICATION HANDLERS ==========
async def verify_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk admin memverifikasi pembayaran"""
    query = update.callback_query
    await query.answer()
    
    deal_id = query.data.split("|")[1]
    
    conn = get_connection()
    if not conn:
        await query.edit_message_caption("❌ Terjadi kesalahan koneksi database.")
        return
    
    cur = conn.cursor()
    try:
        # Update status transaksi ke FUNDED
        cur.execute("UPDATE deals SET status='FUNDED' WHERE id=?", (deal_id,))
        
        # Get transaction details
        cur.execute("SELECT buyer_id, seller_id, title FROM deals WHERE id=?", (deal_id,))
        row = cur.fetchone()
        
        if not row:
            await query.edit_message_caption("❌ Transaksi tidak ditemukan.")
            return
        
        buyer_id = row['buyer_id']
        seller_id = row['seller_id']
        title = row['title']
        
        conn.commit()
        
        # Update admin message
        await query.edit_message_caption(
            f"✅ **PEMBAYARAN DIVERIFIKASI**\n\n"
            f"📋 **ID:** `{deal_id}`\n"
            f"📦 **Produk:** {title}\n\n"
            f"Pembayaran telah diverifikasi dan dana aman di admin.",
            parse_mode="Markdown"
        )
        
        # Notifikasi ke buyer
        await context.bot.send_message(
            chat_id=buyer_id,
            text=f"✅ Pembayaran untuk transaksi <b>{title}</b> ({deal_id}) sudah diverifikasi.\n\nMenunggu penjual mengirim barang/jasa.",
            parse_mode="HTML"
        )
        
        # Notifikasi ke seller dengan tombol mark shipped
        keyboard_seller = [[InlineKeyboardButton("📦 Tandai Sudah Dikirim", callback_data=f"rekber_mark_shipped|{deal_id}")]]
        await context.bot.send_message(
            chat_id=seller_id,
            text=f"✅ Pembayaran untuk transaksi <b>{title}</b> ({deal_id}) sudah diverifikasi.\n\nSilakan kirim barang/jasa ke pembeli.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard_seller)
        )
        
        log_action(deal_id, query.from_user.id, "ADMIN", "VERIFY_PAYMENT", "Admin verifikasi pembayaran")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error verifying payment: {e}")
        await query.edit_message_caption("❌ Terjadi kesalahan saat memverifikasi pembayaran.")
    finally:
        cur.close()
        return_connection(conn)

async def reject_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk admin menolak pembayaran"""
    query = update.callback_query
    await query.answer()
    
    deal_id = query.data.split("|")[1]
    
    conn = get_connection()
    if not conn:
        await query.edit_message_caption("❌ Terjadi kesalahan koneksi database.")
        return
    
    cur = conn.cursor()
    try:
        # Update status transaksi kembali ke PENDING_FUNDING
        cur.execute("UPDATE deals SET status='PENDING_FUNDING', payment_proof_file_id=NULL WHERE id=?", (deal_id,))
        
        # Get transaction details
        cur.execute("SELECT buyer_id, title FROM deals WHERE id=?", (deal_id,))
        row = cur.fetchone()
        
        if not row:
            await query.edit_message_caption("❌ Transaksi tidak ditemukan.")
            return
        
        buyer_id = row['buyer_id']
        title = row['title']
        
        conn.commit()
        
        # Update admin message
        await query.edit_message_caption(
            f"❌ **PEMBAYARAN DITOLAK**\n\n"
            f"📋 **ID:** `{deal_id}`\n"
            f"📦 **Produk:** {title}\n\n"
            f"Bukti pembayaran tidak valid atau tidak sesuai.",
            parse_mode="Markdown"
        )
        
        # Notifikasi ke buyer
        keyboard_buyer = [[InlineKeyboardButton("💰 Coba Transfer Lagi", callback_data=f"start_payment|{deal_id}")]]
        await context.bot.send_message(
            chat_id=buyer_id,
            text=f"❌ Bukti pembayaran untuk transaksi <b>{title}</b> ({deal_id}) ditolak admin.\n\nSilakan periksa kembali nominal dan metode pembayaran, lalu coba transfer ulang.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard_buyer)
        )
        
        log_action(deal_id, query.from_user.id, "ADMIN", "REJECT_PAYMENT", "Admin tolak bukti pembayaran")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error rejecting payment: {e}")
        await query.edit_message_caption("❌ Terjadi kesalahan saat menolak pembayaran.")
    finally:
        cur.close()
        return_connection(conn)