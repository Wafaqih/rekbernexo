from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ConversationHandler, MessageHandler, filters
import config
import signal
import sys
import asyncio
from db_sqlite import init_db
from handlers.start import start, rekber_create_role, rekber_panduan, show_panduan_page, rekber_main_menu
from handlers.admin_dashboard import admin_dashboard, admin_pending_actions, admin_user_stats
from handlers.notifications import init_notifications
from handlers.ux_helpers import (
    help_create_role, help_what_is_rekber, join_cancel, 
    change_fee_payer_handler
)
from handlers.rekber import (
    rekber_create_role_buyer,
    rekber_create_role_seller,
    rekber_create_title,
    rekber_create_amount,
    rekber_pick_fee_payer,
    rekber_fund_confirm,
    rekber_confirm_create, 
    rekber_cancel_create,
    rekber_join,
    rekber_join_confirm, 
    rekber_fund_verify, 
    rekber_funding_cancel, 
    rekber_mark_shipped, 
    rekber_release, 
    rekber_dispute,
    rekber_history,
    rekber_active,
    rekber_done,
    rekber_stats,
    rekber_user_history,
    rekber_status,
    ASK_AMOUNT,
    ASK_TITLE,
    ASK_CONFIRMATION,
    ASK_FEE_PAYER,
    payout_start,
    payout_pick_method,
    payout_cancel,
    payout_bank_name,
    payout_bank_number,
    payout_bank_holder,
    payout_ew_provider,
    payout_ew_number,
    payout_save,
    PAY_METHOD,
    PAY_BANK_NAME,
    PAY_BANK_NUMBER,
    PAY_BANK_HOLDER,
    PAY_EW_PROVIDER,
    PAY_EW_NUMBER,
    PAY_NOTE,
    handle_mediasi,
    ASK_GROUP_LINK,
    receive_group_link,
    rekber_fee_paid,
    rekber_fee_verify,
    start_payment_handler,
    rekber_cancel_request,
    rekber_cancel_approve,
    rekber_cancel_reject,
    handle_payment_proof
)

from handlers.admin import (
    rekber_admin_verify, rekber_admin_reject, rekber_admin_release, 
    rekber_admin_refund, admin_release_final, admin_release_execute, 
    admin_confirm_payout, verify_payment_with_proof, reject_payment_with_proof
)
from handlers.rating import handle_rating, ask_for_comment, receive_comment, skip_comment, cancel_rating, WAITING_COMMENT, send_testimoni_menu, receive_testimoni, cancel_testimoni, WAITING_TESTIMONI





def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    print("\nShutting down bot...")
    sys.exit(0)

