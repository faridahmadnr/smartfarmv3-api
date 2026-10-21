-- Seed kandang utama. Gunakan pemilik dari user admin pertama.
INSERT INTO kandangs (id, nama, kode, lokasi, kapasitas, deskripsi, is_active, pemilik_id, created_at, updated_at)
SELECT
    gen_random_uuid(),
    'Kandang Utama',
    'KDG-001',
    'Farm Broiler',
    5000,
    'Kandang broiler utama',
    true,
    id,
    NOW(),
    NOW()
FROM users
WHERE role = 'ADMIN'
LIMIT 1
ON CONFLICT (kode) DO NOTHING;
