-- Add employee_number column to persons table
ALTER TABLE persons 
ADD COLUMN IF NOT EXISTS employee_number TEXT UNIQUE;

-- Update the view to include employee_number if needed (optional)
-- Note: views usually need to be recreated if the underlying table changes in a way that affects them, 
-- but 'SELECT *' views might check schema on query or need refresh.
-- Here we just ensure the column exists.
