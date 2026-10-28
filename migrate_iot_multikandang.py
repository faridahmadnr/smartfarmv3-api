"""
Migration: tambah kolom kandang_id (UUID, FK -> kandangs.id ON DELETE CASCADE)
dan kandang_kode (String) ke tabel IoT/Sensor (`sensor_data`) untuk mendukung
multi-kandang.

Script ini idempotent / aman dijalankan berulang kali:
  - Mengecek dulu apakah kolom / constraint / index sudah ada.
  - Melewati (skip) langkah yang sudah terpenuhi.

Cara pakai (dari folder smartfarmv3-api, tempat file ini berada):

    python migrate_iot_multikandang.py

Opsional, tentukan nama tabel lain (default: sensor_data):

    python migrate_iot_multikandang.py --table sensor_data

Koneksi database diambil dari DATABASE_URL di file .env (lihat app/config.py).
"""
import argparse
import asyncio
import sys

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Tambahkan root project ke path agar `app` bisa di-import.
sys.path.insert(0, ".")

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.database import engine


async def column_exists(conn: AsyncConnection, table: str, column: str) -> bool:
    """Cek apakah kolom sudah ada di tabel."""
    result = await conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = :table
              AND column_name = :column
            LIMIT 1
            """
        ),
        {"table": table, "column": column},
    )
    return result.scalar() is not None


async def fk_on_column_exists(conn: AsyncConnection, table: str, column: str) -> bool:
    """Cek apakah sudah ada FOREIGN KEY pada kolom tertentu."""
    result = await conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_name = :table
              AND kcu.column_name = :column
            LIMIT 1
            """
        ),
        {"table": table, "column": column},
    )
    return result.scalar() is not None


async def index_exists(conn: AsyncConnection, index_name: str) -> bool:
    """Cek apakah index sudah ada."""
    result = await conn.execute(
        text("SELECT 1 FROM pg_indexes WHERE indexname = :name LIMIT 1"),
        {"name": index_name},
    )
    return result.scalar() is not None


