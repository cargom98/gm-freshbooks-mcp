#!/usr/bin/env python3
"""Test FreshBooks OAuth using existing Cloudflare Tunnel"""

import os
import json
import time
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import requests

# Configuration
CLIENT_ID = os.getenv("FRESHBOOKS_CLIENT_ID")
CLIENT_SECRET = os.getenv("FRESHBOOKS_CLIENT_SECRET")
TUNNEL_URL = "https://test.devopsengineer.com"
REDIRECT_URI = f"{TUNNEL_URL}/callback"

if not CLIENT_ID or not CLIENT_SECRET:
    print("Error: Please set FRESHBOOKS_CLIENT_ID and FRESHBOOKS_CLIENT_SECRET environment variables")
    sys.exit(1)
LOCAL_PORT = 8000

auth_code = None
server_ready = threading.Event()

class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        
        print(f"\n[Server] Received request: {self.path}")
        
        query = parse_qs(urlparse(self.path).query)
        auth_code = query.get('code', [None])[0]
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        html = '''
        <html>
        <head><title>Authorization Successful</title></head>
        <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
            <h1 style="color: green;">Authorization Successful!</h1>
            <p>You can close this window and return to the terminal.</p>
            <script>setTimeout(function(){ window.close(); }, 3000);</script>
        </body>
        </html>
        '''
        self.wfile.write(html.encode('utf-8'))
        
        if auth_code:
            print(f"[Server] Captured authorization code: {auth_code[:20]}...")
        else:
            print(f"[Server] No code in callback - query params: {query}")
    
    def log_message(self, format, *args):
        # Custom logging
        print(f"[Server] {format % args}")

def run_server(server):
    """Run HTTP server in background thread"""
    server_ready.set()
    print(f"[Server] Ready to accept connections on port {LOCAL_PORT}")
    try:
        # Handle multiple requests
        for i in range(10):
            print(f"[Server] Waiting for request {i+1}/10...")
            server.handle_request()
    except Exception as e:
        print(f"[Server] Error: {e}")

