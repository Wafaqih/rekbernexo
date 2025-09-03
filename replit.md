# Overview

This is a Telegram bot for providing "Rekber" (escrow) services in Indonesian, enabling secure transactions between buyers and sellers. The bot manages the entire transaction lifecycle from creation to completion, including payment verification, dispute resolution, and automated testimonial posting. It features role-based transactions where users can create deals as either buyers or sellers, with flexible admin fee allocation and comprehensive transaction monitoring.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Backend Architecture
- **Framework**: Python with `python-telegram-bot` library v20.0
- **Database**: PostgreSQL with connection pooling using `psycopg2`
- **Bot Architecture**: Event-driven using Telegram's webhook/polling system
- **Conversation Management**: Multi-state conversation handlers for complex user interactions

## Database Design
- **Connection Pool**: ThreadedConnectionPool (2-20 connections) for performance optimization
- **Core Tables**: 
  - `deals`: Transaction records with buyer_id, seller_id, status, amounts
  - `ratings`: User rating system (1-5 stars)
  - `logs`: Activity logging for audit trails
  - `payouts`: Payment method information
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
- **PostgreSQL**: Primary database with connection string from `DATABASE_URL`
- **Connection Pooling**: `psycopg2.pool.ThreadedConnectionPool` for scalability

## Environment Configuration
- **BOT_TOKEN**: Telegram Bot API token
- **DATABASE_URL**: PostgreSQL connection string
- **ADMIN_IDS**: Comma-separated list of admin user IDs
- **TESTIMONI_CHANNEL**: Channel for posting testimonials

## Python Dependencies
- **python-telegram-bot**: v20.0 for Telegram API integration
- **psycopg2-binary**: PostgreSQL database adapter
- **asyncio**: Asynchronous programming support

## Third-party Integrations
- **Neon Database**: Serverless PostgreSQL hosting (based on server/db.ts)
- **Drizzle ORM**: Type-safe database queries (server-side)
- **WebSocket**: Real-time communication support