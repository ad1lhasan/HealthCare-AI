import requests
import json

def test_delete_functionality():
    """Test the delete user functionality step by step"""
    
    # Create a session to maintain cookies
    session = requests.Session()
    
    print("=== Testing Delete User Functionality ===\n")
    
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
        print(f"   Response: {login_response.text}")
        return
    
    print("   ✅ Login successful!\n")
    
    # Step 2: Check admin status
    print("2. Checking admin status...")
    debug_response = session.get('http://localhost:5000/debug_admin_status')
    print(f"   Debug status: {debug_response.status_code}")
    
    if debug_response.status_code == 200:
        debug_data = debug_response.json()
        print(f"   Session user_id: {debug_data.get('user_id')}")
        print(f"   Session username: {debug_data.get('username')}")
        print(f"   Session is_admin: {debug_data.get('session_is_admin')}")
        print(f"   DB is_admin: {debug_data.get('db_is_admin')}")
        
        if debug_data.get('db_is_admin'):
            print("   ✅ User is admin!")
        else:
            print("   ❌ User is not admin!")
            return
    else:
        print("   ❌ Could not check admin status!")
        return
    
    print()
    
    # Step 3: Access admin dashboard
    print("3. Accessing admin dashboard...")
    dashboard_response = session.get('http://localhost:5000/admin_dashboard')
    print(f"   Dashboard status: {dashboard_response.status_code}")
    
    if dashboard_response.status_code == 200:
        print("   ✅ Admin dashboard accessible!")
    else:
        print("   ❌ Cannot access admin dashboard!")
        print(f"   Response: {dashboard_response.text}")
        return
    
    print()
    
    # Step 4: Test delete user (try to delete user with ID 2)
    print("4. Testing delete user functionality...")
    delete_response = session.post(
        'http://localhost:5000/admin/delete_user/2',
        headers={
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        }
    )
    
    print(f"   Delete status: {delete_response.status_code}")
    print(f"   Delete response: {delete_response.text}")
    
    try:
        delete_data = delete_response.json()
        if delete_data.get('success'):
            print("   ✅ Delete user successful!")
        else:
            print(f"   ❌ Delete user failed: {delete_data.get('message')}")
    except:
        print("   ❌ Could not parse delete response!")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    test_delete_functionality() 