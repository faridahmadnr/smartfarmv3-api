"""Tests for sensor-data status behavior."""
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.api.v1 import sensor_data as sensor_data_api


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("minutes_ago", "expected_status"),
    [(None, "no_data"), (5, "online"), (40, "offline")],
)
async def test_iot_status_uses_latest_device_reading(
    monkeypatch, minutes_ago, expected_status
):
    last_seen = (
        None
        if minutes_ago is None
        else datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    )

    class FakeSensorDataService:
        def __init__(self, _db):
            pass

        async def get_latest_iot_timestamp(self, _kandang_id):
            return last_seen

    monkeypatch.setattr(sensor_data_api, "SensorDataService", FakeSensorDataService)

    response = await sensor_data_api.get_iot_status(
        current_user=SimpleNamespace(),
        kandang=SimpleNamespace(id=uuid.uuid4()),
        db=object(),
    )

    assert response["data"].status == expected_status
    assert response["data"].last_seen == last_seen
