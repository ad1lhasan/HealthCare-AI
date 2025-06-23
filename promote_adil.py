import sqlite3

conn = sqlite3.connect('instance/healthcare.db')
cursor = conn.cursor()
cursor.execute("UPDATE user SET is_admin = 1 WHERE username = 'adilhasan'")
conn.commit()
conn.close()
print("User 'adilhasan' promoted to admin.") 