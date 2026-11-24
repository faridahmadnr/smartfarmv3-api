-- Migration: Add index on users.pemilik_id (Idempotent)
-- DO NOT RUN unless explicitly confirmed by user.
CREATE INDEX IF NOT EXISTS ix_users_pemilik_id ON users (pemilik_id);
