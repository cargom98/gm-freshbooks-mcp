import os
import requests

CLIENT_ID = os.getenv("FRESHBOOKS_CLIENT_ID")
CLIENT_SECRET = os.getenv("FRESHBOOKS_CLIENT_SECRET")
AUTH_CODE = os.getenv("FRESHBOOKS_AUTH_CODE")  # One-time auth code
REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"

if not CLIENT_ID or not CLIENT_SECRET or not AUTH_CODE:
    print("Error: Please set FRESHBOOKS_CLIENT_ID, FRESHBOOKS_CLIENT_SECRET, and FRESHBOOKS_AUTH_CODE environment variables")
    exit(1)

# Exchange code for access token
token_response = requests.post('https://api.freshbooks.com/auth/oauth/token', data={
    'grant_type': 'authorization_code',
    'client_id': CLIENT_ID,
    'client_secret': CLIENT_SECRET,
    'code': AUTH_CODE,
    'redirect_uri': REDIRECT_URI
})

print(f"Token Response Status: {token_response.status_code}")
token_data = token_response.json()
print(f"Token Data: {token_data}\n")

if 'access_token' in token_data:
    access_token = token_data['access_token']
    
    # Test API - Get account info
    headers = {'Authorization': f'Bearer {access_token}'}
    me_response = requests.get('https://api.freshbooks.com/auth/api/v1/users/me', headers=headers)
    print(f"Account Info Status: {me_response.status_code}")
    print(f"Account Info: {me_response.json()}")
