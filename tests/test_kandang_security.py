"""
Tests for Kandang Tenant Isolation and Role-Based Access Control (Security).
Memverifikasi tidak adanya kebocoran data antar tenant (Pemilik A & B, Peternak A & B).
"""
import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.user import User, UserRole
from app.models.kandang import Kandang


@pytest_asyncio.fixture
async def setup_two_tenants(db_session: AsyncSession, client: AsyncClient):
    """
    Setup dua tenant independen:
    - Tenant A: Pemilik A, Peternak A, Kandang A
    - Tenant B: Pemilik B, Peternak B, Kandang B
    - Peternak Yatim (tanpa pemilik_id)
    """
    # 1. Pemilik A & Peternak A
    pemilik_a = User(
        id=uuid.uuid4(),
        email="pemilik_a@example.com",
        username="pemilika",
        full_name="Pemilik A",
        hashed_password=get_password_hash("password123"),
        role=UserRole.PEMILIK,
        is_active=True,
    )
    db_session.add(pemilik_a)
    await db_session.flush()

    peternak_a = User(
        id=uuid.uuid4(),
        email="peternak_a@example.com",
        username="peternaka",
        full_name="Peternak A",
        hashed_password=get_password_hash("password123"),
        role=UserRole.PETERNAK,
        pemilik_id=pemilik_a.id,
        is_active=True,
    )
    db_session.add(peternak_a)

    kandang_a = Kandang(
        id=uuid.uuid4(),
        nama="Kandang Milik A",
        kode="KDG-AAA-001",
        lokasi="Blok A",
        kapasitas=5000,
        tipe_kandang="Closed House",
        is_active=True,
        pemilik_id=pemilik_a.id,
    )
    db_session.add(kandang_a)

    # 2. Pemilik B & Peternak B
    pemilik_b = User(
        id=uuid.uuid4(),
        email="pemilik_b@example.com",
        username="pemilikb",
        full_name="Pemilik B",
        hashed_password=get_password_hash("password123"),
        role=UserRole.PEMILIK,
        is_active=True,
    )
    db_session.add(pemilik_b)
    await db_session.flush()

    peternak_b = User(
        id=uuid.uuid4(),
        email="peternak_b@example.com",
        username="peternakb",
        full_name="Peternak B",
        hashed_password=get_password_hash("password123"),
        role=UserRole.PETERNAK,
        pemilik_id=pemilik_b.id,
        is_active=True,
    )
    db_session.add(peternak_b)

    kandang_b = Kandang(
        id=uuid.uuid4(),
        nama="Kandang Milik B",
        kode="KDG-BBB-001",
        lokasi="Blok B",
        kapasitas=3000,
        tipe_kandang="Open House",
        is_active=True,
        pemilik_id=pemilik_b.id,
    )
    db_session.add(kandang_b)

    # 3. Peternak Yatim (tanpa pemilik_id)
    peternak_orphan = User(
        id=uuid.uuid4(),
        email="orphan@example.com",
        username="peternakorphan",
        full_name="Peternak Yatim",
        hashed_password=get_password_hash("password123"),
        role=UserRole.PETERNAK,
        pemilik_id=None,
        is_active=True,
    )
    db_session.add(peternak_orphan)

    await db_session.commit()

    # Helper untuk login dan dapatkan auth header
    async def login(username: str) -> dict:
        res = await client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": "password123"},
        )
        assert res.status_code == 200, f"Login failed for {username}: {res.text}"
        token = res.json()["data"]["access_token"]
        return {"Authorization": f"Bearer {token}"}

    headers_pemilik_a = await login("pemilika")
    headers_peternak_a = await login("peternaka")
    headers_pemilik_b = await login("pemilikb")
    headers_peternak_b = await login("peternakb")
    headers_orphan = await login("peternakorphan")

    return {
        "pemilik_a": pemilik_a,
        "peternak_a": peternak_a,
        "kandang_a": kandang_a,
        "headers_pemilik_a": headers_pemilik_a,
        "headers_peternak_a": headers_peternak_a,
        "pemilik_b": pemilik_b,
        "peternak_b": peternak_b,
        "kandang_b": kandang_b,
        "headers_pemilik_b": headers_pemilik_b,
        "headers_peternak_b": headers_peternak_b,
        "peternak_orphan": peternak_orphan,
        "headers_orphan": headers_orphan,
    }


