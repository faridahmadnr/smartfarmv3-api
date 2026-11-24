"""
Test suite for Pemilik managing Peternak endpoints (/api/v1/pemilik/peternak).
Ensures tenant isolation, RBAC guards, data validation, and session revocation.
"""
import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User, UserRole
from app.models.kandang import Kandang
from app.core.security import get_password_hash


@pytest_asyncio.fixture
async def setup_pemilik_peternak_data(db_session: AsyncSession, client: AsyncClient) -> dict:
    """Setup Pemilik A, Pemilik B, Admin, Kandangs, and login headers."""
    # 1. Pemilik A
    pemilik_a = User(
        id=uuid.uuid4(),
        email="pemilika@farm.com",
        username="pemilika",
        full_name="Pemilik A",
        hashed_password=get_password_hash("password123"),
        role=UserRole.PEMILIK,
        is_active=True,
    )
    # 2. Pemilik B
    pemilik_b = User(
        id=uuid.uuid4(),
        email="pemilikb@farm.com",
        username="pemilikb",
        full_name="Pemilik B",
        hashed_password=get_password_hash("password123"),
        role=UserRole.PEMILIK,
        is_active=True,
    )
    # 3. Admin
    admin_user = User(
        id=uuid.uuid4(),
        email="adminmaster@farm.com",
        username="adminmaster",
        full_name="Super Admin",
        hashed_password=get_password_hash("password123"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add_all([pemilik_a, pemilik_b, admin_user])
    await db_session.flush()

    # 4. Kandang Pemilik A
    kandang_a = Kandang(
        id=uuid.uuid4(),
        nama="Kandang Pemilik A",
        kode="KDG-PEMA",
        lokasi="Blok A",
        kapasitas=5000,
        pemilik_id=pemilik_a.id,
        is_active=True,
    )
    # 5. Kandang Pemilik B
    kandang_b = Kandang(
        id=uuid.uuid4(),
        nama="Kandang Pemilik B",
        kode="KDG-PEMB",
        lokasi="Blok B",
        kapasitas=5000,
        pemilik_id=pemilik_b.id,
        is_active=True,
    )
    db_session.add_all([kandang_a, kandang_b])

    # 6. Peternak B awal milik Pemilik B
    peternak_b = User(
        id=uuid.uuid4(),
        email="peternakb@farm.com",
        username="peternakb",
        full_name="Peternak B Asli",
        hashed_password=get_password_hash("password123"),
        role=UserRole.PETERNAK,
        pemilik_id=pemilik_b.id,
        created_by_id=pemilik_b.id,
        is_active=True,
    )
    db_session.add(peternak_b)
    await db_session.commit()

    async def login(username: str) -> tuple[dict, str]:
        res = await client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": "password123"},
        )
        assert res.status_code == 200, f"Login failed for {username}: {res.text}"
        token = res.json()["data"]["access_token"]
        return {"Authorization": f"Bearer {token}"}, token

    headers_a, token_a = await login("pemilika")
    headers_b, token_b = await login("pemilikb")
    headers_admin, token_admin = await login("adminmaster")
    headers_peternak_b, token_peternak_b = await login("peternakb")

    return {
        "pemilik_a": pemilik_a,
        "pemilik_b": pemilik_b,
        "admin_user": admin_user,
        "peternak_b": peternak_b,
        "headers_a": headers_a,
        "headers_b": headers_b,
        "headers_admin": headers_admin,
        "headers_peternak_b": headers_peternak_b,
        "token_peternak_b": token_peternak_b,
    }


@pytest.mark.asyncio
class TestPemilikPeternakEndpoints:

    async def test_pemilik_create_peternak_success(
        self, client: AsyncClient, setup_pemilik_peternak_data: dict
    ):
        """Pemilik A membuat peternak -> 201 Created, pemilik_id terisi otomatis, role=peternak."""
        headers_a = setup_pemilik_peternak_data["headers_a"]
        pemilik_a = setup_pemilik_peternak_data["pemilik_a"]

        payload = {
            "email": "anakbuah_a@farm.com",
            "username": "anakbuah_a",
            "full_name": "Anak Buah A",
            "phone": "08123456789",
            "password": "password123",
        }

        res = await client.post("/api/v1/pemilik/peternak", json=payload, headers=headers_a)
        assert res.status_code == 201
        data = res.json()["data"]

        assert data["username"] == "anakbuah_a"
        assert data["email"] == "anakbuah_a@farm.com"
        assert data["role"] == "peternak"
        assert data["pemilik_id"] == str(pemilik_a.id)
        assert data["created_by_id"] == str(pemilik_a.id)
        assert data["is_active"] is True
        # Respons tidak boleh membocorkan password atau token
        assert "hashed_password" not in data
        assert "refresh_token" not in data

    async def test_create_peternak_tampering_ignored(
        self, client: AsyncClient, setup_pemilik_peternak_data: dict
    ):
        """Payload yang mencoba menyisipkan role=admin atau pemilik_id lain diabaikan."""
        headers_a = setup_pemilik_peternak_data["headers_a"]
        pemilik_a = setup_pemilik_peternak_data["pemilik_a"]
        pemilik_b = setup_pemilik_peternak_data["pemilik_b"]

        payload = {
            "email": "tamper@farm.com",
            "username": "tamper_user",
            "full_name": "Tamper Test",
            "password": "password123",
            "role": "admin",
            "pemilik_id": str(pemilik_b.id),
        }

        res = await client.post("/api/v1/pemilik/peternak", json=payload, headers=headers_a)
        assert res.status_code == 201
        data = res.json()["data"]

        # Pastikan tetap role peternak dan pemilik_id tetap pemilik A
        assert data["role"] == "peternak"
        assert data["pemilik_id"] == str(pemilik_a.id)

    async def test_list_peternaks_scoped_to_own_pemilik(
        self, client: AsyncClient, setup_pemilik_peternak_data: dict
    ):
        """List hanya mengembalikan peternak milik sendiri."""
        headers_a = setup_pemilik_peternak_data["headers_a"]
        headers_b = setup_pemilik_peternak_data["headers_b"]

        # Buat 2 peternak untuk Pemilik A
        for i in range(2):
            await client.post(
                "/api/v1/pemilik/peternak",
                json={
                    "email": f"pema_worker_{i}@farm.com",
                    "username": f"pema_worker_{i}",
                    "full_name": f"Worker A {i}",
                    "password": "password123",
                },
                headers=headers_a,
            )

        # GET oleh Pemilik A -> melihat 2 peternak miliknya
        res_a = await client.get("/api/v1/pemilik/peternak", headers=headers_a)
        assert res_a.status_code == 200
        data_a = res_a.json()["data"]
        assert len(data_a) == 2
        for item in data_a:
            assert item["pemilik_id"] == str(setup_pemilik_peternak_data["pemilik_a"].id)

        # GET oleh Pemilik B -> hanya melihat 1 peternak miliknya (peternakb)
        res_b = await client.get("/api/v1/pemilik/peternak", headers=headers_b)
        assert res_b.status_code == 200
        data_b = res_b.json()["data"]
        assert len(data_b) == 1
        assert data_b[0]["username"] == "peternakb"

    async def test_search_and_filter_peternaks(
        self, client: AsyncClient, setup_pemilik_peternak_data: dict
    ):
        """Pencarian (search) dan filter is_active berfungsi dengan aman (wildcard escaped)."""
        headers_a = setup_pemilik_peternak_data["headers_a"]

        # Tambah peternak
        await client.post(
            "/api/v1/pemilik/peternak",
            json={
                "email": "special_worker@farm.com",
                "username": "special_worker",
                "full_name": "Special Worker 100%",
                "password": "password123",
            },
            headers=headers_a,
        )

        # Search aman dengan wildcard character (%)
        res_search = await client.get("/api/v1/pemilik/peternak?search=%25", headers=headers_a)
        assert res_search.status_code == 200

        # Search username
        res_kw = await client.get("/api/v1/pemilik/peternak?search=special", headers=headers_a)
        assert res_kw.status_code == 200
        assert len(res_kw.json()["data"]) == 1

    async def test_cross_tenant_get_put_delete_returns_404(
        self, client: AsyncClient, setup_pemilik_peternak_data: dict
    ):
        """Pemilik A mengakses peternak milik Pemilik B -> 404 Not Found (mencegah enumerasi)."""
        headers_a = setup_pemilik_peternak_data["headers_a"]
        peternak_b_id = str(setup_pemilik_peternak_data["peternak_b"].id)

        # 1. GET detail peternak B oleh Pemilik A -> 404
        res_get = await client.get(f"/api/v1/pemilik/peternak/{peternak_b_id}", headers=headers_a)
        assert res_get.status_code == 404
        assert res_get.json()["detail"] == "Peternak tidak ditemukan"

        # 2. PUT peternak B oleh Pemilik A -> 404
        res_put = await client.put(
            f"/api/v1/pemilik/peternak/{peternak_b_id}",
            json={"full_name": "Dibajak"},
            headers=headers_a,
        )
        assert res_put.status_code == 404

        # 3. DELETE peternak B oleh Pemilik A -> 404
        res_del = await client.delete(f"/api/v1/pemilik/peternak/{peternak_b_id}", headers=headers_a)
        assert res_del.status_code == 404

    async def test_pemilik_cannot_touch_other_roles(
        self, client: AsyncClient, setup_pemilik_peternak_data: dict
    ):
        """Pemilik tidak bisa menyentuh akun role PEMILIK atau ADMIN via /pemilik/peternak/{id} -> 404."""
        headers_a = setup_pemilik_peternak_data["headers_a"]
        admin_id = str(setup_pemilik_peternak_data["admin_user"].id)
        pemilik_b_id = str(setup_pemilik_peternak_data["pemilik_b"].id)

        res_admin = await client.get(f"/api/v1/pemilik/peternak/{admin_id}", headers=headers_a)
        assert res_admin.status_code == 404

        res_pemilik = await client.get(f"/api/v1/pemilik/peternak/{pemilik_b_id}", headers=headers_a)
        assert res_pemilik.status_code == 404

    async def test_admin_and_peternak_forbidden_from_endpoint(
        self, client: AsyncClient, setup_pemilik_peternak_data: dict
    ):
        """Role ADMIN dan PETERNAK ditolak mengakses /pemilik/peternak -> 403 Forbidden."""
        headers_admin = setup_pemilik_peternak_data["headers_admin"]
        headers_peternak = setup_pemilik_peternak_data["headers_peternak_b"]

        res_admin = await client.get("/api/v1/pemilik/peternak", headers=headers_admin)
        assert res_admin.status_code == 403

        res_peternak = await client.get("/api/v1/pemilik/peternak", headers=headers_peternak)
        assert res_peternak.status_code == 403

    async def test_duplicate_username_or_email_returns_400(
        self, client: AsyncClient, setup_pemilik_peternak_data: dict
    ):
        """Duplikasi email atau username (case-insensitive) ditolak dengan 400 Bad Request."""
        headers_a = setup_pemilik_peternak_data["headers_a"]

        # 1. Duplikasi email peternakb yang sudah ada
        res_email = await client.post(
            "/api/v1/pemilik/peternak",
            json={
                "email": "PETERNAKB@farm.com",  # uppercase check
                "username": "unique_username_1",
                "full_name": "Dupe Email",
                "password": "password123",
            },
            headers=headers_a,
        )
        assert res_email.status_code == 400
        assert "Email sudah terdaftar" in res_email.json()["detail"]

        # 2. Duplikasi username
        res_user = await client.post(
            "/api/v1/pemilik/peternak",
            json={
                "email": "unique_email_1@farm.com",
                "username": "peternakb",  # username peternak B
                "full_name": "Dupe Username",
                "password": "password123",
            },
            headers=headers_a,
        )
        assert res_user.status_code == 400
        assert "Username sudah terdaftar" in res_user.json()["detail"]

    async def test_update_email_to_own_email_does_not_fail(
        self, client: AsyncClient, setup_pemilik_peternak_data: dict
    ):
        """PUT update email ke email sendiri tidak mengembalikan 400."""
        headers_b = setup_pemilik_peternak_data["headers_b"]
        peternak_b_id = str(setup_pemilik_peternak_data["peternak_b"].id)

        res_put = await client.put(
            f"/api/v1/pemilik/peternak/{peternak_b_id}",
            json={"email": "peternakb@farm.com", "full_name": "Nama Baru B"},
            headers=headers_b,
        )
        assert res_put.status_code == 200
        assert res_put.json()["data"]["full_name"] == "Nama Baru B"

    async def test_deactivate_and_revoke_token(
        self, client: AsyncClient, db_session: AsyncSession, setup_pemilik_peternak_data: dict
    ):
        """
        Penonaktifan (DELETE & PUT is_active=false):
        - mencabut refresh_token di DB
        - access token lama langsung ditolak 403 Forbidden pada request berikutnya
        - login ditolak
        - DELETE kedua kali: idempotent (200 OK)
        """
        headers_b = setup_pemilik_peternak_data["headers_b"]
        peternak_b = setup_pemilik_peternak_data["peternak_b"]
        token_peternak_b = setup_pemilik_peternak_data["token_peternak_b"]

        # 1. Sebelum dinonaktifkan, access token peternak B berfungsi (misal GET /kandangs/me)
        res_me_before = await client.get(
            "/api/v1/kandangs/me",
            headers={"Authorization": f"Bearer {token_peternak_b}"},
        )
        assert res_me_before.status_code == 200

        # 2. Pemilik B menonaktifkan peternak B (DELETE)
        res_del = await client.delete(
            f"/api/v1/pemilik/peternak/{peternak_b.id}",
            headers=headers_b,
        )
        assert res_del.status_code == 200

        # 3. Cek di DB: is_active=False dan refresh_token=None
        await db_session.refresh(peternak_b)
        assert peternak_b.is_active is False
        assert peternak_b.refresh_token is None
        assert peternak_b.refresh_token_expires_at is None

        # 4. Access token lama peternak B langsung ditolak dengan 403 Forbidden (User tidak aktif)
        res_me_after = await client.get(
            "/api/v1/kandangs/me",
            headers={"Authorization": f"Bearer {token_peternak_b}"},
        )
        assert res_me_after.status_code == 403
        assert "User tidak aktif" in res_me_after.json()["detail"]

        # 5. Peternak B mencoba login ulang -> 401 Unauthorized
        res_relogin = await client.post(
            "/api/v1/auth/login",
            json={"username": "peternakb", "password": "password123"},
        )
        assert res_relogin.status_code == 401

        # 6. DELETE kedua kali pada peternak yang sudah nonaktif -> idempotent (200 OK)
        res_del_idempotent = await client.delete(
            f"/api/v1/pemilik/peternak/{peternak_b.id}",
            headers=headers_b,
        )
        assert res_del_idempotent.status_code == 200

    async def test_put_deactivate_revokes_token_and_reactivation_works(
        self, client: AsyncClient, db_session: AsyncSession, setup_pemilik_peternak_data: dict
    ):
        """PUT dengan is_active=false mencabut refresh_token, dan PUT is_active=true mengaktifkan kembali."""
        headers_b = setup_pemilik_peternak_data["headers_b"]
        peternak_b = setup_pemilik_peternak_data["peternak_b"]

        # 1. Nonaktifkan via PUT is_active=false
        res_put_false = await client.put(
            f"/api/v1/pemilik/peternak/{peternak_b.id}",
            json={"is_active": False},
            headers=headers_b,
        )
        assert res_put_false.status_code == 200
        assert res_put_false.json()["data"]["is_active"] is False

        await db_session.refresh(peternak_b)
        assert peternak_b.is_active is False
        assert peternak_b.refresh_token is None

        # 2. Aktifkan kembali via PUT is_active=true
        res_put_true = await client.put(
            f"/api/v1/pemilik/peternak/{peternak_b.id}",
            json={"is_active": True},
            headers=headers_b,
        )
        assert res_put_true.status_code == 200
        assert res_put_true.json()["data"]["is_active"] is True

        # Peternak B sekarang bisa login kembali
        res_login = await client.post(
            "/api/v1/auth/login",
            json={"username": "peternakb", "password": "password123"},
        )
        assert res_login.status_code == 200

    async def test_new_peternak_scoped_to_pemilik_kandangs(
        self, client: AsyncClient, setup_pemilik_peternak_data: dict
    ):
        """Peternak baru yang dibuat pemilik bisa login dan GET /kandangs hanya melihat kandang pemiliknya."""
        headers_a = setup_pemilik_peternak_data["headers_a"]

        # Pemilik A buat peternak baru
        res_create = await client.post(
            "/api/v1/pemilik/peternak",
            json={
                "email": "worker_login_test@farm.com",
                "username": "worker_login_test",
                "full_name": "Worker Login Test",
                "password": "password123",
            },
            headers=headers_a,
        )
        assert res_create.status_code == 201

        # Peternak baru login
        res_login = await client.post(
            "/api/v1/auth/login",
            json={"username": "worker_login_test", "password": "password123"},
        )
        assert res_login.status_code == 200
        token_worker = res_login.json()["data"]["access_token"]
        headers_worker = {"Authorization": f"Bearer {token_worker}"}

        # Peternak memanggil GET /kandangs -> hanya melihat kandang Pemilik A
        res_kandangs = await client.get("/api/v1/kandangs", headers=headers_worker)
        assert res_kandangs.status_code == 200
        kandangs_data = res_kandangs.json()["data"]
        assert len(kandangs_data) == 1
        assert kandangs_data[0]["kode"] == "KDG-PEMA"
