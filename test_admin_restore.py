import requests
import json
import os

def test_admin_restore():
    """Test the admin restore functionality"""
    
    # Create a session to maintain cookies
    session = requests.Session()
    
    print("=== Testing Admin Restore Functionality ===\n")
    
    # Step 1: Login as admin
    print("1. Logging in as admin...")
    login_data = {
        'username': 'adilhasan',
        'password': '12001200'
    }
    
    login_response = session.post('http://localhost:5000/login', data=login_data)
    print(f"   Login status: {login_response.status_code}")
    
    if login_response.status_code != 302:
        print("   ❌ Login failed!")
        return
    
    print("   ✅ Login successful!\n")
    
    # Step 2: Check admin dashboard access
    print("2. Checking admin dashboard access...")
    dashboard_response = session.get('http://localhost:5000/admin_dashboard')
    print(f"   Dashboard status: {dashboard_response.status_code}")
    
    if dashboard_response.status_code != 200:
        print("   ❌ Cannot access admin dashboard!")
        return
    
    print("   ✅ Admin dashboard accessible!\n")
    
    # Step 3: Create a test backup file
    print("3. Creating test backup file...")
    test_data = {
        "user": {
            "id": 999,
            "username": "test_restore_user",
            "full_name": "Test Restore User",
            "email": "test@restore.com",
            "age": 25,
            "gender": "Male",
            "phone_number": "+911234567890",
            "is_admin": False,
            "blocked": False
        },
        "health": {
            "height_cm": 175,
            "weight_kg": 70,
            "blood_group": "O+",
            "allergies": "None",
            "chronic_conditions": "None",
            "medications": "None"
        },
        "activities": [
            {
                "action": "Test activity",
                "timestamp": "2024-01-01T12:00:00"
            }
        ],
        "appointments": [],
        "reminders": [],
        "blood_donations": [],
        "insurances": [],
        "chats": [],
        "notifications": [],
        "blood_requests": [],
        "health_reviews": []
    }
    
    # Save test data to file
    with open('test_restore_data.json', 'w') as f:
        json.dump([test_data], f, indent=2)
    
    print("   ✅ Test backup file created!\n")
    
    # Step 4: Test restore functionality
    print("4. Testing restore functionality...")
    
    with open('test_restore_data.json', 'rb') as f:
        files = {'admin_restore_file': ('test_restore_data.json', f, 'application/json')}
        restore_response = session.post('http://localhost:5000/admin/restore_data', files=files)
    
    print(f"   Restore status: {restore_response.status_code}")
    print(f"   Response URL: {restore_response.url}")
    
    if restore_response.status_code == 302:
        print("   ✅ Restore request successful!")
        
        # Check if we're redirected to admin dashboard
        if 'admin_dashboard' in restore_response.url:
            print("   ✅ Redirected to admin dashboard!")
        else:
            print("   ⚠️  Unexpected redirect location")
    else:
        print("   ❌ Restore request failed!")
        print(f"   Response content: {restore_response.text[:200]}...")
    
    # Clean up test file
    if os.path.exists('test_restore_data.json'):
        os.remove('test_restore_data.json')
        print("   ✅ Test file cleaned up!")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    test_admin_restore() 