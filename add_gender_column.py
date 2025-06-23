import sqlite3
import os

def add_gender_column():
    # Get the database path
    db_path = os.path.join('instance', 'healthcare.db')
    
    if not os.path.exists(db_path):
        print("Database file not found!")
        return
    
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if gender column already exists
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'gender' not in columns:
            # Add gender column
            cursor.execute("ALTER TABLE users ADD COLUMN gender VARCHAR(10)")
            print("Gender column added successfully!")
        else:
            print("Gender column already exists!")
        
        # Commit changes
        conn.commit()
        conn.close()
        print("Migration completed successfully!")
        
    except Exception as e:
        print(f"Error during migration: {e}")

if __name__ == "__main__":
    add_gender_column() 