
# 🚀 Rekber Bot by Nexo

Bot Telegram untuk layanan **Rekening Bersama (Rekber)** yang memungkinkan transaksi aman antara pembeli dan penjual dengan sistem escrow.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![Telegram Bot API](https://img.shields.io/badge/Telegram-Bot%20API-blue.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-blue.svg)
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
- **Auto-Generated Deal ID**: Setiap transaksi mendapat ID unik

### 💰 Manajemen Pembayaran
- **Multiple Payment Methods**: Support Bank Transfer dan E-Wallet
- **Real-time Verification**: Admin verifikasi pembayaran secara manual
- **Automatic Fee Calculation**: Biaya admin dihitung otomatis berdasarkan nominal
- **Payout Management**: Sistem pencairan dana yang aman

### 📊 Sistem Rating & Testimoni
- **Rating System**: Pembeli dan penjual bisa saling memberi rating (1-5)
- **Testimoni Channel**: Otomatis posting testimoni ke channel Telegram
- **Comment System**: Support komentar pada rating
- **Public Testimonials**: Testimoni dapat dilihat publik

### 🛡️ Security & Monitoring
- **Rate Limiting**: Pencegahan spam dan abuse
- **Input Validation**: Validasi ketat untuk semua input user
- **Activity Logging**: Log semua aktivitas transaksi
- **Dispute Resolution**: Sistem mediasi untuk sengketa

### 📱 User Experience
- **Interactive Keyboards**: Navigasi mudah dengan inline keyboard
- **Status Tracking**: Real-time tracking status transaksi
- **History Management**: Riwayat lengkap semua transaksi
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
3. **Tunggu Verifikasi** → Admin verifikasi pembayaran
4. **Terima Barang** → Penjual kirim barang/jasa
5. **Konfirmasi** → Konfirmasi penerimaan untuk release dana

## 🚀 Instalasi

### Prerequisites
- Python 3.11+
- PostgreSQL Database
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
   DATABASE_URL=postgresql://username:password@hostname:port/database
   ADMIN_ID=your_telegram_user_id
   TESTIMONI_CHANNEL=@your_testimoni_channel
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
   python -c "from db_postgres import init_db; init_db()"
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
| `BOT_USERNAME` | Username bot (tanpa @) | ✅ | - |
| `DATABASE_URL` | PostgreSQL connection string | ✅ | - |
| `ADMIN_ID` | User ID admin utama | ✅ | - |
| `TESTIMONI_CHANNEL` | Channel untuk posting testimoni | ❌ | @testirekberbotNEXO |

### Bot Configuration
File `config.py` berisi konfigurasi utama:
```python
# Biaya admin berdasarkan nominal
FEE_STRUCTURE = {
    (1000, 100000): 2000,      # 1k-100k = 2k
    (100001, 500000): 5000,    # 100k-500k = 5k  
    (500001, float('inf')): 0.01  # >500k = 1%
}

# Rate limiting
RATE_LIMIT_SECONDS = 30
MAX_MESSAGE_LENGTH = 4096
```

## 🗃️ Struktur Database

### Tabel Utama

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
```

#### `logs` - Activity Logs
```sql
- deal_id: VARCHAR(50) (Foreign Key ke deals)
- actor_id: BIGINT (User yang melakukan aksi)
- role: VARCHAR(20) (BUYER/SELLER/ADMIN)
- action: VARCHAR(50) (CREATE, JOIN, FUND, RELEASE, dll)
- detail: TEXT (Detail aktivitas)
```

#### `ratings` - Sistem Rating
```sql
- deal_id: VARCHAR(50) (Foreign Key ke deals)
- user_id: BIGINT (User pemberi rating)
- rating: INTEGER (1-5)
- comment: TEXT (Komentar opsional)
```

#### `payouts` - Data Pencairan
```sql
- deal_id: VARCHAR(50) (Foreign Key ke deals)
- seller_id: BIGINT (Penjual)
- method: VARCHAR(20) (BANK/EWALLET)
- account_details: JSON (Detail rekening)
```

## 📱 Penggunaan

### Commands untuk User

- `/start` - Memulai bot dan menampilkan menu utama
- `/riwayat` - Melihat riwayat transaksi
- `/rekber_active` - Melihat transaksi aktif
- `/rekber_done` - Melihat transaksi selesai

### Commands untuk Admin

- `/admin` - Dashboard admin
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
├── start.py          # Menu utama & navigasi
├── rekber.py         # Logic transaksi rekber
├── admin.py          # Functions admin
├── rating.py         # Sistem rating & testimoni
└── notifications.py  # Sistem notifikasi

📁 root/
├── main.py           # Entry point aplikasi
├── config.py         # Konfigurasi
├── db_postgres.py    # Database operations
├── utils.py          # Helper functions
└── security.py       # Security utilities
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
- Process management
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
# Verify DATABASE_URL
# Check PostgreSQL status
# Review connection pool settings
```

**Rate limiting issues**
```bash
# Check rate_limits table
# Adjust rate limiting parameters
# Monitor user activity
```

## 📈 Roadmap

### Upcoming Features
- [ ] **Multi-currency Support**: Support mata uang selain Rupiah
- [ ] **Smart Contracts**: Integrasi blockchain untuk transparansi
- [ ] **Mobile App**: Aplikasi mobile native
- [ ] **API Integration**: RESTful API untuk integrasi eksternal
- [ ] **Advanced Analytics**: Dashboard analytics yang lebih detail
- [ ] **Auto Dispute Resolution**: AI-powered dispute resolution

### Performance Improvements
- [ ] **Caching Layer**: Redis untuk cache data
- [ ] **Message Queue**: Async processing untuk high load
- [ ] **CDN Integration**: Asset delivery optimization
- [ ] **Database Sharding**: Horizontal scaling strategy

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
- [PostgreSQL](https://postgresql.org) - Database system
- [Replit](https://replit.com) - Development & hosting platform

---

**Made with ❤️ by Nexo Team**

*Rekber Bot - Making online transactions safe and secure for everyone*
