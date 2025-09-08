from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from db_sqlite import get_connection, log_action
import html
import logging

logger = logging.getLogger(__name__)

# Conversation states
WAITING_COMMENT = 1

async def handle_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle rating submission"""
    query = update.callback_query
    await query.answer()

    logger.info(f"Rating callback data: {query.data}")

    data_parts = query.data.split("|")
    if len(data_parts) < 3:
        logger.error(f"Invalid rating data format: {query.data}")
        await query.edit_message_text("❌ Data rating tidak valid.")
        return

    deal_id = data_parts[1]
    rating = int(data_parts[2])
    user_id = query.from_user.id

    logger.info(f"Processing rating: deal_id={deal_id}, rating={rating}, user_id={user_id}")

    # Save rating to database
    conn = get_connection()
    cur = conn.cursor()

    # Check if user already rated this deal
    cur.execute("SELECT id FROM ratings WHERE deal_id=? AND user_id=?", (deal_id, user_id))
    existing = cur.fetchone()

    if existing:
        await query.edit_message_text("❌ Anda sudah memberikan rating untuk transaksi ini.")
        conn.close()
        return

    # Insert rating
    cur.execute(
        "INSERT INTO ratings (deal_id, user_id, rating, created_at) VALUES (?,?,?,'now')",
        (deal_id, user_id, rating)
    )
    rating_id = cur.lastrowid
    conn.commit()
    conn.close()

    # Store rating_id in user_data for later use
    if context.user_data is None:
        context.user_data = {}
    context.user_data['current_rating_id'] = rating_id

    # Log the action
    log_action(deal_id, user_id, "USER", "RATE", f"Rating: {rating}/5")

    # JANGAN kirim ke channel dulu - tunggu sampai user pilih komentar/skip
    # Show options for comment
    keyboard = [
        [InlineKeyboardButton("💬 Tambah Komentar", callback_data=f"add_comment|{rating_id}")],
        [InlineKeyboardButton("⏭️ Lewati", callback_data=f"skip_comment|{rating_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    stars = "⭐" * rating
    await query.edit_message_text(
        f"🎉 *Rating Berhasil Disimpan!* 🎉\n\n"
        f"┏━━━━━━━━━━━━━━━━━━━━┓\n"
        f"┃ 🌟 *Rating Anda:* {stars}    ┃\n"
        f"┃ 📊 *Skor:* {rating}/5 ⭐          ┃\n"
        f"┗━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"💭 *Ingin berbagi pengalaman lebih detail?*\n"
        f"Komentar Anda akan membantu pengguna lain! 🤝",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def ask_for_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User chooses to add comment"""
    query = update.callback_query
    await query.answer()

    try:
        rating_id = query.data.split("|")[1]
        if context.user_data is None:
            context.user_data = {}
        context.user_data['current_rating_id'] = rating_id

        await query.edit_message_text(
            f"✍️ *Ceritakan Pengalaman Anda!* ✍️\n\n"
            f"┏━━━━━━━━━━━━━━━━━━━━┓\n"
            f"┃ 📝 *TULIS ULASAN ANDA*    ┃\n"
            f"┗━━━━━━━━━━━━━━━━━━━━┛\n\n"
            f"💡 *Contoh yang baik:*\n"
            f"• 🚀 Penjual responsif dan ramah\n"
            f"• ✅ Barang sesuai deskripsi\n"
            f"• 📦 Pengiriman cepat dan aman\n"
            f"• 💯 Recommended seller!\n\n"
            f"🎯 *Ketik ulasan Anda di bawah ini:*",
            parse_mode="Markdown"
        )

        return WAITING_COMMENT

    except (IndexError, ValueError):
        await query.edit_message_text("❌ Data rating tidak valid.")
        return ConversationHandler.END

