# Overview

This is a Telegram bot for providing "Rekber" (escrow) services in Indonesian, enabling secure transactions between buyers and sellers. The bot manages the entire transaction lifecycle from creation to completion, including payment verification, dispute resolution, and automated testimonial posting. It features role-based transactions where users can create deals as either buyers or sellers, with flexible admin fee allocation and comprehensive transaction monitoring.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Backend Architecture
- **Framework**: Python with `python-telegram-bot` library v20.0
- **Database**: SQLite with connection management using `sqlite3`
- **Bot Architecture**: Event-driven using Telegram's webhook/polling system
- **Conversation Management**: Multi-state conversation handlers for complex user interactions

## Database Design
- **Database**: SQLite with connection management for simplicity and reliability
- **Core Tables**: 
  - `deals`: Transaction records with buyer_id, seller_id, status, amounts
  - `ratings`: User rating system (1-5 stars)
  - `logs`: Activity logging for audit trails
  - `payouts`: Payment method information
  - `users`: User statistics and profile information
  - `rate_limits`: Rate limiting for security
  - `disputes`: Dispute management system
  - `shipments`: Shipping tracking information
- **Transaction States**: Multi-status workflow (CREATED → WAITING_VERIFICATION → FUNDED → SHIPPED → COMPLETED)

## Security Features
- **Rate Limiting**: 30-second cooldown per user action to prevent spam
- **Input Validation**: Strict validation for monetary amounts (min: Rp 1,000, max: Rp 100M)
- **Admin Permissions**: Role-based access control for administrative functions
- **Activity Logging**: Comprehensive audit trail for all transaction activities

## User Experience Design
- **Multi-language Support**: Indonesian language interface
- **Conversation States**: Complex multi-step transaction creation process
- **Inline Keyboards**: Rich interactive buttons for navigation
- **Error Handling**: Graceful error handling with user-friendly messages
- **Help System**: Contextual help for role selection and process understanding

## Payment Processing
- **Escrow System**: Admin-mediated fund holding until transaction completion
- **Flexible Fee Structure**: Tiered admin fees based on transaction amount
- **Multiple Payment Methods**: Bank transfer and e-wallet support
- **Manual Verification**: Admin verification system for payment confirmation

## Notification System
- **Real-time Updates**: Immediate notifications for all transaction state changes
- **Reminder System**: Automated payment reminders for pending transactions
- **Public Testimonials**: Automatic posting to public Telegram channel
- **Admin Alerts**: Monitoring system for suspicious activities and stuck transactions

# External Dependencies

## Telegram Integration
- **Telegram Bot API**: Core messaging and interaction platform
- **Public Channel**: `@testirekberbotNEXO` for testimonial publishing
- **Bot Commands**: Rich command set for transaction management

## Database Services
- **SQLite**: Primary database stored as `rekber.db` file
- **Connection Management**: Simple connection handling with proper resource cleanup

## Environment Configuration
- **BOT_TOKEN**: Telegram Bot API token
- **ADMIN_IDS**: Comma-separated list of admin user IDs
- **TESTIMONI_CHANNEL**: Channel for posting testimonials

## Python Dependencies
- **python-telegram-bot**: v20.0 for Telegram API integration
- **sqlite3**: Built-in SQLite database support
- **asyncio**: Asynchronous programming support

## Recent Changes

### Database Migration (September 2025)
- **Migrated from PostgreSQL to SQLite**: Changed from PostgreSQL with connection pooling to SQLite for simplicity and better local development experience
- **Removed Dependencies**: Eliminated PostgreSQL dependencies (psycopg2-binary) and server-side components
- **File Changes**: 
  - Created new `db_sqlite.py` with all database functions
  - Updated all handlers to use SQLite syntax (? parameters instead of %s)
  - Removed `db_postgres.py`, `db_sqlite_fallback.py`, and `server/` directory
- **Preserved Functionality**: All transaction flows and features remain intact