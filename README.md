# SmartFarm API

Backend API untuk aplikasi SmartFarm menggunakan FastAPI.

## Features

- 🔐 **Authentication** - JWT dengan access & refresh token
- 👥 **User Management** - CRUD untuk admin (`/users`), serta manajemen peternak mandiri untuk pemilik (`/pemilik/peternak`)
- 🏠 **Kandang Management** - CRUD untuk manajemen kandang peternakan dengan spesifikasi dimensi dan tipe kandang
- 📊 **Activity Logs** - Tracking aktivitas user dari web dan mobile
- 🐔 **Daily Logs & Death Reports** - Pencatatan harian pakan, minum, bobot, dan pelaporan kematian ayam
- 🤖 **ML Predictions** - Endpoint untuk klasifikasi kondisi kandang dan forecasting mortalitas
- 🔔 **Notifications** - Notifikasi sistem dan broadcast alert via WebSocket

## Requirements

- Python 3.10+
- PostgreSQL 14+

## Installation

1. **Clone dan masuk ke folder API**
   ```bash
   cd smartfarmv3-api
   ```

2. **Buat virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Mac/Linux
   # atau
   .\.venv\Scripts\activate  # Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Setup environment**
   ```bash
   cp .env.example .env
   # Edit .env sesuai kebutuhan
   ```

5. **Setup PostgreSQL database**
   ```bash
   # Buat database di PostgreSQL
   createdb smartfarm
   # atau via psql:
   # CREATE DATABASE smartfarm;
   ```

6. **Run server**
   ```bash
   uvicorn app.main:app --reload
   ```

7. **Akses API docs**
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

## Project Structure

```
smartfarmv3-api/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Settings & configuration
│   ├── database.py          # Database connection
│   │
│   ├── models/              # SQLAlchemy models
│   │   ├── user.py          # User model (admin, pemilik, peternak)
│   │   ├── activity_log.py  # Activity log model
│   │   ├── kandang.py       # Kandang model
│   │   ├── sensor_data.py   # Sensor data model
│   │   ├── daily_log.py     # Daily log model
│   │   ├── death_report.py  # Death report model
│   │   └── notification.py  # Notification model
│   │
│   ├── schemas/             # Pydantic schemas
│   │   ├── base.py          # Base & Paginated response wrappers
│   │   ├── user.py
│   │   ├── auth.py
│   │   ├── activity_log.py
│   │   ├── kandang.py
│   │   ├── sensor_data.py
│   │   ├── daily_log.py
│   │   └── death_report.py
│   │
│   ├── api/                 # API routes
│   │   ├── deps.py          # Security & dependency injection
│   │   └── v1/
│   │       ├── router.py    # Main router v1
│   │       ├── auth.py      # Auth endpoints
│   │       ├── users.py     # Admin User CRUD
│   │       ├── pemilik_peternak.py # Dedicated Pemilik-Peternak CRUD
│   │       ├── kandangs.py  # Kandang CRUD & isolasi tenant
│   │       ├── sensor_data.py
│   │       ├── daily_logs.py
│   │       ├── death_reports.py
│   │       ├── notifications.py
│   │       └── predictions.py
│   │
│   ├── core/                # Core utilities
│   │   └── security.py      # JWT & password hashing
│   │
│   └── services/            # Business logic
│       ├── auth_service.py
│       ├── user_service.py
│       ├── kandang_service.py
│       ├── sensor_data_service.py
│       └── notification_service.py
│
├── scripts/                 # Helper scripts & index migrations
│   └── add_index_users_pemilik_id.sql
├── tests/                   # Pytest automated test suite
├── requirements.txt
├── .env.example
└── README.md
```

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/login` | Login dengan username/email + password |
| POST | `/api/v1/auth/refresh` | Refresh access token menggunakan refresh token |
| GET | `/api/v1/auth/me` | Ambil data profil user yang sedang login |
| POST | `/api/v1/auth/change-password` | Ganti password mandiri |
| POST | `/api/v1/auth/logout` | Logout |

### Users (Khusus Admin)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/users` | List seluruh users (berpaginasi) |
| GET | `/api/v1/users/{id}` | Ambil user berdasarkan ID |
| POST | `/api/v1/users` | Buat user baru (Admin/Pemilik/Peternak) |
| PUT | `/api/v1/users/{id}` | Update data user |
| DELETE | `/api/v1/users/{id}` | Soft delete user |

### Pemilik - Manajemen Peternak (`/api/v1/pemilik/peternak`) (Khusus Role Pemilik)
Endpoint mandiri untuk pemilik mengelola peternak di bawah naungannya.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/pemilik/peternak` | List peternak milik sendiri (query: `page`, `per_page`, `is_active`, `search`) |
| POST | `/api/v1/pemilik/peternak` | Tambah peternak baru (role otomatis `peternak`, `pemilik_id` otomatis terisi) |
| GET | `/api/v1/pemilik/peternak/{id}` | Ambil detail peternak milik sendiri |
| PUT | `/api/v1/pemilik/peternak/{id}` | Update profil peternak (`email`, `username`, `full_name`, `phone`) |
| DELETE | `/api/v1/pemilik/peternak/{id}` | Nonaktifkan peternak & cabut sesi token aktif (Idempotent) |

**Aturan Keamanan & Kode Error:**
- `403 Forbidden`: Jika role pengguna bukan `pemilik`. Pengguna yang dinonaktifkan (`is_active=False`) otomatis ditolak oleh dependensi `get_current_user` dengan 403 Forbidden.
- `404 Not Found`: Jika target `id` bukan peternak atau bukan di bawah naungan pemilik yang sedang login (mencegah *user enumeration*).
- `400 Bad Request`: Duplikasi username atau email (dibandingkan *case-insensitive*, mengecualikan akun yang sedang diperbarui).
- **Pencabutan Token (Revocation):** Jalur penonaktifan (`DELETE` maupun `PUT` dengan `is_active=false`) otomatis mencabut `refresh_token` dan `refresh_token_expires_at` menjadi `None`.

### Kandangs
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/kandangs` | List kandang sesuai scope role user |
| GET | `/api/v1/kandangs/me` | Ambil kandang default aktif sesuai scope kepemilikan |
| GET | `/api/v1/kandangs/{id}` | Ambil detail kandang berdasarkan ID (terisolasi per tenant) |
| POST | `/api/v1/kandangs` | Buat kandang baru (Admin bebas pilih pemilik; Pemilik otomatis miliknya) |
| PUT | `/api/v1/kandangs/{id}` | Update kandang (Hanya Admin dan Pemilik pemilik kandang) |
| DELETE | `/api/v1/kandangs/{id}` | Soft delete kandang (Admin atau Pemilik pemilik kandang) |