async def receive_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive and save comment"""
    comment = update.message.text
    rating_id = context.user_data.get('current_rating_id') if context.user_data else None

    if not rating_id:
        await update.message.reply_text("❌ Session expired. Silakan coba lagi.")
        return ConversationHandler.END

    # Update rating with comment
    conn = get_connection()
    cur = conn.cursor()
    
    # Update comment first
    cur.execute("UPDATE ratings SET comment=? WHERE id=?", (comment, rating_id))
    
    # Get rating details for testimoni
    cur.execute("""
        SELECT deal_id, rating, user_id 
        FROM ratings 
        WHERE id=?
    """, (rating_id,))
    rating_data = cur.fetchone()
    conn.commit()
    conn.close()

    # Cek apakah rating_data ada
    if not rating_data:
        await update.message.reply_text("❌ Data rating tidak ditemukan. Silakan coba lagi.")
        context.user_data.clear()
        return ConversationHandler.END

    # Extract data - sekarang aman karena sudah dicek
    deal_id, rating_value, user_id = rating_data
    stars = "⭐" * rating_value

    await update.message.reply_text(
        f"🎊 *Ulasan Berhasil Tersimpan\\!* 🎊\n\n"
        f"┏━━━━━━━━━━━━━━━━━━━━┓\n"
        f"┃ ✅ *STATUS:* Berhasil       ┃\n"
        f"┃ 📤 *DIKIRIM KE:* Testimoni  ┃\n"
        f"┃ 🌟 *RATING:* {stars}         ┃\n"
        f"┗━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"🙏 *Terima kasih atas kontribusi Anda\\!*\n"
        f"💪 Ulasan Anda membantu komunitas berkembang",
        parse_mode="MarkdownV2"
    )

    # Post to testimoni channel
    user = update.effective_user
    username = "@" + user.username if user.username else user.first_name

    from config import TESTIMONI_CHANNEL

    from telegram.helpers import escape_markdown
    safe_username = escape_markdown(username, version=2)
    safe_deal_id = escape_markdown(deal_id, version=2)
    safe_comment = escape_markdown(comment, version=2)
    
    testimoni_text = (
        f"🌟 *TESTIMONI REKBER*\n\n"
        f"👤 {safe_username} memberikan ulasan {stars} untuk transaksi `{safe_deal_id}`\n\n"
        f"💬 *Komentar:*\n"
        f"❝ _{safe_comment}_ ❞\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🤖 *JASAREKBER_TELEBOT*"
    )

    try:
        await context.bot.send_message(
            chat_id=TESTIMONI_CHANNEL,
            text=testimoni_text,
            parse_mode="MarkdownV2"
        )
    except Exception as e:
        print(f"Error sending to testimoni channel: {e}")

    # Clear user data
    context.user_data.clear()
    return ConversationHandler.END

async def skip_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip comment addition"""
    query = update.callback_query
    await query.answer()

    # Get rating ID from callback data (format: skip_comment|rating_id)
    data_parts = query.data.split("|")
    if len(data_parts) > 1:
        rating_id = data_parts[1]
    else:
        # Fallback ke user_data
        rating_id = context.user_data.get('current_rating_id') if context.user_data else None
        
    if not rating_id:
        await query.edit_message_text("❌ Session expired. Silakan coba lagi.")
        return ConversationHandler.END

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT deal_id, rating, user_id 
        FROM ratings 
        WHERE id=?
    """, (rating_id,))
    rating_data = cur.fetchone()
    conn.close()

    # Post to testimoni channel without comment
    if rating_data:
        deal_id, rating_value, user_id = rating_data
            
        user = query.from_user
        username = "@" + user.username if user.username else user.first_name
        stars = "⭐" * rating_value

        from config import TESTIMONI_CHANNEL
        from telegram.helpers import escape_markdown
        safe_username = escape_markdown(username, version=2)
        safe_deal_id = escape_markdown(deal_id, version=2)
        
        testimoni_text = (
            f"🌟 *TESTIMONI REKBER*\n\n"
            f"👤 {safe_username} memberikan ulasan {stars} untuk transaksi `{safe_deal_id}`\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🤖 *JASAREKBER_TELEBOT*"
        )

        try:
            await context.bot.send_message(
                chat_id=TESTIMONI_CHANNEL,
                text=testimoni_text,
                parse_mode="MarkdownV2"
            )
        except Exception as e:
            print(f"Error sending to testimoni channel: {e}")

        await query.edit_message_text(
            "✅ *Rating berhasil disimpan\\!*\n\n"
            "Terima kasih atas feedback Anda\\.",
            parse_mode="MarkdownV2"
        )
    else:
        await query.edit_message_text("❌ Data rating tidak ditemukan.")

    # Clear user data
    if context.user_data:
        context.user_data.clear()
        
    return ConversationHandler.END

async def cancel_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel rating process"""
    await update.message.reply_text("❌ Proses rating dibatalkan.")
    context.user_data.clear()
    return ConversationHandler.END

# Testimoni handlers
WAITING_TESTIMONI = 2

async def send_testimoni_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show testimoni submission menu"""
    query = update.callback_query
    await query.answer()

    # Handle case where there might not be a deal_id (from main menu)
    data_parts = query.data.split("|")
    if len(data_parts) > 1:
        deal_id = data_parts[1]
        context.user_data['testimoni_deal_id'] = deal_id
    else:
        # For general testimoni from main menu
        context.user_data['testimoni_deal_id'] = None

    await query.edit_message_text(
        f"✨ *KIRIM TESTIMONI* ✨\n\n"
        f"┏━━━━━━━━━━━━━━━━━━━━┓\n"
        f"┃ 🎯 *BAGIKAN PENGALAMAN* ┃\n"
        f"┃ 🤝 *BANTU KOMUNITAS*    ┃\n"
        f"┗━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"📋 *Format yang bisa dikirim:*\n"
        f"• 📝 Testimoni teks\n"
        f"• 📸 Screenshot + caption\n"
        f"• 🖼️ Foto produk + review\n\n"
        f"🎪 *Testimoni akan tampil di channel kami!*\n"
        f"🌟 Bantu calon pembeli/penjual lainnya",
        parse_mode="Markdown"
    )

    return WAITING_TESTIMONI

async def receive_testimoni(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive and forward testimoni to channel"""
    deal_id = context.user_data.get('testimoni_deal_id')
    user = update.effective_user
    username = "@" + user.username if user.username else user.first_name

    from config import TESTIMONI_CHANNEL
    from telegram.helpers import escape_markdown

    # Escape username untuk MarkdownV2
    safe_username = escape_markdown(username, version=2)
    safe_deal_id = escape_markdown(deal_id, version=2) if deal_id else None

    # Format pesan testimoni
    if deal_id:
        testimoni_header = (
            f"🌟 *TESTIMONI REKBER*\n\n"
            f"👤 {safe_username} berbagi pengalaman untuk transaksi `{safe_deal_id}`\n\n"
            f"💬 *Testimoni:*\n"
        )
    else:
        testimoni_header = (
            f"🌟 *TESTIMONI REKBER*\n\n"
            f"👤 {safe_username} berbagi pengalaman transaksi\n\n"
            f"💬 *Testimoni:*\n"
        )

    try:
        footer = (
            f"\n\n━━━━━━━━━━━━━━━\n"
            f"🤖 *JASAREKBER_TELEBOT*"
        )

        if update.message.photo:
            # Testimoni dengan foto
            photo = update.message.photo[-1]  # Ambil resolusi tertinggi
            caption = update.message.caption or ""
            safe_caption = escape_markdown(caption, version=2)
            full_caption = testimoni_header + safe_caption + footer

            await context.bot.send_photo(
                chat_id=TESTIMONI_CHANNEL,
                photo=photo.file_id,
                caption=full_caption,
                parse_mode="MarkdownV2"
            )
        else:
            # Testimoni teks saja
            safe_text = escape_markdown(update.message.text, version=2)
            testimoni_text = testimoni_header + safe_text + footer
            await context.bot.send_message(
                chat_id=TESTIMONI_CHANNEL,
                text=testimoni_text,
                parse_mode="MarkdownV2"
            )

        await update.message.reply_text(
            f"🎉 *TESTIMONI BERHASIL DIKIRIM\\!* 🎉\n\n"
            f"┏━━━━━━━━━━━━━━━━━━━━┓\n"
            f"┃ ✅ *STATUS:* Terkirim       ┃\n"
            f"┃ 📺 *CHANNEL:* Testimoni     ┃\n"
            f"┃ 🌟 *KONTRIBUTOR:* {safe_username} ┃\n"
            f"┗━━━━━━━━━━━━━━━━━━━━┛\n\n"
            f"🙌 *Terima kasih telah berkontribusi\\!*\n"
            f"🚀 Testimoni Anda akan membantu banyak orang",
            parse_mode="MarkdownV2"
        )

    except Exception as e:
        print(f"Error sending testimoni: {e}")
        await update.message.reply_text(
            "❌ Gagal mengirim testimoni\\. Silakan coba lagi atau hubungi admin\\.",
            parse_mode="MarkdownV2"
        )

    # Clear user data
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_testimoni(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel testimoni process"""
    await update.message.reply_text("❌ Pengiriman testimoni dibatalkan.")
    context.user_data.clear()
    return ConversationHandler.END