def main():
    # Handle shutdown signals
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Try to initialize database, but continue if it fails
    try:
        init_db()
    except Exception as e:
        print(f"⚠️ Database initialization failed: {e}")
        print("📱 Bot will start without database - some features may be limited")

    # Build app with retry settings untuk handling conflicts
    app = Application.builder().token(str(config.BOT_TOKEN)).connect_timeout(30).read_timeout(30).build()
    # simpan admin id 
    app.bot_data["admin"] = config.ADMIN_ID

    # Initialize notifications
    notification_manager = init_notifications(app.bot)
    app.bot_data["notification_manager"] = notification_manager

    # === Rekber Conversation ===
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(rekber_create_role_buyer, pattern="^rekber_create_buyer$"),
            CallbackQueryHandler(rekber_create_role_seller, pattern="^rekber_create_seller$")
        ],
        states={
            ASK_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, rekber_create_title)],
            ASK_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, rekber_create_amount)],
            ASK_FEE_PAYER: [CallbackQueryHandler(rekber_pick_fee_payer, pattern="^fee_payer\|")],
            ASK_CONFIRMATION: [
                CallbackQueryHandler(rekber_confirm_create, pattern="^confirm_create$"),
                CallbackQueryHandler(rekber_cancel_create, pattern="^cancel_create$")
            ],
        },
        fallbacks=[],   # cukup pakai tombol, ga perlu /cancel
    )
    app.add_handler(conv_handler)

    # === Testimoni Conversation ===
    conv_handler_testimoni = ConversationHandler(
        entry_points=[CallbackQueryHandler(send_testimoni_menu, pattern="^send_testimoni_menu")],
        states={
            WAITING_TESTIMONI: [
                MessageHandler(filters.PHOTO | filters.TEXT & ~filters.COMMAND, receive_testimoni)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_testimoni)],
    )
    app.add_handler(conv_handler_testimoni)

    # === Payout Conversation ===
    payout_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(payout_start, pattern="^payout_start\\|")],
        states={
            PAY_METHOD: [
                CallbackQueryHandler(payout_pick_method, pattern="^payout_method\\|"),
                CallbackQueryHandler(payout_cancel, pattern="^payout_cancel$")
            ],
            PAY_BANK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, payout_bank_name)],
            PAY_BANK_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, payout_bank_number)],
            PAY_BANK_HOLDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, payout_bank_holder)],
            PAY_EW_PROVIDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, payout_ew_provider)],
            PAY_EW_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, payout_ew_number)],
            PAY_NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, payout_save)],
        },
        fallbacks=[
            CommandHandler("cancel", payout_cancel),
            CallbackQueryHandler(payout_cancel, pattern="^payout_cancel$")
        ],
        per_message=False
    )
    app.add_handler(payout_conv)

    #======= Mediasi Conversation =======
    mediasi_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_mediasi, pattern="^mediasi\\|")],
        states={
            ASK_GROUP_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_group_link)]
        },
        fallbacks=[],
    )
    app.add_handler(mediasi_conv_handler)

    # === Tambahkan handler untuk eksekusi release ===
    app.add_handler(CallbackQueryHandler(admin_release_execute, pattern="^admin_release_execute\\|"))

    # command
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_dashboard))
    app.add_handler(CommandHandler("dashboard", admin_dashboard))

    # === Main Callback Handlers ===
    app.add_handler(CallbackQueryHandler(rekber_create_role, pattern="^rekber_create_role$"))
    app.add_handler(CallbackQueryHandler(rekber_join, pattern="^rekber_join\\|"))
    app.add_handler(CallbackQueryHandler(rekber_join_confirm, pattern="^rekber_join_confirm\\|"))
    app.add_handler(CallbackQueryHandler(rekber_status, pattern="^rekber_status\\|"))
    app.add_handler(CallbackQueryHandler(rekber_mark_shipped, pattern="^rekber_mark_shipped\\|"))
    app.add_handler(CallbackQueryHandler(rekber_release, pattern="^rekber_release\\|"))
    app.add_handler(CallbackQueryHandler(rekber_dispute, pattern="^rekber_dispute\\|"))
    app.add_handler(CallbackQueryHandler(rekber_fee_paid, pattern="^seller_fee_confirm"))
    app.add_handler(CallbackQueryHandler(rekber_fee_verify, pattern="^fee_verify"))
    app.add_handler(CallbackQueryHandler(rekber_fund_confirm, pattern="^rekber_fund_confirm\\|"))
    app.add_handler(CallbackQueryHandler(start_payment_handler, pattern="^start_payment\\|"))
    app.add_handler(CallbackQueryHandler(rekber_funding_cancel, pattern="^rekber_funding_cancel\\|"))
    app.add_handler(CallbackQueryHandler(rekber_cancel_request, pattern="^rekber_cancel_request"))
    app.add_handler(CallbackQueryHandler(rekber_cancel_approve, pattern="^rekber_cancel_approve"))
    app.add_handler(CallbackQueryHandler(rekber_cancel_reject, pattern="^rekber_cancel_reject"))

    # === Admin Handlers ===
    app.add_handler(CallbackQueryHandler(rekber_admin_verify, pattern="^rekber_admin_verify\\|"))
    app.add_handler(CallbackQueryHandler(rekber_admin_reject, pattern="^rekber_admin_reject\\|"))
    app.add_handler(CallbackQueryHandler(rekber_admin_release, pattern="^rekber_admin_release\\|"))
    app.add_handler(CallbackQueryHandler(rekber_admin_refund, pattern="^rekber_admin_refund\\|"))
    app.add_handler(CallbackQueryHandler(admin_release_final, pattern="^admin_release_final\\|"))
    app.add_handler(CallbackQueryHandler(admin_release_execute, pattern="^admin_release_execute\\|"))
    app.add_handler(CallbackQueryHandler(admin_confirm_payout, pattern="^admin_confirm_payout\\|"))
    app.add_handler(CallbackQueryHandler(verify_payment_with_proof, pattern="^verify_payment\\|"))
    app.add_handler(CallbackQueryHandler(reject_payment_with_proof, pattern="^reject_payment\\|"))

    # Rating conversation handler - dipindah ke atas agar prioritas
    rating_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(ask_for_comment, pattern="^add_comment")],
        states={
            WAITING_COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_comment)]
        },
        fallbacks=[CommandHandler("cancel", cancel_rating)],
        per_message=False
    )
    app.add_handler(rating_conv_handler)

    # Rating handlers - setelah conversation handler
    # === Rating Handlers ===
    app.add_handler(CallbackQueryHandler(handle_rating, pattern="^rate"))
    app.add_handler(CallbackQueryHandler(skip_comment, pattern="^skip_comment"))

    # === Command Handlers ===
    app.add_handler(CommandHandler("rekber_history", rekber_history))
    app.add_handler(CommandHandler("rekber_active", rekber_active))
    app.add_handler(CommandHandler("rekber_done", rekber_done))
    app.add_handler(CommandHandler("rekber_stats", rekber_stats))
    app.add_handler(CommandHandler("riwayat", rekber_user_history))
    
    # === Photo Handler ===
    app.add_handler(MessageHandler(filters.PHOTO, handle_payment_proof))

    # === Navigation Handlers ===
    app.add_handler(CallbackQueryHandler(rekber_panduan, pattern="^rekber_panduan$"))
    app.add_handler(CallbackQueryHandler(lambda u, c: show_panduan_page(u.callback_query, 1), pattern="^rekber_panduan_page_1$"))
    app.add_handler(CallbackQueryHandler(lambda u, c: show_panduan_page(u.callback_query, 2), pattern="^rekber_panduan_page_2$"))
    app.add_handler(CallbackQueryHandler(lambda u, c: show_panduan_page(u.callback_query, 3), pattern="^rekber_panduan_page_3$"))
    app.add_handler(CallbackQueryHandler(lambda u, c: show_panduan_page(u.callback_query, 4), pattern="^rekber_panduan_page_4$"))
    app.add_handler(CallbackQueryHandler(lambda u, c: rekber_main_menu(u, c), pattern="^rekber_main_menu$"))
    app.add_handler(CallbackQueryHandler(rekber_user_history, pattern="^rekber_user_history$"))
    app.add_handler(CallbackQueryHandler(rekber_user_history, pattern="^rekber_history_menu$"))

    # === Dashboard and Menu Handlers ===
    app.add_handler(CallbackQueryHandler(admin_pending_actions, pattern="^admin_pending_actions"))
    app.add_handler(CallbackQueryHandler(admin_user_stats, pattern="^admin_user_stats"))

    # === UX Helper Handlers ===
    app.add_handler(CallbackQueryHandler(help_create_role, pattern="^help_create_role"))
    app.add_handler(CallbackQueryHandler(help_what_is_rekber, pattern="^help_what_is_rekber"))
    app.add_handler(CallbackQueryHandler(join_cancel, pattern="^join_cancel"))
    app.add_handler(CallbackQueryHandler(change_fee_payer_handler, pattern="^change_fee_payer"))

    # Start background tasks setelah polling dimulai
    async def post_init(application):
        import asyncio
        asyncio.create_task(notification_manager.start_background_tasks())

    app.post_init = post_init

    try:
        print("Starting bot...")
        # Add retry mechanism untuk conflict handling
        app.run_polling(drop_pending_updates=True, close_loop=False)
    except Exception as e:
        print(f"Bot stopped with error: {e}")
        if "terminated by other getUpdates request" in str(e):
            print("⚠️ Another bot instance is running. Please stop other instances first.")
            print("💡 Tips:")
            print("   - Check if bot is running in another terminal/tab")
            print("   - Wait 30 seconds and try again")
            print("   - Make sure only one bot instance is active")
    finally:
        print("Bot shutdown complete.")

if __name__ == "__main__":
    main()