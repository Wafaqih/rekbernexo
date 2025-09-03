from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from db_postgres import get_connection, log_action, get_payout_info, get_admin_dashboard_stats
from utils import format_rupiah
import config
import logging

logger = logging.getLogger(__name__)


async def rekber_admin_verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin handler untuk verifikasi pembayaran"""
    query = update.callback_query
    await query.answer()
    deal_id = query.data.split("|")[1]

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT buyer_id, seller_id, title, amount, admin_fee, admin_fee_payer FROM deals WHERE id = %s", (deal_id,))
        row = cur.fetchone()

        if not row:
            await query.edit_message_text("❌ Transaksi tidak ditemukan.")
            return

        buyer_id = row['buyer_id']
        seller_id = row['seller_id']
        title = row['title']
        amount = int(row['amount'])  # Convert to integer
        admin_fee = int(row['admin_fee'])
        admin_fee_payer = row['admin_fee_payer']

        # Update status ke FUNDED (dana sudah terverifikasi)
        cur.execute("UPDATE deals SET status = %s WHERE id = %s", ("FUNDED", deal_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error in rekber_admin_verify: {e}")
        await query.edit_message_text("❌ Terjadi kesalahan saat verifikasi.")
        return
    finally:
        cur.close()
        from db_postgres import return_connection
        return_connection(conn)

    # Log the verification
    from db_postgres import log_action
    log_action(deal_id, query.from_user.id, "ADMIN", "VERIFY_PAYMENT", f"Admin verifikasi pembayaran untuk {title}")

    # Notifikasi ke pembeli
    await context.bot.send_message(
        chat_id=buyer_id,
        text=f"✅ Pembayaran untuk transaksi <b>{title}</b> sudah diverifikasi. Menunggu pengiriman barang/jasa dari penjual.",
        parse_mode="HTML"
    )

    # Notifikasi ke penjual dengan tombol mark shipped
    keyboard_seller = [[InlineKeyboardButton("📦 Tandai Sudah Dikirim", callback_data=f"rekber_mark_shipped|{deal_id}")]]
    await context.bot.send_message(
        chat_id=seller_id,
        text=f"✅ Pembayaran untuk transaksi <b>{title}</b> sudah diverifikasi. Silakan kirim barang/jasa ke pembeli dan klik tombol di bawah setelah selesai.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard_seller)
    )

    await query.edit_message_text(f"✅ Pembayaran untuk transaksi {deal_id} berhasil diverifikasi.")


# ADMIN: FINAL RELEASE (cek payout dulu)
async def admin_release_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    deal_id = query.data.split("|")[1]

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT buyer_id, seller_id, title, amount FROM deals WHERE id=%s", (deal_id,))
        row = cur.fetchone()
    finally:
        cur.close()
        from db_postgres import return_connection
        return_connection(conn)

    if not row:
        await query.edit_message_text("❌ Transaksi tidak ditemukan.")
        return

    buyer_id, seller_id, title, amount = row
    payout = get_payout_info(deal_id)

    if not payout:
        # otomatis minta seller mengisi
        kb_seller = [[InlineKeyboardButton("💳 Isi Rekening Pencairan", callback_data=f"payout_start|{deal_id}")]]
        await context.bot.send_message(
            seller_id,
            f"⚠️ Admin akan merilis dana untuk `{deal_id}`, namun data pencairan belum ada.\n"
            f"Silakan isi terlebih dahulu:",
            reply_markup=InlineKeyboardMarkup(kb_seller),
            parse_mode="Markdown"
        )
        # feedback ke admin
        kb_admin = [[InlineKeyboardButton("🔄 Cek Lagi", callback_data=f"admin_release_final|{deal_id}")]]
        new_message = (
            f"⏳ *Belum ada data pencairan penjual.*\n"
            f"Bot sudah meminta penjual mengisi rekening.\n"
            f"Tekan *Cek Lagi* setelah penjual selesai."
        )

        # Only edit if the message content is different
        if query.message.text != new_message:
            await query.edit_message_text(
                new_message,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(kb_admin)
            )
        else:
            await query.answer("Data pencairan masih belum ada, tunggu seller mengisi terlebih dahulu.", show_alert=True)
        return

    # jika payout ada → tampilkan ringkasan dan tombol eksekusi
    if payout["method"] == "BANK":
        summary = (
            f"🏦 *Bank:* {payout['bank_name']}\n"
            f"🔢 *No. Rekening:* `{payout['account_number']}`\n"
            f"👤 *Nama:* {payout['account_name']}"
        )
    else:
        summary = (
            f"📱 *E-Wallet:* {payout['ewallet_provider']}\n"
            f"🔢 *No.:* `{payout['ewallet_number']}`"
        )
    if payout["note"]:
        summary += f"\n📝 *Catatan:* {payout['note']}"

    kb = [[InlineKeyboardButton("✅ Konfirmasi Cairkan", callback_data=f"admin_release_execute|{deal_id}")]]
    new_message = (
        f"🧾 *Preview Pencairan* `{deal_id}`\n"
        f"📦 {title}\n"
        f"💰 {format_rupiah(amount)}\n\n"
        f"{summary}\n\n"
        f"Jika data sudah benar, klik *Konfirmasi Cairkan*."
    )

    # Only edit if the message content is different
    if query.message.text != new_message:
        await query.edit_message_text(
            new_message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    else:
        await query.answer("Data pencairan sudah ditampilkan di atas.", show_alert=True)

# ADMIN: Eksekusi rilis dana setelah preview
async def admin_release_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    deal_id = query.data.split("|")[1]

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT buyer_id, seller_id, title, amount FROM deals WHERE id=%s", (deal_id,))
        row = cur.fetchone()
        if not row:
            await query.edit_message_text("❌ Transaksi tidak ditemukan.")
            return

        buyer_id, seller_id, title, amount = row

        cur.execute("UPDATE deals SET status='COMPLETED' WHERE id=%s", (deal_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error in admin_release_execute: {e}")
        await query.edit_message_text("❌ Terjadi kesalahan saat mengeksekusi pencairan.")
        return
    finally:
        cur.close()
        from db_postgres import return_connection
        return_connection(conn)


    await query.edit_message_text(
        f"✅ *Dana Rekber* `{deal_id}` *berhasil dirilis ke seller*\n\n"
        f"🎉 Transaksi selesai!",
        parse_mode="Markdown"
    )

    # (Notifikasi rating ke buyer & seller – pakai blok yang sama seperti sebelumnya)
    buyer_keyboard = [
        [InlineKeyboardButton("⭐ Berikan Ulasan (1)", callback_data=f"rate|{deal_id}|1"),
         InlineKeyboardButton("⭐⭐ Berikan Ulasan (2)", callback_data=f"rate|{deal_id}|2")],
        [InlineKeyboardButton("⭐⭐⭐ Berikan Ulasan (3)", callback_data=f"rate|{deal_id}|3"),
         InlineKeyboardButton("⭐⭐⭐⭐ Berikan Ulasan (4)", callback_data=f"rate|{deal_id}|4")],
        [InlineKeyboardButton("⭐⭐⭐⭐⭐ Berikan Ulasan (5)", callback_data=f"rate|{deal_id}|5")],
        [InlineKeyboardButton("📝 Kirim Testimoni", callback_data=f"send_testimoni_menu|{deal_id}")]
    ]
    await context.bot.send_message(
        buyer_id,
        f"🎉 *Selamat! Rekber* `{deal_id}` *telah selesai*\n\n"
        f"✅ Dana telah berhasil dirilis ke penjual\n"
        f"🙏 Terima kasih telah menggunakan REKBER-BOT by Nexo\n\n"
        f"💬 Bagaimana pengalaman transaksi Anda dengan penjual?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buyer_keyboard)
    )

    seller_keyboard = [
        [InlineKeyboardButton("⭐ Berikan Ulasan (1)", callback_data=f"rate|{deal_id}|1"),
         InlineKeyboardButton("⭐⭐ Berikan Ulasan (2)", callback_data=f"rate|{deal_id}|2")],
        [InlineKeyboardButton("⭐⭐⭐ Berikan Ulasan (3)", callback_data=f"rate|{deal_id}|3"),
         InlineKeyboardButton("⭐⭐⭐⭐ Berikan Ulasan (4)", callback_data=f"rate|{deal_id}|4")],
        [InlineKeyboardButton("⭐⭐⭐⭐⭐ Berikan Ulasan (5)", callback_data=f"rate|{deal_id}|5")],
        [InlineKeyboardButton("📝 Kirim Testimoni", callback_data=f"send_testimoni_menu|{deal_id}")]
    ]
    await context.bot.send_message(
        seller_id,
        f"🎉 *Selamat! Rekber* `{deal_id}` *telah selesai*\n\n"
        f"💰 Dana sebesar {format_rupiah(amount)} telah dirilis ke Anda\n"
        f"🙏 Terima kasih telah menggunakan REKBER-BOT by Nexo\n\n"
        f"💬 Bagaimana pengalaman transaksi Anda dengan pembeli?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(seller_keyboard)
    )

    log_action(deal_id, query.from_user.id, "ADMIN", "FINAL_RELEASE", "Admin melepaskan dana final ke seller")


# ADMIN: Konfirmasi payout dan selesaikan transaksi
async def admin_confirm_payout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    deal_id = query.data.split("|")[1]

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT buyer_id, seller_id, title, amount FROM deals WHERE id=%s", (deal_id,))
        row = cur.fetchone()

        if not row:
            await query.edit_message_text("❌ Transaksi tidak ditemukan.")
            return

        # Properly extract values from the row
        buyer_id = row['buyer_id']
        seller_id = row['seller_id']
        title = row['title']
        amount = int(row['amount'])

        # Update status ke COMPLETED
        cur.execute("UPDATE deals SET status='COMPLETED' WHERE id=%s", (deal_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error in admin_confirm_payout: {e}")
        await query.edit_message_text("❌ Terjadi kesalahan saat konfirmasi payout.")
        return
    finally:
        cur.close()
        from db_postgres import return_connection
        return_connection(conn)


    await query.edit_message_text(
        f"✅ *Transaksi* `{deal_id}` *berhasil diselesaikan!*\n\n"
        f"💰 Dana telah dikonfirmasi untuk dicairkan ke seller.",
        parse_mode="Markdown"
    )

    # Ambil username buyer & seller dengan error handling
    try:
        buyer_chat = await context.bot.get_chat(buyer_id)
        buyer_username = "@" + buyer_chat.username if buyer_chat.username else buyer_chat.first_name
    except Exception as e:
        logger.warning(f"Cannot get buyer chat info for buyer_id {buyer_id}: {e}")
        buyer_username = f"User {buyer_id}"

    try:
        seller_chat = await context.bot.get_chat(seller_id)
        seller_username = "@" + seller_chat.username if seller_chat.username else seller_chat.first_name
    except Exception as e:
        logger.warning(f"Cannot get seller chat info for seller_id {seller_id}: {e}")
        seller_username = f"User {seller_id}"

    # Notifikasi ke buyer dengan tombol rating
    buyer_keyboard = [
        [InlineKeyboardButton("⭐ Rating (1)", callback_data=f"rate|{deal_id}|1"),
         InlineKeyboardButton("⭐⭐ Rating (2)", callback_data=f"rate|{deal_id}|2")],
        [InlineKeyboardButton("⭐⭐⭐ Rating (3)", callback_data=f"rate|{deal_id}|3"),
         InlineKeyboardButton("⭐⭐⭐⭐ Rating (4)", callback_data=f"rate|{deal_id}|4")],
        [InlineKeyboardButton("⭐⭐⭐⭐⭐ Rating (5)", callback_data=f"rate|{deal_id}|5")],
        [InlineKeyboardButton("📝 Kirim Testimoni", callback_data=f"send_testimoni_menu|{deal_id}")]
    ]

    try:
        await context.bot.send_message(
            chat_id=buyer_id,
            text=f"🎉 <b>Selamat! Rekber {deal_id} telah selesai!</b>\n\n"
                 f"✅ Transaksi telah berhasil diselesaikan\n"
                 f"👨‍💼 <b>Penjual:</b> {seller_username}\n"
                 f"📦 <b>Produk:</b> {title}\n"
                 f"💰 <b>Total:</b> {format_rupiah(amount)}\n\n"
                 f"🙏 Terima kasih telah menggunakan REKBER-BOT by Nexo\n\n"
                 f"💬 Bagaimana pengalaman transaksi Anda dengan penjual?",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(buyer_keyboard)
        )
    except Exception as e:
        logger.warning(f"Cannot send completion message to buyer {buyer_id}: {e}")

    # Notifikasi ke seller dengan tombol rating
    seller_keyboard = [
        [InlineKeyboardButton("⭐ Rating (1)", callback_data=f"rate|{deal_id}|1"),
         InlineKeyboardButton("⭐⭐ Rating (2)", callback_data=f"rate|{deal_id}|2")],
        [InlineKeyboardButton("⭐⭐⭐ Rating (3)", callback_data=f"rate|{deal_id}|3"),
         InlineKeyboardButton("⭐⭐⭐⭐ Rating (4)", callback_data=f"rate|{deal_id}|4")],
        [InlineKeyboardButton("⭐⭐⭐⭐⭐ Rating (5)", callback_data=f"rate|{deal_id}|5")],
        [InlineKeyboardButton("📝 Kirim Testimoni", callback_data=f"send_testimoni_menu|{deal_id}")]
    ]

    try:
        await context.bot.send_message(
            chat_id=seller_id,
            text=f"🎉 <b>Selamat! Rekber {deal_id} telah selesai!</b>\n\n"
                 f"💰 Dana sebesar {format_rupiah(amount)} telah dikonfirmasi untuk dicairkan\n"
                 f"👤 <b>Pembeli:</b> {buyer_username}\n"
                 f"📦 <b>Produk:</b> {title}\n\n"
                 f"🙏 Terima kasih telah menggunakan REKBER-BOT by Nexo\n\n"
                 f"💬 Bagaimana pengalaman transaksi Anda dengan pembeli?",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(seller_keyboard)
        )
    except Exception as e:
        logger.warning(f"Cannot send completion message to seller {seller_id}: {e}")

    log_action(deal_id, query.from_user.id, "ADMIN", "CONFIRM_PAYOUT", "Admin konfirmasi payout dan selesaikan transaksi")


# TOLAK DANA
async def rekber_admin_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin handler untuk menolak pembayaran"""
    query = update.callback_query
    await query.answer()
    deal_id = query.data.split("|")[1]

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT buyer_id, seller_id, title FROM deals WHERE id = %s", (deal_id,))
        row = cur.fetchone()

        if not row:
            await query.edit_message_text("❌ Transaksi tidak ditemukan.")
            return

        buyer_id = row['buyer_id']
        seller_id = row['seller_id']
        title = row['title']

        # Update status ke PENDING_FUNDING (buyer harus transfer ulang)
        cur.execute("UPDATE deals SET status = %s WHERE id = %s", ("PENDING_FUNDING", deal_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error in rekber_admin_reject: {e}")
        await query.edit_message_text("❌ Terjadi kesalahan saat menolak pembayaran.")
        return
    finally:
        cur.close()
        from db_postgres import return_connection
        return_connection(conn)

    await query.edit_message_text(f"❌ Pembayaran untuk transaksi {deal_id} ditolak.")

    # Notif ke pembeli dengan instruksi
    await context.bot.send_message(
        chat_id=buyer_id,
        text=f"❌ <b>Pembayaran Ditolak</b>\n\n"
             f"Pembayaran untuk transaksi <b>{title}</b> ditolak oleh admin.\n\n"
             f"Kemungkinan alasan:\n"
             f"• Jumlah transfer tidak sesuai\n"
             f"• Transfer ke rekening yang salah\n"
             f"• Bukti transfer tidak jelas\n\n"
             f"Silakan hubungi admin: @Nexoitsme untuk klarifikasi dan transfer ulang dengan benar.",
        parse_mode="HTML"
    )

    # Notif ke penjual
    await context.bot.send_message(
        chat_id=seller_id,
        text=f"⚠️ Pembayaran untuk transaksi <b>{title}</b> ditolak oleh admin. Menunggu pembeli melakukan pembayaran ulang.",
        parse_mode="HTML"
    )


# ADMIN: RESOLVE DISPUTE (Release Dana ke Seller)
async def rekber_admin_release(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    deal_id = query.data.split("|")[1]

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT buyer_id, seller_id FROM deals WHERE id=%s", (deal_id,))
        row = cur.fetchone()

        if not row:
            await query.edit_message_text("❌ Transaksi tidak ditemukan.")
            return

        buyer_id, seller_id = row

        # update status → RELEASED
        cur.execute("UPDATE deals SET status='RELEASED' WHERE id=%s", (deal_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error in rekber_admin_release: {e}")
        await query.edit_message_text("❌ Terjadi kesalahan saat merilis dana.")
        return
    finally:
        cur.close()
        from db_postgres import return_connection
        return_connection(conn)


    await query.edit_message_text(f"✅ Admin memutuskan dana Rekber {deal_id} dirilis ke penjual.")

    # notif ke kedua pihak
    await context.bot.send_message(seller_id, f"🎉 Dana escrow Rekber {deal_id} dirilis ke kamu oleh admin.")
    await context.bot.send_message(buyer_id, f"⚠️ Admin memutuskan dana Rekber {deal_id} dirilis ke penjual.")


# ADMIN: RESOLVE DISPUTE (Refund ke Buyer)
async def rekber_admin_refund(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    deal_id = query.data.split("|")[1]

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT buyer_id, seller_id FROM deals WHERE id=%s", (deal_id,))
        row = cur.fetchone()

        if not row:
            await query.edit_message_text("❌ Transaksi tidak ditemukan.")
            return

        buyer_id, seller_id = row

        # update status → REFUNDED
        cur.execute("UPDATE deals SET status='REFUNDED' WHERE id=%s", (deal_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error in rekber_admin_refund: {e}")
        await query.edit_message_text("❌ Terjadi kesalahan saat mengembalikan dana.")
        return
    finally:
        cur.close()
        from db_postgres import return_connection
        return_connection(conn)


    await query.edit_message_text(f"💸 Admin memutuskan dana Rekber {deal_id} dikembalikan ke pembeli.")

    # notif ke kedua pihak
    await context.bot.send_message(buyer_id, f"💸 Dana escrow Rekber {deal_id} dikembalikan ke kamu oleh admin.")
    await context.bot.send_message(seller_id, f"⚠️ Admin memutuskan dana Rekber {deal_id} dikembalikan ke pembeli.")