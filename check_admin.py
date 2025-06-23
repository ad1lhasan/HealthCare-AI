#!/usr/bin/env python3
import sqlite3
import os

def check_admin_status():
    db_path = 'instance/healthcare.db'
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if users table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user'")
    if not cursor.fetchone():
        print("User table not found!")
        return
    
    # Get all users with their admin status
    cursor.execute("SELECT id, username, is_admin, full_name, email FROM user")
    users = cursor.fetchall()
    
    print("=== ALL USERS IN DATABASE ===")
    for user in users:
        user_id, username, is_admin, full_name, email = user
        admin_status = "ADMIN" if is_admin else "USER"
        print(f"ID: {user_id}, Username: {username}, Status: {admin_status}, Name: {full_name}, Email: {email}")
    
    # Check specifically for adilhasan
    cursor.execute("SELECT * FROM user WHERE username = ?", ('adilhasan',))
    adilhasan = cursor.fetchone()
    if adilhasan:
        print(f"\n=== ADILHASAN DETAILS ===")
        print(f"Found adilhasan: {adilhasan}")
    else:
        print(f"\n=== ADILHASAN NOT FOUND ===")
    
    conn.close()

if __name__ == "__main__":
    check_admin_status() 