-- Run this in your Supabase SQL Editor
-- Adds updated_at columns and fixes constraints

-- Fix jobs table unique constraint
ALTER TABLE jobs DROP CONSTRAINT IF EXISTS jobs_user_id_job_id_key;
ALTER TABLE jobs ADD CONSTRAINT jobs_user_id_job_id_key UNIQUE (user_id, job_id);

-- Add updated_at to resumes if missing
ALTER TABLE resumes ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();

-- Add updated_at to cover_letters if missing  
ALTER TABLE cover_letters ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();

-- Add updated_at to jobs if missing
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();
