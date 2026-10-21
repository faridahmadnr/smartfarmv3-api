"""
SmartFarm ML Prediction Endpoints (Deep Learning — LSTM)
"""
import uuid
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.kandang import Kandang
from app.models.sensor_data import SensorData
from app.schemas.base import BaseResponse, success_response
from app.services.prediction_service import PredictionService
from app.api.deps import get_current_user, get_single_kandang
from app.ml.model_loader_dl import (
    load_models, predict_classification, predict_forecasting,
    CLS_TIME_STEPS, CLS_ROLLING_WINDOW, FC_TIME_STEPS, FC_ROLLING_WINDOW,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────────────────────
class ModelInfoResponse(BaseModel):
    classification_model: Dict[str, Any]
    forecasting_model: Dict[str, Any]


class ClassifyRequest(BaseModel):
    hari_ke: int = Field(..., description="Hari ke- dalam siklus")
    suhu: float = Field(..., description="Suhu (°C)")
    kelembaban: float = Field(..., description="Kelembaban (%)")
    amoniak: float = Field(..., description="Amoniak (ppm)")
    pakan: float = Field(0, description="Pakan (kg)")
    minum: float = Field(0, description="Minum (L)")
    bobot: float = Field(0, description="Bobot (g)")
    populasi: int = Field(0, description="Populasi ayam")
    luas_kandang: float = Field(120, description="Luas kandang (m²)")
    hour: int = Field(12, description="Jam saat ini (0-23)")
    kandang_id: Optional[str] = None


class SensorHistoryItem(BaseModel):
    temp: float = Field(..., description="Suhu (°C)")
    hum: float = Field(..., description="Kelembaban (%)")
    ammo: float = Field(..., description="Amoniak (ppm)")
    Death: float = Field(0, description="Jumlah kematian pada interval ini")


class ForecastRequest(BaseModel):
    sensor_history: List[SensorHistoryItem] = Field(
        ..., min_length=4, description="Minimal 4 data point sensor terakhir"
    )
    kandang_id: Optional[str] = None


# ─── DB Query Helpers ─────────────────────────────────────────────────────────
async def _resolve_kandang_id(
    kandang_id_str: Optional[str], db: AsyncSession
) -> Optional[uuid.UUID]:
    """Resolve kandang_id dari request atau fallback ke single kandang aktif."""
    if kandang_id_str:
        try:
            return uuid.UUID(kandang_id_str)
        except ValueError:
            pass
    # Fallback: ambil kandang aktif pertama
    result = await db.execute(
        select(Kandang).where(Kandang.is_active == True).limit(1)
    )
    kandang = result.scalar_one_or_none()
    return kandang.id if kandang else None


async def _fetch_sensor_history(
    db: AsyncSession, kandang_id: uuid.UUID, limit: int
) -> List[SensorData]:
    """Ambil N data sensor terakhir, diurutkan TERLAMA → TERBARU."""
    query = (
        select(SensorData)
        .where(SensorData.kandang_id == kandang_id)
        .order_by(desc(SensorData.timestamp))
        .limit(limit)
    )
    result = await db.execute(query)
    records = list(result.scalars().all())
    records.reverse()  # terlama dulu → terbaru di akhir
    return records


def _sensor_to_cls_dict(s: SensorData, luas_kandang: float = 120.0) -> dict:
    """Konversi SensorData row ke dict untuk classification model."""
    return {
        'Suhu': float(s.suhu),
        'Kelembaban': float(s.kelembaban),
        'Amoniak': float(s.amoniak),
        'Pakan': float(s.pakan or 0),
        'Minum': float(s.minum or 0),
        'Bobot': float(s.bobot or 0),
        'Populasi': float(s.populasi or 0),
        'Luas Kandang': luas_kandang,
        'Hour': s.timestamp.hour if s.timestamp else 12,
    }


def _sensor_to_fc_dict(s: SensorData) -> dict:
    """Konversi SensorData row ke dict untuk forecasting model."""
    return {
        'Suhu': float(s.suhu),
        'Kelembaban': float(s.kelembaban),
        'Amoniak': float(s.amoniak),
        'Hour': s.timestamp.hour if s.timestamp else 12,
        'Death': float(s.death or 0),
    }


# ─── Endpoints ────────────────────────────────────────────────────────────────
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
            "type": "LSTM (Long Short-Term Memory)",
            "version": "3.0.0",
            "scenario": "Balanced (Dampened Class Weight)",
            "status": "loaded",
            "description": "Klasifikasi kondisi kandang (Normal/Abnormal) berbasis LSTM",
            "input_features": [
                "Suhu", "Kelembaban", "Amoniak", "Pakan", "Minum", "Bobot",
                "Populasi", "Luas Kandang", "Hour", "Session",
                "Feed_Water_Ratio", "Density",
                "delta_Suhu", "delta_Kelembaban", "delta_Amoniak",
                "rolling_mean_Suhu", "rolling_mean_Kelembaban", "rolling_mean_Amoniak",
                "rolling_std_Suhu", "rolling_std_Kelembaban", "rolling_std_Amoniak",
            ],
            "window_size": "12 timesteps",
            "output_classes": ["Normal", "Abnormal"],
            "metrics": {
                "accuracy": "86.64%",
                "f1_score": "86.52%",
                "auc": "94.37%",
                "specificity": "94.55%",
            },
        },
        forecasting_model={
            "name": "SmartFarm Forecasting Model",
            "type": "LSTM (Long Short-Term Memory)",
            "version": "2.0.0",
            "scenario": "Balanced (Sample Weights)",
            "status": "loaded",
            "description": "Prediksi jumlah kematian ayam 30 menit ke depan (Autoregressive)",
            "input_features": [
                "Suhu", "Kelembaban", "Amoniak", "Hour",
                "delta_Suhu", "delta_Kelembaban", "delta_Amoniak",
                "rolling_mean_Suhu", "rolling_mean_Kelembaban", "rolling_mean_Amoniak",
                "Death (autoregressive)",
            ],
            "window_size": "6 timesteps (3 jam lookback @ 30 menit)",
            "resampling": "30 menit",
            "output": "predicted_death (count)",
            "metrics": {
                "rmse": "12.9445",
                "mae": "10.6634",
                "r2": "0.7291",
            },
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
    "/history",
    summary="Get Prediction History (DL)",
    description="Riwayat hasil prediksi Deep Learning (classification & forecasting)",
)
async def get_prediction_history(
    type: Optional[str] = None,
    limit: int = 1000,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    _: User = Depends(get_current_user),
    kandang: Kandang = Depends(get_single_kandang),
    db: AsyncSession = Depends(get_db),
):
    import json

    start = start_date.date() if start_date else None
    end = end_date.date() if end_date else None

    svc = PredictionService(db)
    records, _ = await svc.get_history(
        kandang.id,
        page_size=limit,
        offset=0,
        prediction_type=type,
        model_type="dl",
        start_date=start,
        end_date=end,
    )

    data = []
    for r in records:
        data.append({
            "id": str(r.id),
            "type": r.type,
            "prediction": r.prediction,
            "confidence": r.confidence,
            "predicted_death": r.predicted_death,
            "raw_prediction": r.raw_prediction,
            "input_data": json.loads(r.input_data) if r.input_data else None,
            "created_at": r.created_at.isoformat(),
        })

    return success_response(data=data, message=f"{len(data)} riwayat prediksi DL")