async def table_exists(conn: AsyncConnection, table: str) -> bool:
    """Cek apakah tabel ada di schema public."""
    result = await conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = :table
            LIMIT 1
            """
        ),
        {"table": table},
    )
    return result.scalar() is not None


async def run_migration(table: str) -> None:
    print("=" * 62)
    print("  MIGRASI: kolom kandang_id + kandang_kode untuk multi-kandang")
    print(f"  Tabel target : {table}")
    print("=" * 62)

    async with engine.begin() as conn:
        # --- 0. Pastikan tabel ada ---
        if not await table_exists(conn, table):
            print(f"[x] Tabel '{table}' tidak ditemukan. Migrasi dibatalkan.")
            return

        changed = False

        # --- 1. Kolom kandang_id (ditambahkan nullable dulu agar aman) ---
        if await column_exists(conn, table, "kandang_id"):
            print("[=] Kolom 'kandang_id' sudah ada - skip.")
        else:
            await conn.execute(
                text(f'ALTER TABLE "{table}" ADD COLUMN kandang_id UUID NULL')
            )
            print("[+] Kolom 'kandang_id' (UUID, nullable) ditambahkan.")
            changed = True

        # --- 2. Kolom kandang_kode ---
        if await column_exists(conn, table, "kandang_kode"):
            print("[=] Kolom 'kandang_kode' sudah ada - skip.")
        else:
            await conn.execute(
                text(f'ALTER TABLE "{table}" ADD COLUMN kandang_kode VARCHAR(20) NULL')
            )
            print("[+] Kolom 'kandang_kode' (VARCHAR(20)) ditambahkan.")
            changed = True

        # --- 3. Backfill kandang_id untuk baris lama ---
        backfilled = await conn.execute(
            text(
                f"""
                UPDATE "{table}" sd
                SET kandang_id = k.id
                FROM kandangs k
                WHERE sd.kandang_id IS NULL
                  AND sd.kandang_kode IS NOT NULL
                  AND k.kode = sd.kandang_kode
                """
            )
        )
        if backfilled.rowcount:
            print(f"[~] Backfill dari kandang_kode: {backfilled.rowcount} baris terisi.")
            changed = True

        # Fallback: hanya jika tepat ada SATU kandang (tidak ambigu).
        kandang_count = (
            await conn.execute(text("SELECT count(*) FROM kandangs"))
        ).scalar()
        if kandang_count == 1:
            fallback = await conn.execute(
                text(
                    f"""
                    UPDATE "{table}"
                    SET kandang_id = (SELECT id FROM kandangs LIMIT 1)
                    WHERE kandang_id IS NULL
                    """
                )
            )
            if fallback.rowcount:
                print(
                    f"[~] Fallback ke satu-satunya kandang: "
                    f"{fallback.rowcount} baris terisi."
                )
                changed = True

        # --- 4. FOREIGN KEY -> kandangs.id ON DELETE CASCADE ---
        if await fk_on_column_exists(conn, table, "kandang_id"):
            print("[=] Foreign key pada 'kandang_id' sudah ada - skip.")
        else:
            remaining_nulls = (
                await conn.execute(
                    text(f'SELECT count(*) FROM "{table}" WHERE kandang_id IS NULL')
                )
            ).scalar()
            if remaining_nulls:
                print(
                    f"[!] Ada {remaining_nulls} baris dengan kandang_id NULL. "
                    "FK tetap dibuat (constraint tidak memblokir NULL)."
                )
            await conn.execute(
                text(
                    f'ALTER TABLE "{table}" ADD CONSTRAINT fk_{table}_kandang_id '
                    "FOREIGN KEY (kandang_id) REFERENCES kandangs(id) ON DELETE CASCADE"
                )
            )
            print("[+] Foreign key 'kandang_id' -> kandangs(id) ON DELETE CASCADE dibuat.")
            changed = True

        # --- 5. Set NOT NULL jika semua baris sudah terisi ---
        remaining_nulls = (
            await conn.execute(
                text(f'SELECT count(*) FROM "{table}" WHERE kandang_id IS NULL')
            )
        ).scalar()
        if remaining_nulls == 0:
            await conn.execute(
                text(f'ALTER TABLE "{table}" ALTER COLUMN kandang_id SET NOT NULL')
            )
            print("[+] Kolom 'kandang_id' di-set NOT NULL.")
        else:
            print(
                f"[!] Masih ada {remaining_nulls} baris kandang_id NULL - "
                "NOT NULL dilewati (isi dulu datanya, lalu jalankan ulang)."
            )

        # --- 6. Index pendukung query ---
        if await index_exists(conn, f"ix_{table}_kandang_id"):
            print("[=] Index 'ix_..._kandang_id' sudah ada - skip.")
        else:
            await conn.execute(
                text(
                    f'CREATE INDEX ix_{table}_kandang_id ON "{table}" (kandang_id)'
                )
            )
            print("[+] Index pada 'kandang_id' dibuat.")

        if await index_exists(conn, f"ix_{table}_kandang_kode"):
            print("[=] Index 'ix_..._kandang_kode' sudah ada - skip.")
        else:
            await conn.execute(
                text(
                    f'CREATE INDEX ix_{table}_kandang_kode ON "{table}" (kandang_kode)'
                )
            )
            print("[+] Index pada 'kandang_kode' dibuat.")

        if await index_exists(conn, f"ix_{table}_kandang_timestamp"):
            print("[=] Index komposit 'ix_..._kandang_timestamp' sudah ada - skip.")
        else:
            await conn.execute(
                text(
                    f'CREATE INDEX ix_{table}_kandang_timestamp '
                    f'ON "{table}" (kandang_id, "timestamp")'
                )
            )
            print("[+] Index komposit (kandang_id, timestamp) dibuat.")

    print("-" * 62)
    if changed:
        print("[OK] Migrasi selesai, ada perubahan diterapkan.")
    else:
        print("[OK] Migrasi selesai, tidak ada perubahan (sudah up-to-date).")
    print("=" * 62)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Tambah kolom kandang_id + kandang_kode ke tabel IoT/Sensor."
    )
    parser.add_argument(
        "--table",
        default="sensor_data",
        help="Nama tabel IoT/Sensor (default: sensor_data)",
    )
    args = parser.parse_args()

    try:
        await run_migration(args.table)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
