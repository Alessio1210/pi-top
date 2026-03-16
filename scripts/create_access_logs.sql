-- Script for the second Pi-Top Database Logging (Zentrale)
CREATE TABLE IF NOT EXISTS access_logs (
    id SERIAL PRIMARY KEY,
    person_id UUID REFERENCES persons(id) ON DELETE CASCADE,
    person_name VARCHAR(255),
    status VARCHAR(50) NOT NULL, -- e.g. 'pending', 'accepted', 'rejected', 'timeout'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Optional: Create an index for faster queries on recent logs
CREATE INDEX IF NOT EXISTS idx_access_logs_created_at ON access_logs(created_at DESC);
