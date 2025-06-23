import sqlite3
from datetime import datetime

def check_appointments():
    """Check what appointments exist in the database"""
    try:
        conn = sqlite3.connect('instance/healthcare.db')
        cursor = conn.cursor()
        
        # Check if appointments table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='appointment'")
        if not cursor.fetchone():
            print("Appointments table does not exist!")
            return
        
        # Get all appointments
        cursor.execute("SELECT * FROM appointment")
        appointments = cursor.fetchall()
        
        print(f"Found {len(appointments)} appointments in database:")
        for appt in appointments:
            print(f"ID: {appt[0]}, User ID: {appt[1]}, Date: {appt[2]}, Time: {appt[3]}, Doctor: {appt[4]}, Department: {appt[5]}")
        
        # Get user info
        cursor.execute("SELECT id, username FROM user")
        users = cursor.fetchall()
        print(f"\nUsers in database:")
        for user in users:
            print(f"ID: {user[0]}, Username: {user[1]}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_appointments() 