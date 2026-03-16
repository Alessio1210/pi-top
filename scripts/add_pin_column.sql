-- Add PIN column to persons table
ALTER TABLE persons 
ADD COLUMN IF NOT EXISTS pin TEXT;

-- Comment: The PIN should ideally be hashed, but for this school project simple text is acceptable or hashing can be done in Python.
