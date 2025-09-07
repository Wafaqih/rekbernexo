
# 🚀 Rekber Bot by Nexo

Bot Telegram untuk layanan **Rekening Bersama (Rekber)** yang memungkinkan transaksi aman antara pembeli dan penjual dengan sistem escrow.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![Telegram Bot API](https://img.shields.io/badge/Telegram-Bot%20API-blue.svg)
![SQLite](https://img.shields.io/badge/SQLite-Database-blue.svg)
![Status](https://img.shields.io/badge/Status-Production-green.svg)

## 📋 Daftar Isi

- [Fitur Utama](#-fitur-utama)
- [Cara Kerja](#-cara-kerja)
- [Instalasi](#-instalasi)
- [Konfigurasi](#-konfigurasi)
- [Struktur Database](#-struktur-database)
- [Penggunaan](#-penggunaan)
- [API Commands](#-api-commands)
- [Security Features](#-security-features)
- [Contributing](#-contributing)
- [License](#-license)

## ✨ Fitur Utama

### 🔐 Sistem Rekber (Escrow)
- **Transaksi Aman**: Dana ditahan admin hingga transaksi selesai
- **Multi-Role Support**: Bisa membuat transaksi sebagai pembeli atau penjual
- **Flexible Fee**: Biaya admin bisa ditanggung pembeli atau penjual
- **Auto-Generated Deal ID**: Setiap transaksi mendapat ID unik format RB-YYMMDDHHMMSS999

### 💰 Manajemen Pembayaran
- **Multiple Payment Methods**: Support Bank Transfer dan E-Wallet (Dana, GoPay, SeaBank, Bank Jago)
- **Real-time Verification**: Admin verifikasi pembayaran dengan foto bukti transfer
- **Automatic Fee Calculation**: Biaya admin dihitung otomatis berdasarkan nominal
- **Payout Management**: Sistem pencairan dana yang aman dengan detail bank/e-wallet

### 📊 Sistem Rating & Testimoni
- **Rating System**: Pembeli dan penjual bisa saling memberi rating (1-5) dengan emoji
- **Testimoni Channel**: Otomatis posting testimoni ke channel @testirekberbotNEXO
- **Comment System**: Support komentar pada rating
- **Public Testimonials**: Testimoni dapat dilihat publik di channel

### 🛡️ Security & Monitoring
- **Rate Limiting**: Pencegahan spam dan abuse
- **Input Validation**: Validasi ketat untuk semua input user
- **Activity Logging**: Log semua aktivitas transaksi dengan timestamps
- **Dispute Resolution**: Sistem mediasi untuk sengketa dengan grup WhatsApp

### 📱 User Experience
- **Interactive Keyboards**: Navigasi mudah dengan inline keyboard
- **Status Tracking**: Real-time tracking status transaksi
- **History Management**: Riwayat lengkap semua transaksi per user
- **Multi-language Support**: Interface dalam Bahasa Indonesia

## 🔄 Cara Kerja

### Untuk Penjual:
1. **Buat Transaksi** → Input judul, nominal, pilih siapa bayar fee
2. **Share Link** → Bagikan link undangan ke pembeli
3. **Tunggu Join** → Pembeli bergabung ke transaksi
4. **Tunggu Payment** → Pembeli transfer dana ke admin
5. **Kirim Barang** → Setelah dana terverifikasi, kirim barang
6. **Terima Dana** → Pembeli konfirmasi → dana dilepas

### Untuk Pembeli:
1. **Join Transaksi** → Klik link dari penjual
2. **Transfer Dana** → Bayar ke rekening admin sesuai instruksi
3. **Kirim Bukti** → Upload foto bukti transfer
4. **Tunggu Verifikasi** → Admin verifikasi pembayaran
5. **Terima Barang** → Penjual kirim barang/jasa
6. **Konfirmasi** → Konfirmasi penerimaan untuk release dana

## 🚀 Instalasi

### Prerequisites
- Python 3.11+
- SQLite Database (otomatis terbuat)
- Telegram Bot Token

### Quick Start di Replit

1. **Fork Template**
   ```bash
   # Template sudah tersedia di Replit
   # Klik "Use Template" atau fork repository ini
   ```

2. **Setup Environment Variables**
   Buka tab **Secrets** di Replit dan tambahkan:
   ```
   BOT_TOKEN=your_telegram_bot_token
   BOT_USERNAME=your_bot_username
   ADMIN_ID=your_telegram_user_id
   TESTIMONI_CHANNEL=@testirekberbotNEXO
   ```

3. **Deploy**
   ```bash
   # Klik tombol "Deploy" di Replit
   # Pilih "Reserved VM Deployments"
   # Deploy akan otomatis install dependencies
   ```

### Manual Installation

1. **Clone Repository**
   ```bash
   git clone <repository-url>
   cd rekber-bot
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Setup Database**
   ```bash
   python migrate.py
   ```

4. **Run Bot**
   ```bash
   python main.py
   ```

## ⚙️ Konfigurasi

### Environment Variables

| Variable | Deskripsi | Required | Default |
|----------|-----------|----------|---------|
| `BOT_TOKEN` | Token bot dari @BotFather | ✅ | - |
| `BOT_USERNAME` | Username bot (tanpa @) | ❌ | - |
| `ADMIN_ID` | User ID admin utama | ✅ | 7058869200 |
| `TESTIMONI_CHANNEL` | Channel untuk posting testimoni | ❌ | @TESTIJASAREKBER |

### Metode Pembayaran

```python
PAYMENT_METHODS = {
    "DANA": "082119299186 | Muhammad Abdu Wafaqih",
    "GOPAY": "082119299186 | Wafaqih", 
    "SEABANK": "901251081230 | Muhammad Abdu Wafaqih",
    "BANK_JAGO": "103536428831 | Muhammad Abdu Wafaqih"
}
```

## 🗃️ Struktur Database

### Tabel Utama (SQLite)

#### `deals` - Transaksi Rekber
```sql
- id: VARCHAR(50) PRIMARY KEY (Format: RB-YYMMDDHHMMSS999)
- title: TEXT (Judul barang/jasa)
- amount: INTEGER (Nominal dalam Rupiah)
- buyer_id: BIGINT (Telegram User ID pembeli)
- seller_id: BIGINT (Telegram User ID penjual)
- status: VARCHAR(50) (PENDING_JOIN, FUNDED, COMPLETED, dll)
- admin_fee: INTEGER (Biaya admin)
- admin_fee_payer: VARCHAR(20) (BUYER/SELLER)
- joined_by: INTEGER (User ID yang join terakhir)
- payment_proof_file_id: TEXT (File ID bukti pembayaran)
```

#### `logs` - Activity Logs
```sql
- deal_id: VARCHAR(50) (Foreign Key ke deals)
- actor_id: BIGINT (User yang melakukan aksi)
- role: VARCHAR(20) (BUYER/SELLER/ADMIN)
- action: VARCHAR(50) (CREATE, JOIN, FUND, RELEASE, dll)
- detail: TEXT (Detail aktivitas)
- timestamp: DATETIME DEFAULT CURRENT_TIMESTAMP
```

#### `ratings` - Sistem Rating
```sql
- deal_id: VARCHAR(50) (Foreign Key ke deals)
- user_id: BIGINT (User pemberi rating)
- rating: INTEGER (1-5)
- comment: TEXT (Komentar opsional)
- timestamp: DATETIME DEFAULT CURRENT_TIMESTAMP
```

#### `payouts` - Data Pencairan
```sql
- deal_id: VARCHAR(50) (Foreign Key ke deals)
- seller_id: BIGINT (Penjual)
- method: VARCHAR(20) (BANK/EWALLET)
- bank_name: TEXT (Nama bank)
- account_number: TEXT (Nomor rekening)
- account_holder: TEXT (Nama pemegang rekening)
- notes: TEXT (Catatan tambahan)
```

## 📱 Penggunaan

### Commands untuk User

- `/start` - Memulai bot dan menampilkan menu utama
- `/riwayat` - Melihat riwayat transaksi
- `/rekber_active` - Melihat transaksi aktif
- `/rekber_done` - Melihat transaksi selesai

### Commands untuk Admin

- `/admin` - Dashboard admin
- `/dashboard` - Dashboard admin (alias)
- `/rekber_stats [YYYY-MM]` - Statistik transaksi

### Status Transaksi

| Status | Deskripsi |
|--------|-----------|
| `PENDING_JOIN` | Menunggu pihak lain bergabung |
| `PENDING_FUNDING` | Menunggu pembayaran pembeli |
| `WAITING_VERIFICATION` | Menunggu verifikasi admin |
| `FUNDED` | Dana sudah terverifikasi |
| `AWAITING_CONFIRM` | Menunggu konfirmasi penerimaan |
| `AWAITING_PAYOUT` | Menunggu data pencairan |
| `COMPLETED` | Transaksi selesai |
| `CANCELLED` | Transaksi dibatalkan |
| `DISPUTED` | Dalam sengketa |

## 🔒 Security Features

### Input Validation
```python
# Validasi nomor rekening
def validate_bank_account(account: str) -> bool:
    return account.isdigit() and 6 <= len(account) <= 20

# Validasi nomor telepon
def validate_phone_number(phone: str) -> bool:
    pattern = r'^(\+62|62|0)8[1-9][0-9]{6,11}$'
    return bool(re.match(pattern, phone))
```

### Rate Limiting
- Maximum 5 aksi per jam per user
- Auto-reset setiap jam
- Logging aktivitas mencurigakan

### Data Sanitization
- HTML encoding untuk semua input
- SQL injection prevention dengan parameterized queries
- XSS protection pada output formatting

## 🏗️ Architecture

### Core Components

```
📁 handlers/
├── start.py              # Menu utama & navigasi
├── rekber.py            # Logic transaksi rekber
├── admin.py             # Functions admin
├── admin_dashboard.py   # Dashboard admin
├── rating.py            # Sistem rating & testimoni
├── notifications.py     # Sistem notifikasi
└── ux_helpers.py        # Helper untuk UX

📁 root/
├── main.py              # Entry point aplikasi
├── config.py            # Konfigurasi
├── db_sqlite.py         # Database operations
├── migrate.py           # Database migration
├── utils.py             # Helper functions
└── security.py          # Security utilities
```

### Flow Architecture
```
User Input → Security Validation → Business Logic → Database → Response
     ↓              ↓                    ↓           ↓         ↓
Rate Limit → Input Sanitize → Process Transaction → Log Action → Send Message
```

## 🚀 Deployment di Replit

### Automatic Deployment
1. **Connect Repository**: Import dari GitHub
2. **Configure Secrets**: Set environment variables
3. **Deploy**: Klik tombol Deploy
4. **Monitor**: Gunakan Replit monitoring tools

### Production Settings
```python
# Replit automatically handles:
- Process management (Reserved VM)
- Auto-restart on crash
- Load balancing
- SSL certificates
- Domain forwarding
```

## 📊 Monitoring & Analytics

### Built-in Metrics
- Total transaksi per hari/bulan
- Success rate transaksi
- Volume transaksi
- User activity tracking
- Error rate monitoring

### Health Checks
```python
# Database connection health
# Bot API response time
# Memory usage monitoring
# Queue length tracking
```

## 🛠️ Development

### Local Development
```bash
# Setup development environment
pip install -r requirements.txt

# Run with debug logging
export DEBUG=True
python main.py
```

### Testing
```bash
# Run basic tests
python debug_rekber.py

# Check database integrity
python check_logs.py

# Fix stuck transactions
python fix_stuck_transactions.py
```

## 🔧 Troubleshooting

### Common Issues

**Bot tidak respond**
```bash
# Check bot token
# Verify webhook settings
# Monitor error logs
```

**Database connection error**
```bash
# Check rekber.db file permissions
# Run migration: python migrate.py
# Verify SQLite installation
```

**Rate limiting issues**
```bash
# Check activity logs
# Adjust rate limiting parameters
# Monitor user activity
```

## 📈 Roadmap

### Upcoming Features
- [ ] **QRIS Payment**: Integrasi pembayaran QRIS
- [ ] **Multi-currency Support**: Support mata uang selain Rupiah
- [ ] **Smart Contracts**: Integrasi blockchain untuk transparansi
- [ ] **Mobile App**: Aplikasi mobile native
- [ ] **API Integration**: RESTful API untuk integrasi eksternal
- [ ] **Advanced Analytics**: Dashboard analytics yang lebih detail

### Performance Improvements
- [ ] **Caching Layer**: Redis untuk cache data
- [ ] **Message Queue**: Async processing untuk high load
- [ ] **Database Migration**: PostgreSQL untuk production scale
- [ ] **Auto-scaling**: Horizontal scaling strategy

## 🤝 Contributing

### How to Contribute
1. Fork repository
2. Create feature branch
3. Make changes
4. Add tests
5. Submit pull request

### Development Guidelines
- Follow PEP 8 coding standards
- Add docstrings untuk semua functions
- Include type hints
- Write comprehensive tests
- Update documentation

### Bug Reports
Gunakan GitHub Issues dengan template:
```
**Bug Description**: 
**Steps to Reproduce**: 
**Expected Behavior**: 
**Screenshots**: 
**Environment**: 
```

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 📞 Support

- **Developer**: @Nexoitsme
- **Channel**: @testirekberbotNEXO
- **Issues**: GitHub Issues
- **Documentation**: This README

## 🙏 Acknowledgments

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) - Telegram Bot framework
- [SQLite](https://sqlite.org) - Lightweight database system
- [Replit](https://replit.com) - Development & hosting platform

---

**Made with ❤️ by Nexo Team**

*Rekber Bot - Making online transactions safe and secure for everyone*
