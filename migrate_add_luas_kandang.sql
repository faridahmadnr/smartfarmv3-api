-- Migration: tambah kolom luas (m²) ke tabel kandangs
-- Jalankan sekali di production DB

ALTER TABLE kandangs
ADD COLUMN IF NOT EXISTS luas DOUBLE PRECISION DEFAULT NULL;
