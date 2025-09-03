import asyncio
import logging
from datetime import datetime, timedelta
from telegram.ext import ContextTypes
from db_postgres import get_connection
from utils import format_rupiah
import config

logger = logging.getLogger(__name__)

class NotificationManager:
    def __init__(self, bot):
        self.bot = bot
        self.reminder_tasks = {}
    
    async def send_payment_reminder(self, deal_id: str, buyer_id: int):
        """Kirim reminder pembayaran ke buyer"""
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
            SELECT title, amount, admin_fee, admin_fee_payer, created_at 
            FROM deals 
            WHERE id = ? AND status = 'CREATED'
            """, (deal_id,))
            
            deal = cur.fetchone()
            cur.close()
            from db_postgres import return_connection
            return_connection(conn)
            
            if not deal:
                return
            
            title, amount, admin_fee, admin_fee_payer, created_at = deal
            
            # Hitung total yang harus dibayar
            if admin_fee_payer == 'BUYER':
                total_to_pay = amount + admin_fee
            else:
                total_to_pay = amount
            
            # Hitung berapa lama deal sudah dibuat
            time_created = datetime.now() - created_at
            hours_passed = int(time_created.total_seconds() // 3600)
            
            reminder_text = f"""
⏰ **REMINDER PEMBAYARAN**

📋 **Deal ID:** `{deal_id}`
🏷️ **Judul:** {title}
💰 **Total Pembayaran:** {format_rupiah(total_to_pay)}

⚠️ Deal ini sudah dibuat {hours_passed} jam yang lalu dan masih menunggu pembayaran.

📱 **Informasi Pembayaran:**
• DANA: 082119299186 (Muhammad Abdu Wafaqih)
• GoPay: 082119299186 (Wafaqih)  
• SeaBank: 901251081230 (Muhammad Abdu Wafaqih)
• Bank Jago: 103536428831 (Muhammad Abdu Wafaqih)

📩 Setelah transfer, kirim bukti ke admin @Nexoitsme

