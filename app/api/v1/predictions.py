"""
SmartFarm ML Prediction Endpoints
"""
from typing import Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.base import BaseResponse, success_response
from app.services.prediction_service import PredictionService
from app.models.kandang import Kandang
from app.api.deps import get_current_user, get_single_kandang
from app.ml.model_loader import load_models

router = APIRouter()


class ModelInfoResponse(BaseModel):
    classification_model: Dict[str, Any]
    forecasting_model: Dict[str, Any]


@router.get(
    "/models",
    response_model=BaseResponse[ModelInfoResponse],
    summary="Get Model Info",
    description="Get information about loaded ML models",
)
async def get_models_info(
    _: User = Depends(get_current_user),
):
    model_info = ModelInfoResponse(
        classification_model={
            "name": "SmartFarm Classification Model",
            "type": "RandomForestClassifier",
            "version": "1.0.0",
            "status": "loaded",
            "description": "Classification model for farm condition (Normal/Abnormal)",
            "input_features": [
                "Hari Ke-", "Suhu", "Kelembaban", "Amoniak", "Pakan",
                "Minum", "Bobot", "Populasi", "Luas Kandang", "Hour"
            ],
            "output_classes": ["Normal", "Abnormal"],
            "metrics": {
                "accuracy": "97.21%",
                "f1_score": "93.02%"
            }
        },
        forecasting_model={
            "name": "SmartFarm Forecasting Model",
            "type": "XGBRegressor",
            "version": "1.0.0",
            "status": "loaded",
            "description": "Forecasting model for chicken death prediction",
            "input_features": ["temp", "hum", "ammo", "Death (history)"],
            "window_size": "4 data points (2 hours)",
            "output": "predicted_death (count)",
            "metrics": {
                "rmse": "0.2752",
                "pearson": "0.7351"
            }
        },
    )

    return success_response(
        data=model_info,
        message="Informasi model berhasil diambil",
    )


@router.post(
    "/load-models",
    summary="Load/Reload ML Models",
    description="Manually reload ML models (Admin only)",
)
async def reload_models(
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can reload models"
        )

    try:
        load_models()
        return success_response(
            data={"status": "models_reloaded"},
            message="ML models berhasil di-reload",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reload models: {str(e)}"
        )


@router.get(
    "/summary",
    summary="Get Prediction Summary",
    description="Ringkasan jumlah prediksi ML (normal/abnormal, aman/risiko)",
)
async def get_prediction_summary(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    _: User = Depends(get_current_user),
    kandang: Kandang = Depends(get_single_kandang),
    db: AsyncSession = Depends(get_db),
):
    start = start_date.date() if start_date else None
    end = end_date.date() if end_date else None

    svc = PredictionService(db)
    summary = await svc.get_summary(kandang.id, model_type="ml", start_date=start, end_date=end)
    return success_response(data=summary, message="Ringkasan prediksi ML")


@router.get(
    "/history",
    summary="Get Prediction History",
    description="Riwayat hasil prediksi ML dari IoT (classification & forecasting)",
)
async def get_prediction_history(
    type: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    _: User = Depends(get_current_user),
    kandang: Kandang = Depends(get_single_kandang),
    db: AsyncSession = Depends(get_db),
):
    import json

    if sort_by not in ("created_at", "prediction", "confidence", "predicted_death", "raw_prediction"):
        sort_by = "created_at"
    if sort_order not in ("asc", "desc"):
        sort_order = "desc"
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 200:
        page_size = 50

    start = start_date.date() if start_date else None
    end = end_date.date() if end_date else None
    offset = (page - 1) * page_size

    svc = PredictionService(db)
    records, total = await svc.get_history(
        kandang.id,
        page_size=page_size,
        offset=offset,
        prediction_type=type,
        model_type="ml",
        start_date=start,
        end_date=end,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    items = []
    for r in records:
        items.append({
            "id": str(r.id),
            "type": r.type,
            "prediction": r.prediction,
            "confidence": r.confidence,
            "predicted_death": r.predicted_death,
            "raw_prediction": r.raw_prediction,
            "input_data": json.loads(r.input_data) if r.input_data else None,
            "created_at": r.created_at.isoformat(),
        })

    return success_response(
        data={"items": items, "total": total, "page": page, "page_size": page_size},
        message=f"{total} riwayat prediksi",
    )
