-- Migration: tambah kolom tanggal_mulai_siklus ke tabel kandangs
-- Jalankan sekali di production DB

ALTER TABLE kandangs
ADD COLUMN IF NOT EXISTS tanggal_mulai_siklus TIMESTAMP WITH TIME ZONE DEFAULT NULL;
