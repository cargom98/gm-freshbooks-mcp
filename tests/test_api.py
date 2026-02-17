import os
import requests
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

CLIENT_ID = os.getenv("FRESHBOOKS_CLIENT_ID")
CLIENT_SECRET = os.getenv("FRESHBOOKS_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8080/callback"

if not CLIENT_ID or not CLIENT_SECRET:
    print("Error: Please set FRESHBOOKS_CLIENT_ID and FRESHBOOKS_CLIENT_SECRET environment variables")
    exit(1)

auth_code = None

class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        query = parse_qs(urlparse(self.path).query)
        auth_code = query.get('code', [None])[0]
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'<html><body><h1>Authorization successful! You can close this window.</h1></body></html>')
    
    def log_message(self, format, *args):
        pass

# Step 1: Get authorization code
auth_url = f"https://auth.freshbooks.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}"
print(f"Opening browser for authorization...")
webbrowser.open(auth_url)

server = HTTPServer(('localhost', 8080), CallbackHandler)
server.handle_request()

if not auth_code:
    print("Failed to get authorization code")
    exit(1)

# Step 2: Exchange code for access token
token_response = requests.post('https://api.freshbooks.com/auth/oauth/token', data={
    'grant_type': 'authorization_code',
    'client_id': CLIENT_ID,
    'client_secret': CLIENT_SECRET,
    'code': auth_code,
    'redirect_uri': REDIRECT_URI
})

token_data = token_response.json()
access_token = token_data.get('access_token')

if not access_token:
    print(f"Failed to get access token: {token_data}")
    exit(1)

print(f"\nAccess Token: {access_token}\n")

# Step 3: Test API - Get account info
headers = {'Authorization': f'Bearer {access_token}'}
me_response = requests.get('https://api.freshbooks.com/auth/api/v1/users/me', headers=headers)
print(f"Account Info: {me_response.json()}")
