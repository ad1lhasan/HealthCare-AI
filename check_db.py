import sqlite3

def check_database():
    conn = sqlite3.connect('instance/healthcare.db')
    cursor = conn.cursor()
    
    print("=== DATABASE TABLES ===")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    for table in tables:
        print(f"Table: {table[0]}")
        
        # Get table structure
        cursor.execute(f"PRAGMA table_info({table[0]})")
        columns = cursor.fetchall()
        print("  Columns:")
        for col in columns:
            print(f"    {col[1]} ({col[2]})")
        print()
    
    # Check if user table exists
    if any('user' in table[0].lower() for table in tables):
        print("=== USER TABLE DATA ===")
        try:
            cursor.execute("SELECT * FROM user LIMIT 5")
            users = cursor.fetchall()
            for user in users:
                print(f"User: {user}")
        except Exception as e:
            print(f"Error reading user table: {e}")
    
    conn.close()

if __name__ == "__main__":
    check_database() 