@pytest.mark.asyncio
class TestKandangSecurity:

    async def test_peternak_a_cannot_get_or_put_kandang_b(
        self, client: AsyncClient, setup_two_tenants: dict
    ):
        """Peternak A dilarang membaca atau mengupdate kandang milik Pemilik B (403 Forbidden)."""
        kandang_b_id = setup_two_tenants["kandang_b"].id
        headers = setup_two_tenants["headers_peternak_a"]

        # 1. GET detail kandang B
        res_get = await client.get(
            f"/api/v1/kandangs/{kandang_b_id}",
            headers=headers,
        )
        assert res_get.status_code == 403

        # 2. PUT update kandang B
        res_put = await client.put(
            f"/api/v1/kandangs/{kandang_b_id}",
            json={"nama": "Kandang B Dibajak Peternak A"},
            headers=headers,
        )
        assert res_put.status_code == 403

    async def test_peternak_a_can_get_and_put_kandang_a(
        self, client: AsyncClient, setup_two_tenants: dict
    ):
        """Peternak A berhasil membaca dan mengupdate kandang milik Pemilik A (200 OK)."""
        kandang_a_id = setup_two_tenants["kandang_a"].id
        headers = setup_two_tenants["headers_peternak_a"]

        # 1. GET detail kandang A
        res_get = await client.get(
            f"/api/v1/kandangs/{kandang_a_id}",
            headers=headers,
        )
        assert res_get.status_code == 200
        assert res_get.json()["data"]["id"] == str(kandang_a_id)

        # 2. PUT update kandang A
        res_put = await client.put(
            f"/api/v1/kandangs/{kandang_a_id}",
            json={"deskripsi": "Diupdate oleh Peternak A yang sah"},
            headers=headers,
        )
        assert res_put.status_code == 200
        assert res_put.json()["data"]["deskripsi"] == "Diupdate oleh Peternak A yang sah"

    async def test_pemilik_a_cannot_get_or_put_kandang_b(
        self, client: AsyncClient, setup_two_tenants: dict
    ):
        """Pemilik A dilarang membaca atau mengupdate kandang milik Pemilik B (403 Forbidden)."""
        kandang_b_id = setup_two_tenants["kandang_b"].id
        headers = setup_two_tenants["headers_pemilik_a"]

        # 1. GET kandang B
        res_get = await client.get(
            f"/api/v1/kandangs/{kandang_b_id}",
            headers=headers,
        )
        assert res_get.status_code == 403

        # 2. PUT kandang B
        res_put = await client.put(
            f"/api/v1/kandangs/{kandang_b_id}",
            json={"nama": "Kandang B Dibajak Pemilik A"},
            headers=headers,
        )
        assert res_put.status_code == 403

    async def test_get_my_kandang_returns_own_kandang(
        self, client: AsyncClient, setup_two_tenants: dict
    ):
        """GET /kandangs/me mengembalikan kandang sesuai scope role pemilik dan peternak."""
        kandang_a_id = str(setup_two_tenants["kandang_a"].id)
        kandang_b_id = str(setup_two_tenants["kandang_b"].id)

        # Pemilik A -> kandang A
        res_pa = await client.get(
            "/api/v1/kandangs/me",
            headers=setup_two_tenants["headers_pemilik_a"],
        )
        assert res_pa.status_code == 200
        assert res_pa.json()["data"]["id"] == kandang_a_id

        # Peternak A -> kandang A
        res_ta = await client.get(
            "/api/v1/kandangs/me",
            headers=setup_two_tenants["headers_peternak_a"],
        )
        assert res_ta.status_code == 200
        assert res_ta.json()["data"]["id"] == kandang_a_id

        # Pemilik B -> kandang B
        res_pb = await client.get(
            "/api/v1/kandangs/me",
            headers=setup_two_tenants["headers_pemilik_b"],
        )
        assert res_pb.status_code == 200
        assert res_pb.json()["data"]["id"] == kandang_b_id

        # Peternak B -> kandang B
        res_tb = await client.get(
            "/api/v1/kandangs/me",
            headers=setup_two_tenants["headers_peternak_b"],
        )
        assert res_tb.status_code == 200
        assert res_tb.json()["data"]["id"] == kandang_b_id

    async def test_peternak_without_pemilik_rejected(
        self, client: AsyncClient, setup_two_tenants: dict
    ):
        """Peternak tanpa pemilik_id ditolak di /me (404), GET id (403), dan PUT id (403)."""
        headers = setup_two_tenants["headers_orphan"]
        kandang_a_id = setup_two_tenants["kandang_a"].id

        # 1. /me -> 404 (tidak punya kandang)
        res_me = await client.get(
            "/api/v1/kandangs/me",
            headers=headers,
        )
        assert res_me.status_code == 404

        # 2. GET by id -> 403 Forbidden
        res_get = await client.get(
            f"/api/v1/kandangs/{kandang_a_id}",
            headers=headers,
        )
        assert res_get.status_code == 403

        # 3. PUT by id -> 403 Forbidden
        res_put = await client.put(
            f"/api/v1/kandangs/{kandang_a_id}",
            json={"nama": "Kandang Dibajak Orphan"},
            headers=headers,
        )
        assert res_put.status_code == 403

    async def test_admin_can_access_all_kandangs(
        self, client: AsyncClient, admin_auth_headers: dict, setup_two_tenants: dict
    ):
        """Admin memiliki hak akses penuh ke kandang A dan kandang B."""
        kandang_a_id = setup_two_tenants["kandang_a"].id
        kandang_b_id = setup_two_tenants["kandang_b"].id

        # GET kandang A & B
        res_a = await client.get(f"/api/v1/kandangs/{kandang_a_id}", headers=admin_auth_headers)
        assert res_a.status_code == 200

        res_b = await client.get(f"/api/v1/kandangs/{kandang_b_id}", headers=admin_auth_headers)
        assert res_b.status_code == 200

        # PUT kandang A
        res_put = await client.put(
            f"/api/v1/kandangs/{kandang_a_id}",
            json={"deskripsi": "Diupdate oleh Admin"},
            headers=admin_auth_headers,
        )
        assert res_put.status_code == 200

        # /me untuk admin
        res_me = await client.get("/api/v1/kandangs/me", headers=admin_auth_headers)
        assert res_me.status_code == 200

    async def test_list_kandang_per_role(
        self, client: AsyncClient, admin_auth_headers: dict, setup_two_tenants: dict
    ):
        """List kandang mengembalikan hanya kandang sesuai scope role tanpa kebocoran."""
        kandang_a_id = str(setup_two_tenants["kandang_a"].id)
        kandang_b_id = str(setup_two_tenants["kandang_b"].id)

        # Pemilik A hanya melihat kandang A
        res_pa = await client.get("/api/v1/kandangs", headers=setup_two_tenants["headers_pemilik_a"])
        assert res_pa.status_code == 200
        ids_pa = [k["id"] for k in res_pa.json()["data"]]
        assert kandang_a_id in ids_pa
        assert kandang_b_id not in ids_pa

        # Peternak A hanya melihat kandang A
        res_ta = await client.get("/api/v1/kandangs", headers=setup_two_tenants["headers_peternak_a"])
        assert res_ta.status_code == 200
        ids_ta = [k["id"] for k in res_ta.json()["data"]]
        assert kandang_a_id in ids_ta
        assert kandang_b_id not in ids_ta

        # Pemilik B hanya melihat kandang B
        res_pb = await client.get("/api/v1/kandangs", headers=setup_two_tenants["headers_pemilik_b"])
        assert res_pb.status_code == 200
        ids_pb = [k["id"] for k in res_pb.json()["data"]]
        assert kandang_b_id in ids_pb
        assert kandang_a_id not in ids_pb

        # Peternak orphan melihat list kosong
        res_or = await client.get("/api/v1/kandangs", headers=setup_two_tenants["headers_orphan"])
        assert res_or.status_code == 200
        assert len(res_or.json()["data"]) == 0

        # Admin melihat kedua kandang
        res_adm = await client.get("/api/v1/kandangs", headers=admin_auth_headers)
        assert res_adm.status_code == 200
        ids_adm = [k["id"] for k in res_adm.json()["data"]]
        assert kandang_a_id in ids_adm
        assert kandang_b_id in ids_adm

    async def test_delete_kandang_cross_tenant_rejected(
        self, client: AsyncClient, setup_two_tenants: dict
    ):
        """DELETE kandang lintas tenant ditolak (403), dan peternak dilarang menghapus (403)."""
        kandang_a_id = setup_two_tenants["kandang_a"].id
        kandang_b_id = setup_two_tenants["kandang_b"].id

        # 1. Pemilik A mencoba DELETE Kandang B milik Pemilik B -> 403 Forbidden
        res_del_cross = await client.delete(
            f"/api/v1/kandangs/{kandang_b_id}",
            headers=setup_two_tenants["headers_pemilik_a"],
        )
        assert res_del_cross.status_code == 403

        # 2. Peternak A mencoba DELETE Kandang A miliknya sendiri -> 403 Forbidden (RBAC)
        res_del_peternak = await client.delete(
            f"/api/v1/kandangs/{kandang_a_id}",
            headers=setup_two_tenants["headers_peternak_a"],
        )
        assert res_del_peternak.status_code == 403

        # 3. Pemilik A DELETE Kandang A miliknya sendiri -> 200 OK
        res_del_own = await client.delete(
            f"/api/v1/kandangs/{kandang_a_id}",
            headers=setup_two_tenants["headers_pemilik_a"],
        )
        assert res_del_own.status_code == 200

    async def test_get_my_kandang_user_without_kandang_returns_404(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """GET /kandangs/me mengembalikan 404 Not Found untuk user (pemilik) yang belum memiliki kandang."""
        pemilik_c = User(
            id=uuid.uuid4(),
            email="pemilik_c@example.com",
            username="pemilikc",
            full_name="Pemilik C",
            hashed_password=get_password_hash("password123"),
            role=UserRole.PEMILIK,
            is_active=True,
        )
        db_session.add(pemilik_c)
        await db_session.commit()

        login_res = await client.post(
            "/api/v1/auth/login",
            json={"username": "pemilikc", "password": "password123"},
        )
        assert login_res.status_code == 200
        token = login_res.json()["data"]["access_token"]
        headers_c = {"Authorization": f"Bearer {token}"}

        res_me = await client.get("/api/v1/kandangs/me", headers=headers_c)
        assert res_me.status_code == 404
        assert res_me.json()["detail"] == "Kandang tidak ditemukan"
