#!/usr/bin/env python3
import sqlite3
import os
from werkzeug.security import generate_password_hash
import random
import string

def generate_medical_id():
    while True:
        medical_id = 'MID' + ''.join(random.choices(string.digits, k=9))
        return medical_id

def create_admin_user():
    db_path = 'instance/healthcare.db'
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if adilhasan already exists
    cursor.execute("SELECT id FROM user WHERE username = ?", ('adilhasan',))
    if cursor.fetchone():
        print("Admin user 'adilhasan' already exists!")
        return
    
    # Create admin user
    medical_id = generate_medical_id()
    hashed_password = generate_password_hash('admin123')  # Default password
    
    cursor.execute("""
        INSERT INTO user (medical_id, username, password, is_admin, full_name, email, age, gender, phone_number, blocked, profile_picture)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (medical_id, 'adilhasan', hashed_password, True, 'Admin User', 'admin@healthcare.com', 30, 'Male', '+1234567890', False, None))
    
    conn.commit()
    print("Admin user 'adilhasan' created successfully!")
    print("Username: adilhasan")
    print("Password: admin123")
    
    conn.close()

if __name__ == "__main__":
    create_admin_user() 