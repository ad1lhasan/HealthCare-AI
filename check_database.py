import sqlite3
import os

def check_database():
    # Get the database path
    db_path = os.path.join('instance', 'healthcare.db')
    
    if not os.path.exists(db_path):
        print("Database file not found!")
        return
    
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print("Tables in database:")
        for table in tables:
            print(f"- {table[0]}")
            
            # Get table structure
            cursor.execute(f"PRAGMA table_info({table[0]})")
            columns = cursor.fetchall()
            print("  Columns:")
            for column in columns:
                print(f"    {column[1]} ({column[2]})")
            print()
        
        # Check for user table specifically
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%user%';")
        user_tables = cursor.fetchall()
        print("Tables with 'user' in name:")
        for table in user_tables:
            print(f"- {table[0]}")
        
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_database() 