**Spesifikasi Field Kandang:**
- `panjang`: Panjang kandang dalam satuan meter (Float).
- `lebar`: Lebar kandang dalam satuan meter (Float).
- `luas`: Luas kandang dalam m² (Float, otomatis dihitung `panjang * lebar`).
- `tipe_kandang`: Tipe konstruksi kandang, wajib bernilai `Closed House` atau `Open House` (Enum validasi 422).

### Sensor Data
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/sensor-data/iot` | Ingest data IoT dari ESP32 (Auth via header `X-API-Key`) |
| GET | `/api/v1/sensor-data/latest` | Ambil data sensor terbaru kandang pengguna (default 4) |
| GET | `/api/v1/sensor-data/stats` | Statistik pembacaan sensor |
| GET | `/api/v1/sensor-data/history` | Riwayat data sensor |
| POST | `/api/v1/sensor-data/manual` | Input data sensor manual (Khusus Admin) |

### Activity Logs
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/activity-logs` | List seluruh activity logs (Khusus Admin) |
| GET | `/api/v1/activity-logs/me` | Ambil riwayat log aktivitas user login |

### Predictions
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/predictions/classify` | Klasifikasi kondisi lingkungan kandang (Normal/Abnormal) |
| POST | `/api/v1/predictions/forecast` | Forecasting mortalitas ayam berbasis model ML |
| GET | `/api/v1/predictions/models` | Informasi model ML aktif |

---

## Matriks Hak Akses & Perilaku Aktual

| Fitur / Tindakan | Admin | Pemilik | Peternak |
| :--- | :---: | :---: | :---: |
| Login / Logout / Refresh Token | ✅ | ✅ | ✅ |
| Kelola Profil Sendiri & Ganti Password | ✅ | ✅ | ✅ |
| Kelola Semua User Global (`/users`) | ✅ | ❌ | ❌ |
| Kelola Peternak Sendiri (`/pemilik/peternak`) | ❌ | ✅ | ❌ |
| Buat Kandang Baru (`POST /kandangs`) | ✅ | ✅ (milik sendiri) | ❌ |
| Ubah Kandang (`PUT /kandangs/{id}`) | ✅ | ✅ (kandang miliknya) | ❌ |
| Hapus Kandang (`DELETE /kandangs/{id}`) | ✅ | ✅ (kandang miliknya) | ❌ |
| Lihat Detail Kandang (`GET /kandangs/{id}`) | ✅ (semua) | ✅ (hanya miliknya) | ✅ (hanya pemiliknya) |
| Input Log Harian & Kematian | ✅ | ❌ | ✅ |
| Akses Prediksi ML & Notifikasi | ✅ | ✅ | ✅ |

### Mekanisme Dependensi Kandang:
1. **`get_single_kandang_for_user`:**
   - Mengambil data kandang untuk user terotentikasi via JWT.
   - Mengisolasi tenant: Pemilik hanya bisa mengakses kandang miliknya, Peternak hanya bisa mengakses kandang yang dinaungi pemiliknya, sedangkan Admin memiliki akses global.
2. **`get_kandang_for_iot`:**
   - Mengotentikasi perangkat IoT hardware via header `X-API-Key` (`get_iot_auth`).
   - Mengambil kandang berdasarkan query parameter `kandang_id` untuk ingest data sensor.

---

## Catatan Database & Migrasi

- **Inisialisasi Skema:** Proyek ini menggunakan inisialisasi tabel otomatis SQLAlchemy `Base.metadata.create_all()` pada *lifespan startup* (`app/main.py`) tanpa menggunakan tool migrasi Alembic.
- **Index Performa Relasi Pemilik-Peternak:** Disediakan script SQL idempotent di `scripts/add_index_users_pemilik_id.sql`:
  ```sql
  CREATE INDEX IF NOT EXISTS ix_users_pemilik_id ON users (pemilik_id);
  ```
  Script ini opsional dan disiapkan untuk dijalankan pada database production ketika volume data peternak membesar.

---

## Creating First Admin User

Untuk membuat admin pertama, jalankan script berikut setelah database siap:

```python
# create_admin.py
import asyncio
from app.database import async_session_maker
from app.models.user import User, UserRole
from app.core.security import get_password_hash

async def create_admin():
    async with async_session_maker() as session:
        admin = User(
            email="admin@smartfarm.com",
            username="admin",
            hashed_password=get_password_hash("admin123"),
            full_name="Administrator",
            role=UserRole.ADMIN,
        )
        session.add(admin)
        await session.commit()
        print("Admin user created!")

async def main():
    await create_admin()

if __name__ == "__main__":
    asyncio.run(main())
```

## License

MIT
