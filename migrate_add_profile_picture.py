import sqlite3

conn = sqlite3.connect('instance/healthcare.db')
conn.execute("ALTER TABLE user ADD COLUMN profile_picture VARCHAR(255);")
conn.commit()
conn.close()

print("Migration complete: profile_picture column added to user table.") 