-- ============================================================
-- Supabase Schema für Face Recognition System
-- Schulprojekt: 30-Tage Speicherung mit Timestamps
-- ============================================================

-- Tabelle: persons (Registrierte Personen)
CREATE TABLE IF NOT EXISTS persons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    face_encoding JSONB NOT NULL,
    photo_url TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tabelle: detections (Erkennungs-Historie)
CREATE TABLE IF NOT EXISTS detections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id UUID REFERENCES persons(id) ON DELETE CASCADE,
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    confidence FLOAT NOT NULL,
    snapshot_url TEXT,
    location TEXT DEFAULT 'Pi-Top Camera',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index für schnelle Abfragen
CREATE INDEX IF NOT EXISTS idx_detections_person_id ON detections(person_id);
CREATE INDEX IF NOT EXISTS idx_detections_detected_at ON detections(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_persons_name ON persons(name);

-- Funktion: Auto-Update von updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger für persons Tabelle
DROP TRIGGER IF EXISTS update_persons_updated_at ON persons;
CREATE TRIGGER update_persons_updated_at
    BEFORE UPDATE ON persons
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Funktion: Lösche alte Detections (älter als 30 Tage)
CREATE OR REPLACE FUNCTION cleanup_old_detections()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM detections
    WHERE detected_at < NOW() - INTERVAL '30 days';
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- View: Statistiken pro Person
CREATE OR REPLACE VIEW person_statistics AS
SELECT 
    p.id,
    p.name,
    p.photo_url,
    p.created_at as registered_at,
    COUNT(d.id) as total_detections,
    MAX(d.detected_at) as last_seen,
    MIN(d.detected_at) as first_seen,
    AVG(d.confidence) as avg_confidence
FROM persons p
LEFT JOIN detections d ON p.id = d.person_id
GROUP BY p.id, p.name, p.photo_url, p.created_at;

-- View: Tägliche Statistiken
CREATE OR REPLACE VIEW daily_statistics AS
SELECT 
    DATE(detected_at) as date,
    COUNT(DISTINCT person_id) as unique_persons,
    COUNT(*) as total_detections,
    AVG(confidence) as avg_confidence
FROM detections
WHERE detected_at >= NOW() - INTERVAL '30 days'
GROUP BY DATE(detected_at)
ORDER BY date DESC;

-- View: Letzte Erkennungen (für Dashboard)
CREATE OR REPLACE VIEW recent_detections AS
SELECT 
    d.id,
    d.detected_at,
    d.confidence,
    d.snapshot_url,
    p.name as person_name,
    p.photo_url as person_photo
FROM detections d
JOIN persons p ON d.person_id = p.id
WHERE d.detected_at >= NOW() - INTERVAL '30 days'
ORDER BY d.detected_at DESC
LIMIT 100;

-- ============================================================
-- Row Level Security (RLS) Policies
-- ============================================================

-- Enable RLS
ALTER TABLE persons ENABLE ROW LEVEL SECURITY;
ALTER TABLE detections ENABLE ROW LEVEL SECURITY;

-- Policy: Jeder kann lesen (für Anon Key)
CREATE POLICY "Allow public read access on persons"
    ON persons FOR SELECT
    TO anon
    USING (true);

CREATE POLICY "Allow public read access on detections"
    ON detections FOR SELECT
    TO anon
    USING (true);

-- Policy: Jeder kann einfügen (für Anon Key)
CREATE POLICY "Allow public insert on persons"
    ON persons FOR INSERT
    TO anon
    WITH CHECK (true);

CREATE POLICY "Allow public insert on detections"
    ON detections FOR INSERT
    TO anon
    WITH CHECK (true);

-- Policy: Jeder kann updaten (für Anon Key)
CREATE POLICY "Allow public update on persons"
    ON persons FOR UPDATE
    TO anon
    USING (true)
    WITH CHECK (true);

-- Policy: Jeder kann löschen (für Anon Key)
CREATE POLICY "Allow public delete on persons"
    ON persons FOR DELETE
    TO anon
    USING (true);

CREATE POLICY "Allow public delete on detections"
    ON detections FOR DELETE
    TO anon
    USING (true);

-- ============================================================
-- Storage Buckets (Manuell im Supabase Dashboard erstellen!)
-- ============================================================

-- WICHTIG: Erstelle diese Buckets im Supabase Dashboard:
-- 1. Bucket Name: "person-photos"
--    - Public: true
--    - File size limit: 5MB
--    - Allowed MIME types: image/jpeg, image/png
--
-- 2. Bucket Name: "detection-snapshots"
--    - Public: true
--    - File size limit: 2MB
--    - Allowed MIME types: image/jpeg

-- ============================================================
-- Test Daten (Optional)
-- ============================================================

-- Beispiel Person (nur zum Testen)
-- INSERT INTO persons (name, face_encoding, notes)
-- VALUES ('Test Person', '[]'::jsonb, 'Dies ist eine Test-Person');

-- ============================================================
-- Nützliche Queries
-- ============================================================

-- Zeige alle Personen mit Anzahl Erkennungen
-- SELECT * FROM person_statistics ORDER BY total_detections DESC;

-- Zeige tägliche Statistiken
-- SELECT * FROM daily_statistics;

-- Zeige letzte Erkennungen
-- SELECT * FROM recent_detections;

-- Cleanup alte Detections manuell ausführen
-- SELECT cleanup_old_detections();

-- Zeige Personen die heute gesehen wurden
-- SELECT DISTINCT p.name, COUNT(*) as times_seen
-- FROM detections d
-- JOIN persons p ON d.person_id = p.id
-- WHERE DATE(d.detected_at) = CURRENT_DATE
-- GROUP BY p.name
-- ORDER BY times_seen DESC;