# ─── POST /classify ──────────────────────────────────────────────────────────
@router.post(
    "/classify",
    summary="Run Classification Prediction",
    description="Jalankan prediksi klasifikasi (Normal/Abnormal) berdasarkan data sensor saat ini.",
)
async def classify(
    req: ClassifyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    features = {
        'Hari Ke-': req.hari_ke,
        'Suhu': req.suhu,
        'Kelembaban': req.kelembaban,
        'Amoniak': req.amoniak,
        'Pakan': req.pakan,
        'Minum': req.minum,
        'Bobot': req.bobot,
        'Populasi': req.populasi,
        'Luas Kandang': req.luas_kandang,
        'Hour': req.hour,
    }

    # ── Query riwayat sensor dari database ────────────────────────────────
    db_history = None
    kandang_uuid = await _resolve_kandang_id(req.kandang_id, db)

    if kandang_uuid:
        cls_needed = CLS_TIME_STEPS + CLS_ROLLING_WINDOW  # 18
        sensors = await _fetch_sensor_history(db, kandang_uuid, limit=cls_needed)
        if sensors:
            db_history = [_sensor_to_cls_dict(s, req.luas_kandang) for s in sensors]
            logger.info(f"Classify: ditemukan {len(sensors)} data sensor di DB")

    # ── Jalankan prediksi ─────────────────────────────────────────────────
    try:
        result = predict_classification(features, db_history=db_history)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Classification failed: {str(e)}"
        )

    # ── Simpan ke database ────────────────────────────────────────────────
    if kandang_uuid:
        try:
            svc = PredictionService(db)
            await svc.save_classification(
                kandang_id=kandang_uuid,
                prediction=result['class'],
                confidence=result['confidence'],
                input_data={
                    "suhu": req.suhu,
                    "kelembaban": req.kelembaban,
                    "amoniak": req.amoniak,
                    "hari_ke": req.hari_ke,
                    "source": "api_manual",
                    "db_history_count": len(db_history) if db_history else 0,
                },
                model_type="dl",
            )
        except Exception:
            pass  # Don't fail the prediction if DB save fails

    return success_response(
        data={
            "classification": result['class'],
            "confidence": result['confidence'],
            "probability": result['probability'],
        },
        message=f"Klasifikasi: {result['class']} ({result['confidence']:.1%})",
    )


