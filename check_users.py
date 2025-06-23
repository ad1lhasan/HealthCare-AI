import sqlite3

def check_users():
    conn = sqlite3.connect('instance/healthcare.db')
    cursor = conn.cursor()
    
    print("=== ALL USERS IN DATABASE ===")
    cursor.execute("SELECT id, username, full_name, email, is_admin, blocked FROM users")
    users = cursor.fetchall()
    
    for user in users:
        user_id, username, full_name, email, is_admin, blocked = user
        status = "ADMIN" if is_admin else "USER"
        blocked_status = "BLOCKED" if blocked else "ACTIVE"
        print(f"ID: {user_id}, Username: {username}, Status: {status}, Name: {full_name}, Email: {email}, Blocked: {blocked_status}")
    
    print("\n=== ADILHASAN DETAILS ===")
    cursor.execute("SELECT * FROM users WHERE username='adilhasan'")
    adilhasan = cursor.fetchone()
    
    if adilhasan:
        print(f"Found adilhasan: {adilhasan}")
        print(f"Admin status: {adilhasan[5] if len(adilhasan) > 5 else 'Unknown'}")
    else:
        print("adilhasan not found!")
    
    conn.close()

if __name__ == "__main__":
    check_users() 