def main():
    print("=" * 70)
    print("FreshBooks OAuth with Existing Cloudflare Tunnel")
    print("=" * 70)
    print()
    print(f"Tunnel URL: {TUNNEL_URL}")
    print(f"Local Port: {LOCAL_PORT}")
    print(f"Redirect URI: {REDIRECT_URI}")
    print()
    
    # Step 1: Verify tunnel is working
    print("Step 1: Verifying tunnel connectivity...")
    print("-" * 70)
    
    try:
        # Test if tunnel is accessible
        test_response = requests.get(TUNNEL_URL, timeout=5)
        print(f"✓ Tunnel is accessible (status: {test_response.status_code})")
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Warning: Could not verify tunnel: {e}")
        print("   Continuing anyway...")
    
    print()
    
    # Step 2: Start local HTTP server
    print("Step 2: Starting local HTTP server...")
    print("-" * 70)
    
    try:
        server = HTTPServer(('localhost', LOCAL_PORT), CallbackHandler)
        print(f"✓ HTTP server created on http://localhost:{LOCAL_PORT}")
        
        # Start server in background thread
        server_thread = threading.Thread(target=run_server, args=(server,), daemon=True)
        server_thread.start()
        
        # Wait for server to be ready
        server_ready.wait(timeout=2)
        print(f"✓ Server listening and ready for callbacks")
        
    except OSError as e:
        if e.errno == 48:  # Address already in use
            print(f"✗ Port {LOCAL_PORT} is already in use")
            print(f"   Run: lsof -ti:{LOCAL_PORT} | xargs kill -9")
        else:
            print(f"✗ Failed to start server: {e}")
        return
    except Exception as e:
        print(f"✗ Failed to start server: {e}")
        return
    
    print()
    
    # Step 3: Instructions for FreshBooks configuration
    print("Step 3: FreshBooks App Configuration")
    print("-" * 70)
    print()
    print("Make sure your FreshBooks app is configured with:")
    print(f"  Redirect URI: {REDIRECT_URI}")
    print()
    print("To update:")
    print("  1. Go to: https://my.freshbooks.com/#/developer")
    print("  2. Edit your app")
    print("  3. Set Redirect URI to the URL above")
    print("  4. Save changes")
    print()
    
    response = input("Is your FreshBooks app configured? (y/n): ").strip().lower()
    if response != 'y':
        print("\nPlease configure your app first, then run this script again.")
        return
    
    print()
    
    # Step 4: Open browser for authorization
    print("Step 4: Starting OAuth authorization flow...")
    print("-" * 70)
    
    auth_url = f"https://auth.freshbooks.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}"
    
    print(f"Opening browser to: {auth_url[:80]}...")
    print()
    
    webbrowser.open(auth_url)
    
    print("Waiting for authorization callback...")
    print("(Timeout in 120 seconds)")
    print()
    
    # Wait for callback
    start_time = time.time()
    while not auth_code and (time.time() - start_time) < 120:
        time.sleep(0.5)
    
    if not auth_code:
        print("\n✗ Timeout waiting for callback")
        print("\nTroubleshooting:")
        print("  1. Did you authorize the app in FreshBooks?")
        print("  2. Is your cloudflared tunnel running?")
        print(f"  3. Is the tunnel pointing to http://localhost:{LOCAL_PORT}?")
        print(f"  4. Check tunnel logs for incoming requests")
        return
    
    print()
    print(f"✓ Received authorization code")
    print()
    
    # Step 5: Exchange code for token
    print("Step 5: Exchanging authorization code for access token...")
    print("-" * 70)
    
    token_response = requests.post('https://api.freshbooks.com/auth/oauth/token', data={
        'grant_type': 'authorization_code',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'code': auth_code,
        'redirect_uri': REDIRECT_URI
    })
    
    print(f"Token response status: {token_response.status_code}")
    token_data = token_response.json()
    
    if 'access_token' not in token_data:
        print(f"✗ Failed to get access token")
        print(f"Response: {json.dumps(token_data, indent=2)}")
        return
    
    access_token = token_data['access_token']
    refresh_token = token_data.get('refresh_token')
    print(f"✓ Access token received")
    print()
    
    # Save token
    token_file = os.path.expanduser("~/.freshbooks_token.json")
    with open(token_file, 'w') as f:
        json.dump(token_data, f, indent=2)
    print(f"✓ Token saved to {token_file}")
    print()
    
    # Step 6: Test API
    print("Step 6: Testing FreshBooks API...")
    print("-" * 70)
    
    headers = {'Authorization': f'Bearer {access_token}'}
    me_response = requests.get('https://api.freshbooks.com/auth/api/v1/users/me', headers=headers)
    
    if me_response.status_code == 200:
        me_data = me_response.json()
        print("✓ Account info retrieved successfully!")
        print()
        print("Account Details:")
        print(f"  Email: {me_data['response'].get('email', 'N/A')}")
        print(f"  First Name: {me_data['response'].get('first_name', 'N/A')}")
        print(f"  Last Name: {me_data['response'].get('last_name', 'N/A')}")
        
        if me_data['response'].get('business_memberships'):
            business = me_data['response']['business_memberships'][0]['business']
            print(f"  Business: {business.get('name', 'N/A')}")
            print(f"  Account ID: {business.get('account_id', 'N/A')}")
    else:
        print(f"✗ Failed to get account info: {me_response.status_code}")
        print(f"Response: {me_response.text}")
        return
    
    print()
    print("=" * 70)
    print("✓ Authentication completed successfully!")
    print("=" * 70)
    print()
    print("Token Details:")
    print(f"  Access Token: {access_token[:50]}...")
    if refresh_token:
        print(f"  Refresh Token: {refresh_token[:50]}...")
    print(f"  Saved to: {token_file}")
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
