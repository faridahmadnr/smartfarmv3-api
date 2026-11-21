-- Migration: tambah kolom panjang, lebar, dan tipe_kandang ke tabel kandangs
-- Jalankan sekali di production DB

ALTER TABLE kandangs
ADD COLUMN IF NOT EXISTS panjang DOUBLE PRECISION DEFAULT NULL,
ADD COLUMN IF NOT EXISTS lebar DOUBLE PRECISION DEFAULT NULL,
ADD COLUMN IF NOT EXISTS tipe_kandang VARCHAR(50) DEFAULT 'Closed House';