# ─── POST /forecast ──────────────────────────────────────────────────────────
@router.post(
    "/forecast",
    summary="Run Death Forecasting",
    description="Prediksi jumlah kematian ayam berdasarkan riwayat data sensor (min. 4 data point).",
)
async def forecast(
    req: ForecastRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sensor_history = [item.model_dump() for item in req.sensor_history]

    # ── Query riwayat sensor dari database ────────────────────────────────
    db_history = None
    kandang_uuid = await _resolve_kandang_id(req.kandang_id, db)

    if kandang_uuid:
        fc_needed = FC_TIME_STEPS + FC_ROLLING_WINDOW  # 9
        sensors = await _fetch_sensor_history(db, kandang_uuid, limit=fc_needed)
        if sensors:
            db_history = [_sensor_to_fc_dict(s) for s in sensors]
            logger.info(f"Forecast: ditemukan {len(sensors)} data sensor di DB")

    # ── Jalankan prediksi ─────────────────────────────────────────────────
    try:
        result = predict_forecasting(sensor_history, db_history=db_history)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Forecasting failed: {str(e)}"
        )

    has_risk = result['predicted_death'] > 0

    # ── Simpan ke database ────────────────────────────────────────────────
    if kandang_uuid:
        try:
            svc = PredictionService(db)
            await svc.save_forecasting(
                kandang_id=kandang_uuid,
                predicted_death=result['predicted_death'],
                raw_prediction=result['raw_prediction'],
                input_data={
                    "sensor_history": sensor_history,
                    "source": "api_manual",
                    "db_history_count": len(db_history) if db_history else 0,
                },
                model_type="dl",
            )
        except Exception:
            pass

    return success_response(
        data={
            "predicted_death": result['predicted_death'],
            "raw_prediction": result['raw_prediction'],
            "has_risk": has_risk,
        },
        message=f"Prediksi: {result['predicted_death']} kematian {'⚠️ RISIKO' if has_risk else '(aman)'}",
    )
