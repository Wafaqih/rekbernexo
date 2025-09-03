from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

async def help_create_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Helper untuk menjelaskan perbedaan role buyer vs seller"""
    query = update.callback_query
    await query.answer()
    
    help_text = (
        "❓ **BANTUAN: PILIH ROLE**\n\n"
        
        "🤔 **Bingung pilih sebagai apa?**\n\n"
        
        "**PILIH PENJUAL jika:**\n"
        "✅ Kamu punya barang/jasa yang mau dijual\n"
        "✅ Kamu yang menentukan harga\n"
        "✅ Kamu yang akan mengirim barang\n"
        "✅ Contoh: Jual akun game, jasa design, handphone bekas\n\n"
        
        "**PILIH PEMBELI jika:**\n"
        "✅ Kamu mau beli barang/jasa dari orang lain\n"
        "✅ Kamu yang akan bayar\n"
        "✅ Kamu yang akan nerima barang\n"
        "✅ Contoh: Beli jasa website, beli laptop, order design logo\n\n"
        
        "💡 **Tips:** Kalau masih bingung, tanya diri sendiri: *\"Apakah saya yang punya barang atau yang mau beli barang?\"*\n\n"
        
        "🔄 **Keduanya sama amannya** dengan sistem rekber!"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔙 Kembali Pilih Role", callback_data="rekber_create_role")]
    ]
    
    await query.edit_message_text(
        help_text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def help_what_is_rekber(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Helper untuk menjelaskan apa itu rekber"""
    query = update.callback_query
    await query.answer()
    
    help_text = (
        "❓ **APA ITU REKBER (REKENING BERSAMA)?**\n\n"
        
        "🔐 **Rekber adalah sistem transaksi aman** dengan admin sebagai perantara.\n\n"
        
        "📋 **Cara kerja:**\n"
        "1️⃣ Pembeli transfer dana ke admin dulu (tidak ke penjual)\n"
        "2️⃣ Admin konfirmasi dana sudah masuk\n" 
        "3️⃣ Penjual kirim barang/jasa ke pembeli\n"
        "4️⃣ Pembeli konfirmasi barang diterima\n"
        "5️⃣ Admin release dana ke penjual\n\n"
        
        "✅ **Keuntungan:**\n"
        "• Pembeli: Dana aman, barang pasti diterima atau refund\n"
        "• Penjual: Pembayaran dijamin setelah kirim barang\n"
        "• Admin: Mediasi jika ada masalah\n\n"
        
        "💸 **Biaya admin kecil** untuk jaminan keamanan transaksi jutaan rupiah\n\n"
        
        "⚠️ **INGAT:** Jangan transfer langsung ke penjual tanpa rekber!"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_join")]
    ]
    
    await query.edit_message_text(
        help_text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def join_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk membatalkan join"""
    query = update.callback_query
    await query.answer()
    
    cancel_text = (
        "❌ **JOIN DIBATALKAN**\n\n"
        "Tidak jadi bergabung dalam transaksi ini.\n\n"
        "💡 **Tips:** Jika Anda ragu, sebaiknya diskusikan dulu detail barang/jasa dengan lawan transaksi sebelum bergabung.\n\n"
        "🔄 **Ingin coba lagi?** Klik link undangan sekali lagi."
    )
    
    await query.edit_message_text(
        cancel_text,
        parse_mode="Markdown"
    )

async def change_fee_payer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk mengubah fee payer"""
    query = update.callback_query
    await query.answer()
    
    # Kembali ke step pilihan fee payer
    title = context.user_data.get("title", "")
    amount = context.user_data.get("amount", 0)
    admin_fee = context.user_data.get("admin_fee", 0)
    
    fee_preview = (
        "💰 **UBAH PENANGUNG BIAYA ADMIN**\n\n"
        f"📦 **Barang/Jasa:** {title}\n"
        f"💵 **Harga:** Rp {amount:,}\n"
        f"💸 **Biaya Admin:** Rp {admin_fee:,}\n\n"
        
        "👤 **Siapa yang akan menanggung biaya admin?**\n\n"
        
        "🔹 **Ditanggung Pembeli:**\n"
        f"   • Pembeli transfer: Rp {amount + admin_fee:,}\n"
        f"   • Penjual terima: Rp {amount:,}\n\n"
        
        "🔹 **Ditanggung Penjual:**\n"
        f"   • Pembeli transfer: Rp {amount:,}\n"
        f"   • Penjual terima: Rp {amount - admin_fee:,}\n\n"
    )

    keyboard = [
        [InlineKeyboardButton("🛒 Fee ditanggung Pembeli", callback_data="fee_payer|BUYER")],
        [InlineKeyboardButton("📦 Fee ditanggung Penjual", callback_data="fee_payer|SELLER")],
        [InlineKeyboardButton("❌ Batalkan", callback_data="cancel_create")]
    ]
    
    await query.edit_message_text(
        fee_preview,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def get_status_progress_bar(status: str) -> str:
    """Generate progress bar berdasarkan status transaksi"""
    progress_map = {
        "CREATED": "🟢⚪⚪⚪⚪⚪",  # 1/6
        "WAITING_VERIFICATION": "🟢🟢⚪⚪⚪⚪",  # 2/6  
        "FUNDED": "🟢🟢🟢⚪⚪⚪",  # 3/6
        "SHIPPED": "🟢🟢🟢🟢⚪⚪",  # 4/6
        "COMPLETED": "🟢🟢🟢🟢🟢🟢",  # 6/6
        "CANCELLED": "🔴⚪⚪⚪⚪⚪",  # Failed
        "DISPUTED": "🟡🟡🟡🟡🟡⚪",  # Under review
        "REFUNDED": "🔵🔵🔵🔵🔵🔵"  # Refunded
    }
    
    return progress_map.get(status, "⚪⚪⚪⚪⚪⚪")

def get_status_description(status: str) -> tuple[str, str]:
    """Get user-friendly status description dan next action"""
    status_map = {
        "CREATED": (
            "📝 **Menunggu Pembayaran**", 
            "Pembeli perlu transfer dana ke admin"
        ),
        "WAITING_VERIFICATION": (
            "⏳ **Verifikasi Pembayaran**", 
            "Admin sedang memverifikasi transfer"
        ),
        "FUNDED": (
            "💰 **Dana Sudah Aman**", 
            "Penjual bisa mulai kirim barang/jasa"
        ),
        "SHIPPED": (
            "📦 **Barang Dikirim**", 
            "Pembeli perlu konfirmasi setelah terima barang"
        ),
        "COMPLETED": (
            "✅ **Transaksi Selesai**", 
            "Dana sudah dilepas ke penjual"
        ),
        "CANCELLED": (
            "❌ **Transaksi Dibatalkan**", 
            "Transaksi tidak dapat dilanjutkan"
        ),
        "DISPUTED": (
            "⚖️ **Dalam Mediasi**", 
            "Admin sedang menangani dispute"
        ),
        "REFUNDED": (
            "↩️ **Dana Dikembalikan**", 
            "Refund sudah diproses"
        )
    }
    
    return status_map.get(status, ("❓ Status Tidak Dikenal", "Hubungi admin"))

def format_transaction_summary(deal_data: dict, user_role: str = None) -> str:
    """Format ringkasan transaksi yang user-friendly"""
    status_desc, next_action = get_status_description(deal_data['status'])
    progress = get_status_progress_bar(deal_data['status'])
    
    summary = f"""
📊 **RINGKASAN TRANSAKSI**

📋 **ID:** `{deal_data['id']}`
📦 **Barang/Jasa:** {deal_data['title']}
💰 **Nilai:** {deal_data['amount']:,}

{progress}
{status_desc}

🎯 **Langkah selanjutnya:** {next_action}
"""
    
    if user_role:
        summary += f"\n🔄 **Peran Anda:** {user_role}"
    
    return summary