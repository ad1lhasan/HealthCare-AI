import sqlite3

db_path = "instance/healthcare.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE insurance ADD COLUMN type VARCHAR(20) NOT NULL DEFAULT 'Health';")
    print("Column 'type' added successfully.")
except Exception as e:
    print("Error:", e)

conn.commit()
conn.close() 