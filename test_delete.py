import requests
import json

# Test the delete user functionality
def test_delete_user():
    # First, let's check if we can access the admin dashboard
    session = requests.Session()
    
    # Try to login as admin
    login_data = {
        'username': 'adilhasan',
        'password': '12001200'
    }
    
    print("Attempting to login as admin...")
    response = session.post('http://localhost:5000/login', data=login_data)
    print(f"Login response status: {response.status_code}")
    
    if response.status_code == 302:  # Redirect after successful login
        print("Login successful!")
        
        # Check admin dashboard access
        print("Checking admin dashboard access...")
        dashboard_response = session.get('http://localhost:5000/admin_dashboard')
        print(f"Dashboard response status: {dashboard_response.status_code}")
        
        if dashboard_response.status_code == 200:
            print("Admin dashboard accessible!")
            
            # Test delete user functionality
            print("Testing delete user functionality...")
            delete_response = session.post('http://localhost:5000/admin/delete_user/2', 
                                         headers={'Content-Type': 'application/json', 
                                                 'X-Requested-With': 'XMLHttpRequest'})
            print(f"Delete response status: {delete_response.status_code}")
            print(f"Delete response content: {delete_response.text}")
            
            try:
                delete_data = delete_response.json()
                print(f"Delete response JSON: {json.dumps(delete_data, indent=2)}")
            except:
                print("Could not parse JSON response")
        else:
            print("Cannot access admin dashboard")
            print(f"Response content: {dashboard_response.text}")
    else:
        print("Login failed!")
        print(f"Response content: {response.text}")

if __name__ == "__main__":
    test_delete_user() 