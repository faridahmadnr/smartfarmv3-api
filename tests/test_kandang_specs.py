"""
Tests for Kandang Specifications and Validation (Tahap 4).
Memverifikasi validasi tipe_kandang (Closed House / Open House), dimensi panjang, lebar, luas,
dan pembuatan kandang oleh role Admin dan Pemilik.
"""
import uuid
import pytest
from httpx import AsyncClient

from app.models.user import User


@pytest.mark.asyncio
async def test_invalid_tipe_kandang_rejected_422(
    client: AsyncClient,
    admin_auth_headers: dict,
    test_user: User,
):
    """Memverifikasi bahwa tipe_kandang di luar Closed House dan Open House ditolak 422."""
    payload = {
        "nama": "Kandang Invalid",
        "kode": f"KND-INV-{uuid.uuid4().hex[:4]}",
        "kapasitas": 1000,
        "tipe_kandang": "Semi Closed House",  # Nilai tidak valid
        "panjang": 20.0,
        "lebar": 5.0,
        "luas": 100.0,
        "pemilik_id": str(test_user.id),
    }
    response = await client.post(
        "/api/v1/kandangs",
        json=payload,
        headers=admin_auth_headers,
    )
    assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"


@pytest.mark.asyncio
async def test_create_kandang_by_admin_with_specs(
    client: AsyncClient,
    admin_auth_headers: dict,
    test_user: User,
):
    """Admin dapat membuat kandang dengan spesifikasi lengkap dan menentukan pemiliknya."""
    payload = {
        "nama": "Kandang Closed House Admin",
        "kode": f"KND-ADM-{uuid.uuid4().hex[:4]}",
        "kapasitas": 5000,
        "tipe_kandang": "Closed House",
        "panjang": 50.0,
        "lebar": 10.0,
        "luas": 500.0,
        "pemilik_id": str(test_user.id),
    }
    response = await client.post(
        "/api/v1/kandangs",
        json=payload,
        headers=admin_auth_headers,
    )
    assert response.status_code == 201, f"Create failed: {response.text}"
    data = response.json()["data"]
    assert data["tipe_kandang"] == "Closed House"
    assert data["panjang"] == 50.0
    assert data["lebar"] == 10.0
    assert data["luas"] == 500.0
    assert data["pemilik_id"] == str(test_user.id)


@pytest.mark.asyncio
async def test_create_kandang_by_pemilik_with_specs(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
):
    """Pemilik dapat membuat kandang miliknya sendiri dengan spesifikasi panjang, lebar, luas, tipe."""
    payload = {
        "nama": "Kandang Open House Pemilik",
        "kode": f"KND-PEM-{uuid.uuid4().hex[:4]}",
        "kapasitas": 3000,
        "tipe_kandang": "Open House",
        "panjang": 30.0,
        "lebar": 8.0,
        "luas": 240.0,
    }
    response = await client.post(
        "/api/v1/kandangs",
        json=payload,
        headers=auth_headers,
    )
    assert response.status_code == 201, f"Create failed: {response.text}"
    data = response.json()["data"]
    assert data["tipe_kandang"] == "Open House"
    assert data["panjang"] == 30.0
    assert data["lebar"] == 8.0
    assert data["luas"] == 240.0
    # pemilik_id harus otomatis terisi ID pemilik yang login
    assert data["pemilik_id"] == str(test_user.id)

    # Verifikasi GET detail kandang mengembalikan spesifikasi yang sama
    kandang_id = data["id"]
    get_res = await client.get(
        f"/api/v1/kandangs/{kandang_id}",
        headers=auth_headers,
    )
    assert get_res.status_code == 200
    detail = get_res.json()["data"]
    assert detail["tipe_kandang"] == "Open House"
    assert detail["panjang"] == 30.0
    assert detail["lebar"] == 8.0
    assert detail["luas"] == 240.0
