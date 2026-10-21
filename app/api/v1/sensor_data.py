import uuid
from typing import Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.kandang import Kandang
from app.schemas.base import BaseResponse, success_response
from app.schemas.sensor_data import (
    SensorDataCreate,
    SensorDataIoTCreate,
    SensorDataManualUpdate,
    SensorDataResponse,
    SensorDataListResponse,
    SensorDataStats,
)
from app.services.sensor_data_service import SensorDataService
from app.api.deps import get_current_user, get_iot_auth, get_single_kandang, require_roles
from app.models.user import UserRole

router = APIRouter()


@router.post(
    "/iot",
    response_model=BaseResponse[SensorDataResponse],
    status_code=status.HTTP_201_CREATED,
    summary="IoT Device - Submit Sensor Data",
    description="Endpoint khusus perangkat IoT (ESP32). Auth via X-API-Key header.",
)
async def create_sensor_data_iot(
    data: SensorDataIoTCreate,
    _: str = Depends(get_iot_auth),
    kandang: Kandang = Depends(get_single_kandang),
    db: AsyncSession = Depends(get_db),
):
    from app.ml.model_loader import predict_classification, predict_forecasting
    from app.services.notification_service import NotificationService
    from app.services.prediction_service import PredictionService
    from app.services.death_report_service import DeathReportService
    import logging

    logger = logging.getLogger(__name__)

    sensor_service = SensorDataService(db)
    hari_ke = await sensor_service.get_hari_ke(kandang.id, kandang.tanggal_mulai_siklus)

    death_service = DeathReportService(db)
    today_deaths = await death_service.get_total_today(kandang.id)

    from app.services.daily_log_service import DailyLogService
    daily_log_service = DailyLogService(db)
    today_log = await daily_log_service.get_today(kandang.id)

    last_readings = await sensor_service.get_latest(kandang.id, limit=1)
    if today_log and today_log.populasi is not None:
        today_populasi = today_log.populasi - today_deaths
    elif last_readings and last_readings[-1].populasi is not None:
        today_populasi = last_readings[-1].populasi
    else:
        today_populasi = None

    sensor_create = SensorDataCreate(
        timestamp=datetime.now(),
        hari_ke=hari_ke,
        suhu=data.temperature,
        kelembaban=data.humidity,
        amoniak=data.ammonia,
        death=today_deaths,
        populasi=today_populasi,
        pakan=today_log.pakan if today_log else None,
        minum=today_log.minum if today_log else None,
    )
    sensor_data = await sensor_service.create(sensor_create, kandang_id=kandang.id)

    auto_prediction_results = {}

    try:
        features = {
            'Hari Ke-': hari_ke,
            'Suhu': data.temperature,
            'Kelembaban': data.humidity,
            'Amoniak': data.ammonia,
            'Pakan': today_log.pakan if today_log and today_log.pakan is not None else 0,
            'Minum': today_log.minum if today_log and today_log.minum is not None else 0,
            'Bobot': today_log.bobot if today_log and today_log.bobot is not None else 0,
            'Populasi': today_populasi if today_populasi is not None else 0,
            'Death': today_deaths,
            'Luas Kandang': kandang.kapasitas / 10 if kandang.kapasitas else 120,
            'Hour': sensor_data.timestamp.hour,
        }
        cls_result = predict_classification(features)
        auto_prediction_results["classification"] = {
            "prediction": cls_result['class'],
            "confidence": cls_result['confidence'],
            "is_abnormal": cls_result['class'] == 'Abnormal',
        }

        try:
            prediction_svc = PredictionService(db)
            await prediction_svc.save_classification(
                kandang_id=kandang.id,
                prediction=cls_result['class'],
                confidence=cls_result['confidence'],
                input_data={"suhu": data.temperature, "kelembaban": data.humidity, "amoniak": data.ammonia, "hari_ke": hari_ke, "source": "iot_auto"},
                sensor_data_id=sensor_data.id,
                model_type="ml",
            )
        except Exception as log_err:
            logger.warning(f"IoT classification save failed: {log_err}")

        if cls_result['class'] == 'Abnormal':
            try:
                notification_service = NotificationService(db)
                await notification_service.create_classification_alert(
                    kandang_id=kandang.id,
                    prediction=cls_result['class'],
                    sensor_data=features,
                )
            except Exception as notif_err:
                logger.warning(f"IoT classification notification failed: {notif_err}")
    except Exception as e:
        logger.warning(f"IoT auto-classification failed: {e}")
        auto_prediction_results["classification"] = {"error": str(e)}

    try:
        from app.models.prediction import Prediction
        from sqlalchemy import select as sa_select, desc as sa_desc

        last_fc_result = await db.execute(
            sa_select(Prediction.created_at)
            .where(Prediction.kandang_id == kandang.id, Prediction.type == "forecasting", Prediction.model_type == "ml")
            .order_by(sa_desc(Prediction.created_at))
            .limit(1)
        )
        last_fc_time = last_fc_result.scalar_one_or_none()
        forecast_cooldown_ok = (
            last_fc_time is None or
            (datetime.utcnow() - last_fc_time.replace(tzinfo=None)) >= timedelta(minutes=30)
        )

        recent_data = await sensor_service.get_latest_at_interval(kandang_id=kandang.id, n_points=4, interval_minutes=30)
        if len(recent_data) >= 4 and forecast_cooldown_ok:
            sensor_history = [
                {'temp': sd.suhu, 'hum': sd.kelembaban, 'ammo': sd.amoniak, 'Death': sd.death or 0}
                for sd in recent_data[-4:]
            ]
            fc_result = predict_forecasting(sensor_history)
            auto_prediction_results["forecasting"] = {
                "predicted_death": fc_result['predicted_death'],
                "has_risk": fc_result['predicted_death'] > 0,
            }

            try:
                prediction_svc = PredictionService(db)
                await prediction_svc.save_forecasting(
                    kandang_id=kandang.id,
                    predicted_death=fc_result['predicted_death'],
                    raw_prediction=fc_result['raw_prediction'],
                    input_data={"sensor_history": sensor_history, "source": "iot_auto"},
                    sensor_data_id=sensor_data.id,
                    model_type="ml",
                )
            except Exception as fc_save_err:
                logger.warning(f"IoT forecasting save failed: {fc_save_err}")

            if fc_result['predicted_death'] > 1:
                try:
                    notification_service = NotificationService(db)
                    await notification_service.create_death_forecast_alert(
                        kandang_id=kandang.id,
                        predicted_death=fc_result['predicted_death'],
                        raw_prediction=fc_result['raw_prediction'],
                    )
                except Exception as notif_err:
                    logger.warning(f"IoT forecast notification failed: {notif_err}")
        else:
            auto_prediction_results["forecasting"] = {"skipped": True, "reason": f"Need 4 data points x 30 menit, baru ada {len(recent_data)}"}
    except Exception as e:
        logger.warning(f"IoT auto-forecasting failed: {e}")
        auto_prediction_results["forecasting"] = {"error": str(e)}

    # ─── Deep Learning Auto-Prediction (Opsi B) ───
    try:
        from app.ml.model_loader_dl import (
            predict_classification as predict_classification_dl,
            predict_forecasting as predict_forecasting_dl
        )
        from app.services.prediction_service import PredictionService

        # 1. DL Classification
        try:
            features_dl = {
                'Hari Ke-': hari_ke,
                'Suhu': data.temperature,
                'Kelembaban': data.humidity,
                'Amoniak': data.ammonia,
                'Pakan': today_log.pakan if today_log and today_log.pakan is not None else 0,
                'Minum': today_log.minum if today_log and today_log.minum is not None else 0,
                'Bobot': today_log.bobot if today_log and today_log.bobot is not None else 0,
                'Populasi': today_populasi if today_populasi is not None else 0,
                'Luas Kandang': kandang.kapasitas / 10 if kandang.kapasitas else 120,
                'Hour': sensor_data.timestamp.hour,
            }
            cls_dl_result = predict_classification_dl(features_dl)
            auto_prediction_results["classification_dl"] = {
                "prediction": cls_dl_result['class'],
                "confidence": cls_dl_result['confidence'],
                "is_abnormal": cls_dl_result['class'] == 'Abnormal',
            }

            try:
                prediction_svc = PredictionService(db)
                await prediction_svc.save_classification(
                    kandang_id=kandang.id,
                    prediction=cls_dl_result['class'],
                    confidence=cls_dl_result['confidence'],
                    input_data={"suhu": data.temperature, "kelembaban": data.humidity, "amoniak": data.ammonia, "hari_ke": hari_ke, "source": "iot_auto_dl"},
                    sensor_data_id=sensor_data.id,
                    model_type="dl",
                )
            except Exception as log_dl_err:
                logger.warning(f"IoT classification DL save failed: {log_dl_err}")

            if cls_dl_result['class'] == 'Abnormal':
                try:
                    notification_service = NotificationService(db)
                    await notification_service.create_classification_alert(
                        kandang_id=kandang.id,
                        prediction=cls_dl_result['class'],
                        sensor_data=features_dl,
                    )
                except Exception as notif_err:
                    logger.warning(f"IoT classification DL notification failed: {notif_err}")
        except Exception as cls_dl_err:
            logger.warning(f"IoT auto-classification DL failed: {cls_dl_err}")
            auto_prediction_results["classification_dl"] = {"error": str(cls_dl_err)}

        # 2. DL Forecasting
        try:
            from app.models.prediction import Prediction
            from sqlalchemy import select as sa_select, desc as sa_desc

            last_fc_dl_result = await db.execute(
                sa_select(Prediction.created_at)
                .where(Prediction.kandang_id == kandang.id, Prediction.type == "forecasting", Prediction.model_type == "dl")
                .order_by(sa_desc(Prediction.created_at))
                .limit(1)
            )
            last_fc_dl_time = last_fc_dl_result.scalar_one_or_none()
            forecast_dl_cooldown_ok = (
                last_fc_dl_time is None or
                (datetime.utcnow() - last_fc_dl_time.replace(tzinfo=None)) >= timedelta(minutes=30)
            )

            recent_dl_data = await sensor_service.get_latest_at_interval(kandang_id=kandang.id, n_points=4, interval_minutes=30)
            if len(recent_dl_data) >= 4 and forecast_dl_cooldown_ok:
                sensor_dl_history = [
                    {'temp': sd.suhu, 'hum': sd.kelembaban, 'ammo': sd.amoniak, 'Death': sd.death or 0}
                    for sd in recent_dl_data[-4:]
                ]
                fc_dl_result = predict_forecasting_dl(sensor_dl_history)
                auto_prediction_results["forecasting_dl"] = {
                    "predicted_death": fc_dl_result['predicted_death'],
                    "has_risk": fc_dl_result['predicted_death'] > 0,
                }

                try:
                    prediction_svc = PredictionService(db)
                    await prediction_svc.save_forecasting(
                        kandang_id=kandang.id,
                        predicted_death=fc_dl_result['predicted_death'],
                        raw_prediction=fc_dl_result['raw_prediction'],
                        input_data={"sensor_history": sensor_dl_history, "source": "iot_auto_dl"},
                        sensor_data_id=sensor_data.id,
                        model_type="dl",
                    )
                except Exception as fc_dl_save_err:
                    logger.warning(f"IoT forecasting DL save failed: {fc_dl_save_err}")

                if fc_dl_result['predicted_death'] > 1:
                    try:
                        notification_service = NotificationService(db)
                        await notification_service.create_death_forecast_alert(
                            kandang_id=kandang.id,
                            predicted_death=fc_dl_result['predicted_death'],
                            raw_prediction=fc_dl_result['raw_prediction'],
                        )
                    except Exception as notif_err:
                        logger.warning(f"IoT forecast DL notification failed: {notif_err}")
            else:
                auto_prediction_results["forecasting_dl"] = {"skipped": True, "reason": "Cooldown or insufficient points"}
        except Exception as fc_dl_err:
            logger.warning(f"IoT auto-forecasting DL failed: {fc_dl_err}")
            auto_prediction_results["forecasting_dl"] = {"error": str(fc_dl_err)}

    except Exception as dl_wrapper_err:
        logger.warning(f"DL Auto-Prediction wrapper failed: {dl_wrapper_err}")

    try:
        from app.services.notification_service import manager
        await manager.broadcast_all({
            "type": "sensor_data",
            "data": {
                "id": str(sensor_data.id),
                "kandang_id": str(kandang.id),
                "timestamp": sensor_data.timestamp.isoformat(),
                "hari_ke": sensor_data.hari_ke,
                "suhu": sensor_data.suhu,
                "kelembaban": sensor_data.kelembaban,
                "amoniak": sensor_data.amoniak,
                "auto_prediction": auto_prediction_results,
            },
        })
    except Exception as ws_err:
        logger.warning(f"IoT WebSocket broadcast failed: {ws_err}")

    return success_response(data=SensorDataResponse.model_validate(sensor_data), message="Data IoT berhasil disimpan")


@router.post(
    "",
    response_model=BaseResponse[SensorDataResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create Sensor Data (Manual - Admin Only)",
    description="Manual sensor data input by Admin as fallback when IoT device is offline. Auto-triggers ML predictions.",
)
async def create_sensor_data(
    data: SensorDataCreate,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    kandang: Kandang = Depends(get_single_kandang),
    db: AsyncSession = Depends(get_db),
):
    from app.ml.model_loader import predict_classification, predict_forecasting
    from app.services.notification_service import NotificationService
    from app.services.activity_log_service import ActivityLogService
    from app.api.deps import get_request_info
    import logging

    logger = logging.getLogger(__name__)

    sensor_service = SensorDataService(db)
    sensor_data = await sensor_service.create(data, kandang_id=kandang.id, recorded_by=current_user.id)

    auto_prediction_results = {}

    try:
        features = {
            'Hari Ke-': data.hari_ke,
            'Suhu': data.suhu,
            'Kelembaban': data.kelembaban,
            'Amoniak': data.amoniak,
            'Pakan': data.pakan or 0,
            'Minum': data.minum or 0,
            'Bobot': data.bobot or 0,
            'Populasi': data.populasi or 0,
            'Luas Kandang': kandang.kapasitas / 10 if kandang.kapasitas else 120,
            'Hour': sensor_data.timestamp.hour if sensor_data.timestamp else 12,
        }
        cls_result = predict_classification(features)
        auto_prediction_results["classification"] = {
            "prediction": cls_result['class'],
            "confidence": cls_result['confidence'],
            "is_abnormal": cls_result['class'] == 'Abnormal',
        }

        if cls_result['class'] == 'Abnormal':
            try:
                notification_service = NotificationService(db)
                await notification_service.create_classification_alert(
                    kandang_id=kandang.id,
                    prediction=cls_result['class'],
                    sensor_data=features,
                )
            except Exception as notif_err:
                logger.warning(f"Auto-classification notification failed: {notif_err}")

    except Exception as e:
        logger.warning(f"Auto-classification failed: {e}")
        auto_prediction_results["classification"] = {"error": str(e)}

    try:
        recent_data = await sensor_service.get_latest(kandang_id=kandang.id, limit=4)
        if len(recent_data) >= 4:
            sensor_history = [
                {'temp': sd.suhu, 'hum': sd.kelembaban, 'ammo': sd.amoniak, 'Death': sd.death or 0}
                for sd in recent_data[-4:]
            ]
            fc_result = predict_forecasting(sensor_history)
            auto_prediction_results["forecasting"] = {
                "predicted_death": fc_result['predicted_death'],
                "has_risk": fc_result['predicted_death'] > 0,
            }
            if fc_result['predicted_death'] > 1:
                try:
                    notification_service = NotificationService(db)
                    await notification_service.create_death_forecast_alert(
                        kandang_id=kandang.id,
                        predicted_death=fc_result['predicted_death'],
                        raw_prediction=fc_result['raw_prediction'],
                    )
                except Exception as notif_err:
                    logger.warning(f"Auto-forecast notification failed: {notif_err}")
        else:
            auto_prediction_results["forecasting"] = {"skipped": True, "reason": f"Need 4+ data points, have {len(recent_data)}"}
    except Exception as e:
        logger.warning(f"Auto-forecasting failed: {e}")
        auto_prediction_results["forecasting"] = {"error": str(e)}

    # ─── Deep Learning Auto-Prediction (Opsi B) ───
    try:
        from app.ml.model_loader_dl import (
            predict_classification as predict_classification_dl,
            predict_forecasting as predict_forecasting_dl
        )
        from app.services.prediction_service import PredictionService

        # 1. DL Classification (Manual)
        try:
            features_dl = {
                'Hari Ke-': data.hari_ke,
                'Suhu': data.suhu,
                'Kelembaban': data.kelembaban,
                'Amoniak': data.amoniak,
                'Pakan': data.pakan or 0,
                'Minum': data.minum or 0,
                'Bobot': data.bobot or 0,
                'Populasi': data.populasi or 0,
                'Luas Kandang': kandang.kapasitas / 10 if kandang.kapasitas else 120,
                'Hour': sensor_data.timestamp.hour if sensor_data.timestamp else 12,
            }
            cls_dl_result = predict_classification_dl(features_dl)
            auto_prediction_results["classification_dl"] = {
                "prediction": cls_dl_result['class'],
                "confidence": cls_dl_result['confidence'],
                "is_abnormal": cls_dl_result['class'] == 'Abnormal',
            }

            try:
                prediction_svc = PredictionService(db)
                await prediction_svc.save_classification(
                    kandang_id=kandang.id,
                    prediction=cls_dl_result['class'],
                    confidence=cls_dl_result['confidence'],
                    input_data={"suhu": data.suhu, "kelembaban": data.kelembaban, "amoniak": data.amoniak, "hari_ke": data.hari_ke, "source": "manual_dl"},
                    sensor_data_id=sensor_data.id,
                    model_type="dl",
                )
            except Exception as log_dl_err:
                logger.warning(f"Manual classification DL save failed: {log_dl_err}")

            if cls_dl_result['class'] == 'Abnormal':
                try:
                    notification_service = NotificationService(db)
                    await notification_service.create_classification_alert(
                        kandang_id=kandang.id,
                        prediction=cls_dl_result['class'],
                        sensor_data=features_dl,
                    )
                except Exception as notif_err:
                    logger.warning(f"Manual classification DL notification failed: {notif_err}")
        except Exception as cls_dl_err:
            logger.warning(f"Manual auto-classification DL failed: {cls_dl_err}")
            auto_prediction_results["classification_dl"] = {"error": str(cls_dl_err)}

        # 2. DL Forecasting (Manual)
        try:
            recent_dl_data = await sensor_service.get_latest(kandang_id=kandang.id, limit=4)
            if len(recent_dl_data) >= 4:
                sensor_dl_history = [
                    {'temp': sd.suhu, 'hum': sd.kelembaban, 'ammo': sd.amoniak, 'Death': sd.death or 0}
                    for sd in recent_dl_data[-4:]
                ]
                fc_dl_result = predict_forecasting_dl(sensor_dl_history)
                auto_prediction_results["forecasting_dl"] = {
                    "predicted_death": fc_dl_result['predicted_death'],
                    "has_risk": fc_dl_result['predicted_death'] > 0,
                }

                try:
                    prediction_svc = PredictionService(db)
                    await prediction_svc.save_forecasting(
                        kandang_id=kandang.id,
                        predicted_death=fc_dl_result['predicted_death'],
                        raw_prediction=fc_dl_result['raw_prediction'],
                        input_data={"sensor_history": sensor_dl_history, "source": "manual_dl"},
                        sensor_data_id=sensor_data.id,
                        model_type="dl",
                    )
                except Exception as fc_dl_save_err:
                    logger.warning(f"Manual forecasting DL save failed: {fc_dl_save_err}")

                if fc_dl_result['predicted_death'] > 1:
                    try:
                        notification_service = NotificationService(db)
                        await notification_service.create_death_forecast_alert(
                            kandang_id=kandang.id,
                            predicted_death=fc_dl_result['predicted_death'],
                            raw_prediction=fc_dl_result['raw_prediction'],
                        )
                    except Exception as notif_err:
                        logger.warning(f"Manual forecast DL notification failed: {notif_err}")
            else:
                auto_prediction_results["forecasting_dl"] = {"skipped": True, "reason": f"Need 4+ points, have {len(recent_dl_data)}"}
        except Exception as fc_dl_err:
            logger.warning(f"Manual auto-forecasting DL failed: {fc_dl_err}")
            auto_prediction_results["forecasting_dl"] = {"error": str(fc_dl_err)}

    except Exception as dl_wrapper_err:
        logger.warning(f"DL Auto-Prediction manual wrapper failed: {dl_wrapper_err}")

    try:
        from app.services.notification_service import manager
        await manager.broadcast_all({
            "type": "sensor_data",
            "data": {
                "id": str(sensor_data.id),
                "kandang_id": str(kandang.id),
                "timestamp": sensor_data.timestamp.isoformat() if sensor_data.timestamp else None,
                "hari_ke": sensor_data.hari_ke,
                "suhu": sensor_data.suhu,
                "kelembaban": sensor_data.kelembaban,
                "amoniak": sensor_data.amoniak,
                "pakan": sensor_data.pakan,
                "minum": sensor_data.minum,
                "populasi": sensor_data.populasi,
                "bobot": sensor_data.bobot,
                "death": sensor_data.death,
                "auto_prediction": auto_prediction_results,
            },
        })
    except Exception as ws_err:
        logger.warning(f"WebSocket broadcast failed: {ws_err}")

    request_info = await get_request_info(request)
    activity_service = ActivityLogService(db)
    await activity_service.log_action(
        user_id=current_user.id,
        action="create_sensor_data",
        resource="sensor_data",
        resource_id=sensor_data.id,
        request_info=request_info,
    )

    return success_response(data=SensorDataResponse.model_validate(sensor_data), message="Data sensor berhasil disimpan")


@router.put(
    "/{sensor_data_id}/manual",
    response_model=BaseResponse[SensorDataResponse],
    summary="Update Manual Fields",
    description="Update manually-input fields (pakan, minum, bobot, populasi, death)",
)
async def update_manual_fields(
    sensor_data_id: uuid.UUID,
    data: SensorDataManualUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sensor_service = SensorDataService(db)
    sensor_data = await sensor_service.get_by_id(sensor_data_id)

    if not sensor_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data sensor tidak ditemukan")

    updated = await sensor_service.update_manual_fields(sensor_data_id, data, current_user.id)
    return success_response(data=SensorDataResponse.model_validate(updated), message="Data manual berhasil diupdate")


@router.get(
    "",
    response_model=BaseResponse[SensorDataListResponse],
    summary="Get Sensor Data",
    description="Get paginated sensor data",
)
async def get_sensor_data(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=1000),
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    current_user: User = Depends(get_current_user),
    kandang: Kandang = Depends(get_single_kandang),
    db: AsyncSession = Depends(get_db),
):
    sensor_service = SensorDataService(db)
    items, total = await sensor_service.get_by_kandang(kandang.id, page, page_size, start_time, end_time)

    return success_response(
        data=SensorDataListResponse(
            items=[SensorDataResponse.model_validate(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
        ),
        message="Data sensor berhasil diambil",
    )


@router.get(
    "/latest",
    response_model=BaseResponse[list[SensorDataResponse]],
    summary="Get Latest Sensor Data",
    description="Get latest N sensor data readings (default 4)",
)
async def get_latest_sensor_data(
    limit: int = Query(default=4, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    kandang: Kandang = Depends(get_single_kandang),
    db: AsyncSession = Depends(get_db),
):
    sensor_service = SensorDataService(db)
    items = await sensor_service.get_latest(kandang.id, limit)

    return success_response(data=[SensorDataResponse.model_validate(item) for item in items], message=f"{len(items)} data sensor terbaru")


@router.get(
    "/stats",
    response_model=BaseResponse[SensorDataStats],
    summary="Get Sensor Statistics",
    description="Get statistical summary of sensor data",
)
async def get_sensor_stats(
    hours: int = Query(default=24, ge=1, le=168),
    current_user: User = Depends(get_current_user),
    kandang: Kandang = Depends(get_single_kandang),
    db: AsyncSession = Depends(get_db),
):
    sensor_service = SensorDataService(db)
    stats = await sensor_service.get_stats(kandang.id, hours)

    if not stats:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tidak ada data sensor dalam periode yang diminta")

    return success_response(data=stats, message=f"Statistik {hours} jam terakhir")