⏳ Deal akan otomatis dibatalkan jika tidak ada pembayaran dalam 24 jam.
"""
            
            await self.bot.send_message(
                chat_id=buyer_id,
                text=reminder_text,
                parse_mode="Markdown"
            )
            
        except Exception as e:
            logger.error(f"Error sending payment reminder: {e}")
    
    async def send_completion_reminder(self, deal_id: str, buyer_id: int):
        """Kirim reminder konfirmasi penerimaan barang ke buyer"""
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
            SELECT title, seller_id 
            FROM deals 
            WHERE id = ? AND status = 'SHIPPED'
            """, (deal_id,))
            
            deal = cur.fetchone()
            cur.close()
            from db_postgres import return_connection
            return_connection(conn)
            
            if not deal:
                return
            
            title, seller_id = deal
            
            reminder_text = f"""
📦 **REMINDER KONFIRMASI BARANG**

📋 **Deal ID:** `{deal_id}`
🏷️ **Judul:** {title}

✅ Penjual sudah mengirim barang. Apakah barang sudah Anda terima?

🔍 **Langkah Selanjutnya:**
1. Cek barang yang diterima
2. Konfirmasi jika sesuai dengan deskripsi
3. Jika ada masalah, segera laporkan dispute

⚠️ Jika tidak ada konfirmasi dalam 3x24 jam, dana akan otomatis dilepas ke penjual.

Gunakan /rekber_active untuk melihat dan mengonfirmasi transaksi ini.
"""
            
            await self.bot.send_message(
                chat_id=buyer_id,
                text=reminder_text,
                parse_mode="Markdown"
            )
            
        except Exception as e:
            logger.error(f"Error sending completion reminder: {e}")
    
    async def send_expiry_warning(self, deal_id: str, buyer_id: int):
        """Kirim peringatan sebelum deal expired"""
        try:
            reminder_text = f"""
🚨 **PERINGATAN DEAL AKAN BERAKHIR**

📋 **Deal ID:** `{deal_id}`

⏰ Deal ini akan otomatis dibatalkan dalam 2 jam jika tidak ada pembayaran.

💡 **Untuk melanjutkan:**
1. Lakukan pembayaran sesuai nominal yang tertera
2. Kirim bukti transfer ke admin @Nexoitsme
3. Tunggu verifikasi dari admin

❌ Jika terlewat, Anda perlu membuat deal baru.
"""
            
            await self.bot.send_message(
                chat_id=buyer_id,
                text=reminder_text,
                parse_mode="Markdown"
            )
            
        except Exception as e:
            logger.error(f"Error sending expiry warning: {e}")
    
    async def schedule_reminders(self, deal_id: str, buyer_id: int):
        """Schedule berbagai reminder untuk sebuah deal"""
        # Reminder pembayaran setelah 2 jam
        await asyncio.sleep(2 * 3600)  # 2 jam
        await self.send_payment_reminder(deal_id, buyer_id)
        
        # Reminder lagi setelah 12 jam
        await asyncio.sleep(10 * 3600)  # 10 jam lagi (total 12 jam)
        await self.send_payment_reminder(deal_id, buyer_id)
        
        # Warning sebelum expired (22 jam)
        await asyncio.sleep(10 * 3600)  # 10 jam lagi (total 22 jam)
        await self.send_expiry_warning(deal_id, buyer_id)
    
    async def auto_cancel_unpaid_deals(self):
        """Background task untuk auto-cancel deal yang tidak dibayar"""
        try:
            conn = get_connection()
            cur = conn.cursor()
            
            try:
                # Cari deal yang sudah lebih dari 24 jam tanpa pembayaran
                cur.execute("""
                SELECT id, buyer_id, seller_id, title
                FROM deals 
                WHERE status = 'CREATED' 
                AND created_at < ?
                """, (datetime.now() - timedelta(hours=24),))
                
                expired_deals = cur.fetchall()
                
                for deal in expired_deals:
                    deal_id, buyer_id, seller_id, title = deal
                    
                    # Update status jadi CANCELLED
                    cur.execute("""
                    UPDATE deals 
                    SET status = 'CANCELLED', updated_at = ? 
                    WHERE id = ?
                    """, (datetime.now(), deal_id))
                    
                    # Notify buyer dan seller
                    try:
                        await self.bot.send_message(
                            chat_id=buyer_id,
                            text=f"❌ Deal `{deal_id}` ({title}) dibatalkan otomatis karena tidak ada pembayaran dalam 24 jam.",
                            parse_mode="Markdown"
                        )
                    except Exception as notify_error:
                        logger.error(f"Failed to notify buyer {buyer_id}: {notify_error}")
                    
                    if seller_id:
                        try:
                            await self.bot.send_message(
                                chat_id=seller_id,
                                text=f"❌ Deal `{deal_id}` ({title}) dibatalkan otomatis karena buyer tidak melakukan pembayaran.",
                                parse_mode="Markdown"
                            )
                        except Exception as notify_error:
                            logger.error(f"Failed to notify seller {seller_id}: {notify_error}")
                    
                    logger.info(f"Auto-cancelled deal {deal_id} due to no payment")
                
                conn.commit()
            except Exception as db_error:
                conn.rollback()
                raise db_error
            finally:
                cur.close()
                from db_postgres import return_connection
                return_connection(conn)
            
        except Exception as e:
            logger.error(f"Error in auto_cancel_unpaid_deals: {e}")
    
    async def auto_complete_shipped_deals(self):
        """Background task untuk auto-complete deal yang sudah shipped >72 jam"""
        try:
            conn = get_connection()
            cur = conn.cursor()
            
            try:
                # Cari deal yang sudah shipped >72 jam
                cur.execute("""
                SELECT d.id, d.buyer_id, d.seller_id, d.title, d.amount
                FROM deals d
                JOIN shipments s ON d.id = s.deal_id
                WHERE d.status = 'SHIPPED' 
                AND s.created_at < ?
                """, (datetime.now() - timedelta(hours=72),))
                
                auto_complete_deals = cur.fetchall()
                
                for deal in auto_complete_deals:
                    deal_id, buyer_id, seller_id, title, amount = deal
                    
                    # Update status jadi COMPLETED
                    cur.execute("""
                    UPDATE deals 
                    SET status = 'COMPLETED', updated_at = ? 
                    WHERE id = ?
                    """, (datetime.now(), deal_id))
                    
                    # Notify buyer dan seller with error handling
                    try:
                        await self.bot.send_message(
                            chat_id=buyer_id,
                            text=f"""
✅ **TRANSAKSI OTOMATIS DISELESAIKAN**

📋 **Deal ID:** `{deal_id}`
🏷️ **Judul:** {title}
💰 **Nominal:** {format_rupiah(amount)}

Dana sudah dilepas ke penjual karena tidak ada konfirmasi dalam 72 jam.

🌟 Jangan lupa berikan rating untuk transaksi ini!
""",
                            parse_mode="Markdown"
                        )
                    except Exception as notify_error:
                        logger.error(f"Failed to notify buyer {buyer_id}: {notify_error}")
                    
                    try:
                        await self.bot.send_message(
                            chat_id=seller_id,
                            text=f"""
🎉 **DANA SUDAH DILEPAS!**

📋 **Deal ID:** `{deal_id}`
🏷️ **Judul:** {title}
💰 **Nominal:** {format_rupiah(amount)}

Transaksi selesai otomatis. Dana sudah bisa dicairkan.

🌟 Jangan lupa berikan rating untuk transaksi ini!
""",
                            parse_mode="Markdown"
                        )
                    except Exception as notify_error:
                        logger.error(f"Failed to notify seller {seller_id}: {notify_error}")
                    
                    logger.info(f"Auto-completed deal {deal_id} after 72 hours")
                
                conn.commit()
            except Exception as db_error:
                conn.rollback()
                raise db_error
            finally:
                cur.close()
                from db_postgres import return_connection
                return_connection(conn)
            
        except Exception as e:
            logger.error(f"Error in auto_complete_shipped_deals: {e}")
    
    async def start_background_tasks(self):
        """Start background tasks untuk auto-processing"""
        while True:
            try:
                # Jalankan auto-cancel setiap 1 jam
                await self.auto_cancel_unpaid_deals()
                
                # Jalankan auto-complete setiap 1 jam  
                await self.auto_complete_shipped_deals()
                
                # Tunggu 1 jam sebelum cycle berikutnya
                await asyncio.sleep(3600)
                
            except Exception as e:
                logger.error(f"Error in background tasks: {e}")
                await asyncio.sleep(300)  # Tunggu 5 menit jika ada error

# Global instance
notification_manager = None

def init_notifications(bot):
    """Inisialisasi notification manager"""
    global notification_manager
    notification_manager = NotificationManager(bot)
    return notification_manager