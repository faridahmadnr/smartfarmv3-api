# SmartFarm API

Backend API untuk aplikasi SmartFarm menggunakan FastAPI.

## Features

- 🔐 **Authentication** - JWT dengan access & refresh token
- 👥 **User Management** - CRUD untuk admin, pemilik, peternak dengan relasi pemilik-peternak
- 🏠 **Kandang Management** - CRUD untuk manajemen kandang peternakan
- 📊 **Activity Logs** - Tracking aktivitas user dari web dan mobile
- 🤖 **ML Predictions** - Endpoint untuk klasifikasi dan forecasting (placeholder, akan diintegrasikan)

## Requirements

- Python 3.10+
- PostgreSQL 14+

## Installation

1. **Clone dan masuk ke folder API**
   ```bash
   cd /Users/geffaaa/Smartfarm/api
   ```

2. **Buat virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Mac/Linux
   # atau
   .\venv\Scripts\activate  # Windows
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
api/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Settings & configuration
│   ├── database.py          # Database connection
│   │
│   ├── models/              # SQLAlchemy models
│   │   ├── user.py          # User model (admin, pemilik, peternak)
│   │   ├── activity_log.py  # Activity log model
│   │   └── kandang.py       # Kandang model
│   │
│   ├── schemas/             # Pydantic schemas
│   │   ├── base.py          # Base response schemas
│   │   ├── user.py
│   │   ├── auth.py
│   │   ├── activity_log.py
│   │   └── kandang.py
│   │
│   ├── api/                 # API routes
│   │   ├── deps.py          # Dependencies (auth, etc.)
│   │   └── v1/
│   │       ├── router.py    # Main router
│   │       ├── auth.py      # Auth endpoints
│   │       ├── users.py     # User CRUD
│   │       ├── activity_logs.py
│   │       ├── kandangs.py
│   │       └── predictions.py
│   │
│   ├── core/                # Core utilities
│   │   └── security.py      # JWT & password hashing
│   │
│   └── services/            # Business logic
│       ├── auth_service.py
│       ├── user_service.py
│       ├── activity_log_service.py
│       └── kandang_service.py
│
├── requirements.txt
├── .env.example
└── README.md
```

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/login` | Login dengan username/email + password |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| GET | `/api/v1/auth/me` | Get current user info |
| POST | `/api/v1/auth/change-password` | Change password |
| POST | `/api/v1/auth/logout` | Logout |

### Users (Admin only untuk create/update/delete)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/users` | List users (paginated) |
| GET | `/api/v1/users/{id}` | Get user by ID |
| POST | `/api/v1/users` | Create user |
| PUT | `/api/v1/users/{id}` | Update user |
| DELETE | `/api/v1/users/{id}` | Soft delete user |
| GET | `/api/v1/users/pemilik/{id}/peternaks` | Get peternaks by pemilik |

### Kandangs
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/kandangs` | List kandangs |
| GET | `/api/v1/kandangs/{id}` | Get kandang by ID |
| POST | `/api/v1/kandangs` | Create kandang |
| PUT | `/api/v1/kandangs/{id}` | Update kandang |
| DELETE | `/api/v1/kandangs/{id}` | Soft delete kandang |

### Activity Logs
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/activity-logs` | List activity logs (Admin) |
| GET | `/api/v1/activity-logs/me` | Get current user's logs |

### Predictions (Placeholder)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/predictions/classify` | Classify condition |
| POST | `/api/v1/predictions/forecast` | Forecast mortality |
| GET | `/api/v1/predictions/models` | Get model info |

## User Roles

| Feature | Admin | Pemilik | Peternak |
|---------|-------|---------|----------|
| Login/Logout | ✅ | ✅ | ✅ |
| View own profile | ✅ | ✅ | ✅ |
| Change password | ✅ | ✅ | ✅ |
| Create users | ✅ | ❌ | ❌ |
| Manage users | ✅ | ❌ | ❌ |
| View all activity logs | ✅ | ❌ | ❌ |
| View own activity logs | ✅ | ✅ | ✅ |
| Create kandang | ✅ | ✅ (own) | ❌ |
| View kandang | ✅ | ✅ (own) | ✅ (pemilik's) |
| ML Predictions | ✅ | ✅ | ✅ |

## Creating First Admin User

Untuk membuat admin pertama, jalankan script berikut setelah database ready:

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

asyncio.run(create_admin())
```

## License

MIT
