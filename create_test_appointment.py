import sqlite3
from datetime import datetime, timedelta

def create_test_appointment():
    """Create a test appointment for user ID 1"""
    try:
        conn = sqlite3.connect('instance/healthcare.db')
        cursor = conn.cursor()
        
        # Create a future appointment (tomorrow)
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        
        cursor.execute("""
            INSERT INTO appointment (user_id, date, time, reason, doctor, department, reminder_time)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (1, tomorrow, '10:00', 'Regular checkup', 'Dr. Smith', 'Cardiology', '24'))
        
        conn.commit()
        print(f"Created test appointment for tomorrow ({tomorrow}) at 10:00 AM")
        
        # Verify it was created
        cursor.execute("SELECT * FROM appointment WHERE user_id = 1")
        appointments = cursor.fetchall()
        print(f"Now have {len(appointments)} appointments for user 1")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    create_test_appointment() 