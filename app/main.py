from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.config import get_settings
from app.database import create_tables
from app.api.v1.router import api_router
from app.schemas.base import error_response

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    print("🚀 Starting SmartFarm API...")
    await create_tables()
    print("✅ Database tables created/verified")
    
    # Load ML models
    try:
        from app.ml.model_loader import load_models
        load_models()
    except Exception as e:
        print(f"⚠️  ML models not loaded: {e}")

    # Start scheduler
    try:
        from app.services.scheduler_service import start_scheduler
        start_scheduler()
    except Exception as e:
        print(f"⚠️  Scheduler not started: {e}")

    yield

    # Shutdown
    from app.services.scheduler_service import stop_scheduler
    stop_scheduler()
    print("👋 Shutting down SmartFarm API...")


# Create FastAPI application
# root_path allows FastAPI to generate correct URLs when deployed under a sub-path
# e.g. ROOT_PATH=/api when running at broilabs.ukirbin.com/api
app = FastAPI(
    title=settings.app_name,
    description="""
    SmartFarm API - Backend untuk aplikasi monitoring kandang ayam broiler berbasis IoT dan ML.

    ## Features

    * **Authentication** - JWT-based auth dengan access & refresh token
    * **Kandang Management** - CRUD kandang beserta manajemen siklus ternak
    * **Sensor Data** - Penerimaan data IoT dari ESP32 (suhu, kelembaban, amonia) dan input manual oleh admin
    * **Daily Logs** - Pencatatan harian pakan, minum, populasi, dan bobot ayam
    * **Death Reports** - Pelaporan dan rekap kematian ayam per kandang
    * **ML Predictions** - Klasifikasi kondisi kandang (Normal/Abnormal) dan forecasting berbasis RandomForest & LSTM
    * **Notifications** - Riwayat notifikasi dan real-time push via WebSocket
    * **Activity Logs** - Audit trail aktivitas pengguna dari web dan mobile

    ## Roles

    * **Admin** - Full access ke semua fitur termasuk input manual dan reload model ML
    * **Pemilik** - Manage kandang dan peternak miliknya
    * **Peternak** - Input log harian dan laporan kematian pada kandang yang dikelola
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    root_path=settings.root_path,
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with consistent response format."""
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        errors.append(f"{field}: {error['msg']}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response(
            message="Validation error",
            errors=errors,
        ),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions with consistent response format."""
    if settings.debug:
        # In debug mode, show the actual error
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response(
                message="Internal server error",
                errors=[str(exc)],
            ),
        )
    else:
        # In production, hide the actual error
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response(
                message="Internal server error",
            ),
        )


# Include API router
app.include_router(api_router, prefix=settings.api_v1_prefix)


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "app": settings.app_name}


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API info."""
    return {
        "app": settings.app_name,
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }
