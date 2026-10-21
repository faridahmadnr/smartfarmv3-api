"""
Prediction Service - Simpan dan ambil hasil prediksi ML
"""
import uuid
import json
import datetime
from typing import Optional, List, Tuple, Dict, Any

from sqlalchemy import select, desc, asc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prediction import Prediction


_SORT_COLUMNS = {
    "created_at": Prediction.created_at,
    "prediction": Prediction.prediction,
    "confidence": Prediction.confidence,
    "predicted_death": Prediction.predicted_death,
    "raw_prediction": Prediction.raw_prediction,
}


class PredictionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def save_classification(
        self,
        kandang_id: uuid.UUID,
        prediction: str,
        confidence: float,
        input_data: dict,
        sensor_data_id: Optional[uuid.UUID] = None,
        model_type: str = "ml",
    ) -> Prediction:
        record = Prediction(
            kandang_id=kandang_id,
            sensor_data_id=sensor_data_id,
            type="classification",
            model_type=model_type,
            prediction=prediction,
            confidence=confidence,
            input_data=json.dumps(input_data),
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        return record

    async def save_forecasting(
        self,
        kandang_id: uuid.UUID,
        predicted_death: int,
        raw_prediction: float,
        input_data: dict,
        sensor_data_id: Optional[uuid.UUID] = None,
        model_type: str = "ml",
    ) -> Prediction:
        record = Prediction(
            kandang_id=kandang_id,
            sensor_data_id=sensor_data_id,
            type="forecasting",
            model_type=model_type,
            predicted_death=predicted_death,
            raw_prediction=raw_prediction,
            input_data=json.dumps(input_data),
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        return record

    def _base_filters(
        self,
        kandang_id: uuid.UUID,
        model_type: str,
        prediction_type: Optional[str],
        start_date: Optional[datetime.date],
        end_date: Optional[datetime.date],
    ):
        conditions = [
            Prediction.kandang_id == kandang_id,
            Prediction.model_type == model_type,
        ]
        if prediction_type:
            conditions.append(Prediction.type == prediction_type)
        if start_date:
            conditions.append(Prediction.created_at >= datetime.datetime.combine(start_date, datetime.time.min))
        if end_date:
            conditions.append(Prediction.created_at < datetime.datetime.combine(end_date + datetime.timedelta(days=1), datetime.time.min))
        return conditions

    async def get_history(
        self,
        kandang_id: uuid.UUID,
        page_size: int = 50,
        offset: int = 0,
        prediction_type: Optional[str] = None,
        model_type: str = "ml",
        start_date: Optional[datetime.date] = None,
        end_date: Optional[datetime.date] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> Tuple[List[Prediction], int]:
        conditions = self._base_filters(kandang_id, model_type, prediction_type, start_date, end_date)

        sort_col = _SORT_COLUMNS.get(sort_by, Prediction.created_at)
        order_fn = desc if sort_order == "desc" else asc

        count_q = select(func.count()).select_from(
            select(Prediction).where(*conditions).subquery()
        )
        total_result = await self.db.execute(count_q)
        total = total_result.scalar() or 0

        query = (
            select(Prediction)
            .where(*conditions)
            .order_by(order_fn(sort_col))
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def get_summary(
        self,
        kandang_id: uuid.UUID,
        model_type: str = "ml",
        start_date: Optional[datetime.date] = None,
        end_date: Optional[datetime.date] = None,
    ) -> Dict[str, Any]:
        async def count_where(*extra):
            conditions = self._base_filters(kandang_id, model_type, None, start_date, end_date)
            q = select(func.count()).where(*conditions, *extra)
            r = await self.db.execute(q)
            return r.scalar() or 0

        cls_total    = await count_where(Prediction.type == "classification")
        cls_normal   = await count_where(Prediction.type == "classification", Prediction.prediction == "Normal")
        cls_abnormal = await count_where(Prediction.type == "classification", Prediction.prediction == "Abnormal")
        fc_total     = await count_where(Prediction.type == "forecasting")
        fc_safe      = await count_where(Prediction.type == "forecasting", Prediction.predicted_death == 0)
        fc_risk      = await count_where(Prediction.type == "forecasting", Prediction.predicted_death > 0)

        return {
            "classification": {"total": cls_total, "normal": cls_normal, "abnormal": cls_abnormal},
            "forecasting": {"total": fc_total, "safe": fc_safe, "risk": fc_risk},
        }
