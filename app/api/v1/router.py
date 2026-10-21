from fastapi import APIRouter

from app.api.v1 import auth, users, activity_logs, kandangs, predictions, predictions_dl, sensor_data, notifications, death_reports, daily_logs

api_router = APIRouter()

# Include all routers
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"],
)

api_router.include_router(
    users.router,
    prefix="/users",
    tags=["Users"],
    include_in_schema=False,
)

api_router.include_router(
    activity_logs.router,
    prefix="/activity-logs",
    tags=["Activity Logs"],
)

api_router.include_router(
    kandangs.router,
    prefix="/kandangs",
    tags=["Kandangs"],
)

api_router.include_router(
    predictions.router,
    prefix="/predictions",
    tags=["Predictions"],
)

api_router.include_router(
    predictions_dl.router,
    prefix="/predictions-dl",
    tags=["Predictions Deep Learning"],
)

api_router.include_router(
    sensor_data.router,
    prefix="/sensor-data",
    tags=["Sensor Data"],
)

api_router.include_router(
    notifications.router,
    prefix="/notifications",
    tags=["Notifications"],
)

api_router.include_router(
    death_reports.router,
    prefix="/death-reports",
    tags=["Death Reports"],
)

api_router.include_router(
    daily_logs.router,
    prefix="/daily-logs",
    tags=["Daily Logs"],
)
