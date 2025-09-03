from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from handlers.rekber import rekber_join  # import fungsi join
from telegram.helpers import escape_markdown

# Assuming 'title' is defined elsewhere or passed as an argument.
# If 'title' is not available, this line might cause an error.
# For the purpose of this fix, we'll assume it's handled correctly in the context
# where this file is used. If not, it would need to be defined or removed.
# For demonstration, let's assume a placeholder if it's not critical for the fix:
# title = "Default Title"
# title_safe = escape_markdown(title, version=2)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args and context.args[0].startswith("rekber_"):
        # Mode: join lewat invite link
        from handlers.rekber import rekber_join
        await rekber_join(update, context)
        return   # ⬅️ biar gak lanjut ke menu
    else:
        # Mode: start normal tanpa argumen
        welcome_text = (
            "🎆 *Selamat datang di REKBER-BOT by Nexo!*\n\n"
            "🚀 *Buat Rekber* - Mulai transaksi aman sebagai pembeli atau penjual\n"
            "📄 *Riwayat Rekber* - Lihat history transaksi Anda\n"
            "📝 *Kirim Testimoni* - Bagikan pengalaman transaksi Anda\n"
            "🔍 *Cek Testimoni* - Lihat testimoni pengguna lain\n"
            "📜 *Panduan* - Syarat, ketentuan & biaya admin\n\n"
            "🔒 *Transaksi aman dengan jaminan Rekber*"
        )

        keyboard = [
            [InlineKeyboardButton("🚀 Buat Rekber", callback_data="rekber_create_role")],
            [InlineKeyboardButton("📄 Riwayat Rekber", callback_data="rekber_user_history"),
            InlineKeyboardButton("📜 Panduan", callback_data="rekber_panduan")],
            [InlineKeyboardButton("📝 Kirim Testimoni", callback_data="send_testimoni_menu"),
             InlineKeyboardButton("🔍 Cek Testimoni", url="https://t.me/testirekberbotNEXO")],

        ]
        await update.message.reply_text(
            welcome_text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

#========== rekber_create_role ==========
async def rekber_create_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    create_text = (
        "🎯 **PILIH PERAN ANDA DALAM TRANSAKSI**\n\n"

        "📦 **SEBAGAI PENJUAL** (Saya yang menjual)\n"
        "• Anda memiliki barang/jasa yang akan dijual\n"
        "• Buyer akan transfer dana ke admin terlebih dahulu\n"
        "• Anda kirim barang setelah dana terverifikasi\n"
        "• Dana dilepas setelah buyer konfirmasi\n\n"

        "🛒 **SEBAGAI PEMBELI** (Saya yang membeli)\n" 
        "• Anda ingin membeli barang/jasa dari seseorang\n"
        "• Anda transfer dana ke admin untuk keamanan\n"
        "• Seller kirim barang setelah dana aman\n"
        "• Anda konfirmasi penerimaan untuk release dana\n\n"

        "💡 *Tips: Pilih sesuai dengan posisi Anda dalam transaksi ini*"
    )

    keyboard = [
        [
            InlineKeyboardButton("📦 Saya Penjual", callback_data="rekber_create_seller"),
            InlineKeyboardButton("🛒 Saya Pembeli", callback_data="rekber_create_buyer")
        ],
        [InlineKeyboardButton("❓ Bantuan", callback_data="help_create_role"),
         InlineKeyboardButton("🏠 Kembali", callback_data="rekber_main_menu")]
    ]

    await query.edit_message_text(
        create_text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

#========== PANDUAN ==========
#========== rekber_panduan ==========
async def rekber_panduan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await show_panduan_page(query, page=1)


async def show_panduan_page(query, page: int):
    if page == 1:
        text = (
            "📜 *Panduan Rekber Bot* (1/4)\n\n"
            "🔒 *APA ITU REKBER?*\n\n"
            "Rekber (Rekening Bersama) adalah sistem transaksi aman dengan perantara admin.\n"
            "Dana pembeli dititipkan ke admin dulu, lalu dilepas ke penjual setelah barang/jasa diterima.\n\n"
            "⚡ *ALUR TRANSAKSI:*\n"
            "```bash\n"
            "[1] Pembeli/penjual memulai rekber\n"
            "[2] Bot membuat link undangan untuk lawan transaksi\n"
            "[3] Lawan transaksi join dengan link\n"
            "[4] Pembeli transfer dana 👉 admin verifikasi\n"
            "[5] Penjual kirim barang/jasa\n"
            "[6] Pembeli konfirmasi barang diterima\n"
            "[7] Admin melepas dana ke seller\n"
            "```\n"
            "🔐 *Keamanan & Transparansi* | ⚖️ *Adil* | 🚀 *Cepat*\n"
            "━━━━━━━━━━━━ NEXT ▷▷ BIAYA ADMIN\n"

        )
        keyboard = [[InlineKeyboardButton("➡️ Berikutnya", callback_data="rekber_panduan_page_2")]]

    elif page == 2:
        text = (
            "📜 *Panduan Rekber Bot* (2/4)\n\n"

            "💻 *BIAYA ADMIN REKBER*\n\n"

            "```bash\n"
            "[TIER 1]  <= Rp50.000               :: Rp2.000\n"
            "[TIER 2]  <= Rp50.001 - 100.000  :: Rp3.000\n"
            "[TIER 3]  Rp100.001 - 500.000     :: Rp5.000\n"
            "[TIER 4]  Rp500.001 - 1.000.000  :: 1% dari nominal\n"
            "[TIER 5]  Rp1.000.001-5.000.000  :: 0.7% dari nominal\n"
            "[TIER 6]  > Rp5.000.000             :: 0.5% dari nominal\n"
            "```\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚡ *Note:* biaya admin dihitung otomatis oleh sistem.\n"
            "━━━━━━━━━━━━━━ NEXT ▷▷ PAYMENT\n"
            )





        keyboard = [[
            InlineKeyboardButton("⬅️ Sebelumnya", callback_data="rekber_panduan_page_1"),
            InlineKeyboardButton("➡️ Berikutnya", callback_data="rekber_panduan_page_3")
        ]]

    elif page == 3:
        text = (
            "📜 *Panduan Rekber Bot* (3/4)\n\n"

            "🏦 *INFORMASI PEMBAYARAN*\n\n"

            "```\n"
            "[DANA]      : 082119299186  | Muhammad Abdu Wafaqih\n"
            "[GoPay]     : 082119299186  | Wafaqih\n"
            "[SeaBank]  : 901251081230  | Muhammad Abdu Wafaqih\n"
            "[Bank Jago]: 103536428831  | Muhammad Abdu Wafaqih\n"
            "[QRIS]       : (sementara belum tersedia)\n"
            "```\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📩 Kirim bukti transfer ke admin 👉 @Nexoitsme\n"
            "━━━━━━━━━━━━━━━━ NEXT ▷▷ S&K\n"

        )
        keyboard = [[
            InlineKeyboardButton("⬅️ Sebelumnya", callback_data="rekber_panduan_page_2"),
            InlineKeyboardButton("➡️ Berikutnya", callback_data="rekber_panduan_page_4")
        ]]

    elif page == 4:
        text = (
            "📜 *Panduan Rekber Bot* (4/4)\n\n"
            "🗒️ *Syarat & Ketentuan Rekber via Bot Telegram*\n\n"
            "1. *Definisi*\n"
                "• Rekber (rekening bersama) adalah sistem perantara transaksi antara penjual dan pembeli melalui Admin Rekber untuk meningkatkan keamanan transaksi.\n"
                "• Bot hanya sebagai media otomatisasi, keputusan akhir tetap berada di Admin Rekber.\n\n"

                "2. *Aturan Mediasi*\n"
                "• Mediasi dilakukan jika ada perbedaan klaim antara pembeli & penjual.\n"
                "• Admin Rekber berhak meminta bukti (screenshot, resi, rekaman, dsb).\n"
                "• Hasil keputusan mediasi bersifat *final & mengikat*.\n\n"

                "3. *Biaya Layanan*\n"
                "• Setiap transaksi melalui Rekber dikenakan biaya administrasi sesuai ketentuan yang berlaku.\n"
                "• Biaya ditanggung oleh pembeli/penjual sesuai kesepakatan awal.\n\n"

                "4. *Ketentuan Umum*\n"
                "• Admin Rekber tidak bertanggung jawab atas kualitas barang/jasa.\n"
                "• Admin hanya menjamin keamanan alur dana selama melalui Rekber.\n"
                "• Dilarang menggunakan Rekber untuk transaksi ilegal (narkoba, judi, pornografi, penipuan, dll).\n"
                "• Dengan menggunakan bot ini, pembeli & penjual dianggap telah membaca dan menyetujui seluruh S&K.\n"
        )
        keyboard = [[
            InlineKeyboardButton("⬅️ Sebelumnya", callback_data="rekber_panduan_page_3"),
            InlineKeyboardButton("🏠 Kembali ke Menu", callback_data="rekber_main_menu")
        ]]
    else:
        # Default case for invalid page numbers
        text = "❌ Halaman tidak ditemukan."
        keyboard = [[InlineKeyboardButton("🏠 Kembali ke Menu", callback_data="rekber_main_menu")]]

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def rekber_main_menu(update_or_query, context: ContextTypes.DEFAULT_TYPE):
    if hasattr(update_or_query, "callback_query"):
        # kalau dipanggil dari tombol
        query = update_or_query.callback_query
        await query.answer()
        target = query.edit_message_text
    else:
        # kalau dipanggil dari /start
        target = update_or_query.message.reply_text

    welcome_text = (
        "🎆 *Selamat datang di REKBER-BOT by Nexo!*\n\n"
        "🚀 *Buat Rekber* - Mulai transaksi aman sebagai pembeli atau penjual\n"
        "📄 *Riwayat Rekber* - Lihat history transaksi Anda\n"
        "📝 *Kirim Testimoni* - Bagikan pengalaman transaksi Anda\n"
        "🔍 *Cek Testimoni* - Lihat testimoni pengguna lain\n"
        "📜 *Panduan* - Syarat, ketentuan & biaya admin\n\n"
        "🔒 *Transaksi aman dengan jaminan escrow*"
    )

    keyboard = [
        [InlineKeyboardButton("🚀 Buat Rekber", callback_data="rekber_create_role")],
        [InlineKeyboardButton("📄 Riwayat Rekber", callback_data="rekber_history_menu")],
        [InlineKeyboardButton("📝 Kirim Testimoni", callback_data="send_testimoni_menu"),
         InlineKeyboardButton("🔍 Cek Testimoni", url="https://t.me/RekberTestimoni")],
        [InlineKeyboardButton("📜 Panduan", callback_data="rekber_panduan")]
    ]

    await target(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )