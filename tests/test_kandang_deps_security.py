"""
Tests for Kandang Scoped Dependencies and Cross-Tenant Isolation on Child Endpoints
(Daily Logs, Death Reports, Sensor Data, Predictions, and IoT Route).
"""
import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.user import User, UserRole
from app.models.kandang import Kandang
from app.config import get_settings


@pytest_asyncio.fixture
async def setup_two_tenants_with_data(db_session: AsyncSession, client: AsyncClient):
    """
    Setup dua tenant dengan user, kandang, dan kredensial auth.
    """
    settings = get_settings()

    # 1. Pemilik A & Kandang A
    pemilik_a = User(
        id=uuid.uuid4(),
        email="pemilik_a_deps@example.com",
        username="pemilikadeps",
        full_name="Pemilik A Deps",
        hashed_password=get_password_hash("password123"),
        role=UserRole.PEMILIK,
        is_active=True,
    )
    db_session.add(pemilik_a)
    await db_session.flush()

    kandang_a = Kandang(
        id=uuid.uuid4(),
        nama="Kandang Deps A",
        kode="KDG-DPA-001",
        lokasi="Blok A",
        kapasitas=5000,
        tipe_kandang="Closed House",
        is_active=True,
        pemilik_id=pemilik_a.id,
    )
    db_session.add(kandang_a)

    # 2. Pemilik B & Kandang B
    pemilik_b = User(
        id=uuid.uuid4(),
        email="pemilik_b_deps@example.com",
        username="pemilikbdeps",
        full_name="Pemilik B Deps",
        hashed_password=get_password_hash("password123"),
        role=UserRole.PEMILIK,
        is_active=True,
    )
    db_session.add(pemilik_b)
    await db_session.flush()

    kandang_b = Kandang(
        id=uuid.uuid4(),
        nama="Kandang Deps B",
        kode="KDG-DPB-001",
        lokasi="Blok B",
        kapasitas=3000,
        tipe_kandang="Open House",
        is_active=True,
        pemilik_id=pemilik_b.id,
    )
    db_session.add(kandang_b)

    # 3. Pemilik C (tanpa kandang)
    pemilik_c = User(
        id=uuid.uuid4(),
        email="pemilik_c_deps@example.com",
        username="pemilikcdeps",
        full_name="Pemilik C Deps",
        hashed_password=get_password_hash("password123"),
        role=UserRole.PEMILIK,
        is_active=True,
    )
    db_session.add(pemilik_c)

    await db_session.commit()

    async def login(username: str) -> dict:
        res = await client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": "password123"},
        )
        assert res.status_code == 200, f"Login failed for {username}: {res.text}"
        token = res.json()["data"]["access_token"]
        return {"Authorization": f"Bearer {token}"}

    headers_a = await login("pemilikadeps")
    headers_b = await login("pemilikbdeps")
    headers_c = await login("pemilikcdeps")

    return {
        "pemilik_a": pemilik_a,
        "kandang_a": kandang_a,
        "headers_a": headers_a,
        "pemilik_b": pemilik_b,
        "kandang_b": kandang_b,
        "headers_b": headers_b,
        "headers_c": headers_c,
        "iot_headers": {"X-API-Key": settings.iot_api_key},
    }


@pytest.mark.asyncio
class TestKandangDepsSecurity:

    async def test_cross_tenant_daily_log_blocked(
        self, client: AsyncClient, setup_two_tenants_with_data: dict
    ):
        """User A dilarang membaca atau menulis daily-log kandang B (403 Forbidden)."""
        kandang_b_id = str(setup_two_tenants_with_data["kandang_b"].id)
        kandang_a_id = str(setup_two_tenants_with_data["kandang_a"].id)
        headers_a = setup_two_tenants_with_data["headers_a"]

        # 1. POST daily-log ke Kandang B dengan kredensial User A -> 403 Forbidden
        res_post_cross = await client.post(
            f"/api/v1/daily-logs?kandang_id={kandang_b_id}",
            json={"pakan": 100, "minum": 200, "populasi": 4000},
            headers=headers_a,
        )
        assert res_post_cross.status_code == 403

        # 2. GET daily-logs dari Kandang B dengan kredensial User A -> 403 Forbidden
        res_get_cross = await client.get(
            f"/api/v1/daily-logs?kandang_id={kandang_b_id}",
            headers=headers_a,
        )
        assert res_get_cross.status_code == 403

        # 3. POST daily-log ke Kandang A dengan kredensial User A yang sah -> 200 OK
        res_post_own = await client.post(
            f"/api/v1/daily-logs?kandang_id={kandang_a_id}",
            json={"pakan": 120, "minum": 250, "populasi": 4900},
            headers=headers_a,
        )
        assert res_post_own.status_code == 200
        assert res_post_own.json()["data"]["kandang_id"] == kandang_a_id

    async def test_cross_tenant_death_report_blocked(
        self, client: AsyncClient, setup_two_tenants_with_data: dict
    ):
        """User A dilarang membaca atau menulis death-report kandang B (403 Forbidden)."""
        kandang_b_id = str(setup_two_tenants_with_data["kandang_b"].id)
        kandang_a_id = str(setup_two_tenants_with_data["kandang_a"].id)
        headers_a = setup_two_tenants_with_data["headers_a"]

        # 1. POST death-report ke Kandang B dengan kredensial User A -> 403 Forbidden
        res_post_cross = await client.post(
            f"/api/v1/death-reports?kandang_id={kandang_b_id}",
            json={"count": 5, "notes": "Kematian palsu"},
            headers=headers_a,
        )
        assert res_post_cross.status_code == 403

        # 2. GET death-reports dari Kandang B dengan kredensial User A -> 403 Forbidden
        res_get_cross = await client.get(
            f"/api/v1/death-reports?kandang_id={kandang_b_id}",
            headers=headers_a,
        )
        assert res_get_cross.status_code == 403

        # 3. POST death-report ke Kandang A sah -> 200 OK
        res_post_own = await client.post(
            f"/api/v1/death-reports?kandang_id={kandang_a_id}",
            json={"count": 2, "notes": "Mati wajar"},
            headers=headers_a,
        )
        assert res_post_own.status_code == 200
        assert res_post_own.json()["data"]["kandang_id"] == kandang_a_id

    async def test_cross_tenant_sensor_data_blocked(
        self, client: AsyncClient, setup_two_tenants_with_data: dict
    ):
        """User A dilarang membaca telemetri/sensor-data kandang B (403 Forbidden)."""
        kandang_b_id = str(setup_two_tenants_with_data["kandang_b"].id)
        headers_a = setup_two_tenants_with_data["headers_a"]

        # 1. GET /sensor-data
        res_list = await client.get(
            f"/api/v1/sensor-data?kandang_id={kandang_b_id}",
            headers=headers_a,
        )
        assert res_list.status_code == 403

        # 2. GET /sensor-data/latest
        res_latest = await client.get(
            f"/api/v1/sensor-data/latest?kandang_id={kandang_b_id}",
            headers=headers_a,
        )
        assert res_latest.status_code == 403

        # 3. GET /sensor-data/stats
        res_stats = await client.get(
            f"/api/v1/sensor-data/stats?kandang_id={kandang_b_id}",
            headers=headers_a,
        )
        assert res_stats.status_code == 403

        # 4. GET /sensor-data/export/csv
        res_exp = await client.get(
            f"/api/v1/sensor-data/export/csv?kandang_id={kandang_b_id}",
            headers=headers_a,
        )
        assert res_exp.status_code == 403

    async def test_cross_tenant_predictions_blocked(
        self, client: AsyncClient, setup_two_tenants_with_data: dict
    ):
        """User A dilarang melihat riwayat prediksi kandang B (403 Forbidden)."""
        kandang_b_id = str(setup_two_tenants_with_data["kandang_b"].id)
        headers_a = setup_two_tenants_with_data["headers_a"]

        res_pred = await client.get(
            f"/api/v1/predictions/history?kandang_id={kandang_b_id}",
            headers=headers_a,
        )
        assert res_pred.status_code == 403

    async def test_fallback_without_kandang_id_scoped_to_user(
        self, client: AsyncClient, setup_two_tenants_with_data: dict
    ):
        """Tanpa parameter ?kandang_id=, fallback otomatis mengambil kandang milik user sendiri."""
        kandang_a_id = str(setup_two_tenants_with_data["kandang_a"].id)
        headers_a = setup_two_tenants_with_data["headers_a"]
        headers_c = setup_two_tenants_with_data["headers_c"]

        # User A memanggil GET daily-logs tanpa kandang_id -> otomatis kandang A
        res_a = await client.get("/api/v1/daily-logs", headers=headers_a)
        assert res_a.status_code == 200

        # User C (tanpa kandang) memanggil GET daily-logs tanpa kandang_id -> 404 Kandang tidak ditemukan
        res_c = await client.get("/api/v1/daily-logs", headers=headers_c)
        assert res_c.status_code == 404
        assert res_c.json()["detail"] == "Kandang tidak ditemukan"

    async def test_iot_endpoint_with_api_key_succeeds(
        self, client: AsyncClient, setup_two_tenants_with_data: dict
    ):
        """Endpoint IoT /sensor-data/iot menggunakan X-API-Key dan get_kandang_for_iot tetap berhasil."""
        iot_headers = setup_two_tenants_with_data["iot_headers"]
        kandang_a = setup_two_tenants_with_data["kandang_a"]

        # 1. IoT kirim data dengan kandang_kode eksplisit
        payload_with_code = {
            "temperature": 29.5,
            "humidity": 70.0,
            "ammonia": 4.0,
            "kandang_kode": kandang_a.kode,
        }
        res_iot_code = await client.post(
            "/api/v1/sensor-data/iot",
            json=payload_with_code,
            headers=iot_headers,
        )
        assert res_iot_code.status_code == 201
        assert res_iot_code.json()["data"]["kandang_id"] == str(kandang_a.id)

        # 2. IoT kirim data tanpa kode/id (fallback global get_kandang_for_iot)
        payload_no_id = {
            "temperature": 28.0,
            "humidity": 68.0,
            "ammonia": 3.0,
        }
        res_iot_fallback = await client.post(
            "/api/v1/sensor-data/iot",
            json=payload_no_id,
            headers=iot_headers,
        )
        assert res_iot_fallback.status_code == 201

    async def test_admin_can_access_all_endpoints(
        self, client: AsyncClient, admin_auth_headers: dict, setup_two_tenants_with_data: dict
    ):
        """Admin memiliki hak akses ke semua kandang lintas tenant."""
        kandang_a_id = str(setup_two_tenants_with_data["kandang_a"].id)
        kandang_b_id = str(setup_two_tenants_with_data["kandang_b"].id)

        # Admin akses daily-logs kandang A dan kandang B
        res_a = await client.get(f"/api/v1/daily-logs?kandang_id={kandang_a_id}", headers=admin_auth_headers)
        assert res_a.status_code == 200

        res_b = await client.get(f"/api/v1/daily-logs?kandang_id={kandang_b_id}", headers=admin_auth_headers)
        assert res_b.status_code == 200

        # Admin akses sensor-data kandang B
        res_sensor = await client.get(f"/api/v1/sensor-data?kandang_id={kandang_b_id}", headers=admin_auth_headers)
        assert res_sensor.status_code == 200

    async def test_put_delete_with_own_kandang_param_but_cross_tenant_resource_id_returns_404(
        self, client: AsyncClient, setup_two_tenants_with_data: dict
    ):
        """
        User A menyertakan ?kandang_id=<kandang A> (sah miliknya), tetapi log_id / report_id
        milik kandang B -> query wajib memfilter kandang_id == kandang A sehingga menghasilkan 404 Not Found.
        """
        kandang_a_id = str(setup_two_tenants_with_data["kandang_a"].id)
        kandang_b_id = str(setup_two_tenants_with_data["kandang_b"].id)
        headers_a = setup_two_tenants_with_data["headers_a"]
        headers_b = setup_two_tenants_with_data["headers_b"]

        # 1. User B membuat daily-log di kandang B
        res_b_log = await client.post(
            f"/api/v1/daily-logs?kandang_id={kandang_b_id}",
            json={"pakan": 80, "minum": 150, "populasi": 3000},
            headers=headers_b,
        )
        assert res_b_log.status_code == 200
        log_b_id = res_b_log.json()["data"]["id"]

        # 2. User B membuat death-report di kandang B
        res_b_death = await client.post(
            f"/api/v1/death-reports?kandang_id={kandang_b_id}",
            json={"count": 3, "notes": "Mati di kandang B"},
            headers=headers_b,
        )
        assert res_b_death.status_code == 200
        death_b_id = res_b_death.json()["data"]["id"]

        # 3. User A mencoba PUT log B dengan ?kandang_id=<kandang A> -> 404 Not Found
        res_put_log = await client.put(
            f"/api/v1/daily-logs/{log_b_id}?kandang_id={kandang_a_id}",
            json={"pakan": 999, "minum": 999, "populasi": 999},
            headers=headers_a,
        )
        assert res_put_log.status_code == 404
        assert res_put_log.json()["detail"] == "Log tidak ditemukan"

        # 4. User A mencoba DELETE log B dengan ?kandang_id=<kandang A> -> 404 Not Found
        res_del_log = await client.delete(
            f"/api/v1/daily-logs/{log_b_id}?kandang_id={kandang_a_id}",
            headers=headers_a,
        )
        assert res_del_log.status_code == 404
        assert res_del_log.json()["detail"] == "Log tidak ditemukan"

        # 5. User A mencoba PUT death report B dengan ?kandang_id=<kandang A> -> 404 Not Found
        res_put_death = await client.put(
            f"/api/v1/death-reports/{death_b_id}?kandang_id={kandang_a_id}",
            json={"count": 99, "notes": "Hacked"},
            headers=headers_a,
        )
        assert res_put_death.status_code == 404
        assert res_put_death.json()["detail"] == "Laporan tidak ditemukan"

        # 6. User A mencoba DELETE death report B dengan ?kandang_id=<kandang A> -> 404 Not Found
        res_del_death = await client.delete(
            f"/api/v1/death-reports/{death_b_id}?kandang_id={kandang_a_id}",
            headers=headers_a,
        )
        assert res_del_death.status_code == 404
        assert res_del_death.json()["detail"] == "Laporan tidak ditemukan"

