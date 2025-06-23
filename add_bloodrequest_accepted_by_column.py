import sqlite3

db_path = "instance/healthcare.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE blood_request ADD COLUMN accepted_by INTEGER;")
    print("Column 'accepted_by' added successfully.")
except Exception as e:
    print("Error:", e)

conn.commit()
conn.close() 