#!/usr/bin/env python3
"""Simple standalone test for FreshBooks OAuth with HTTPS"""

import os
import json
import ssl
import time
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import requests

# Configuration
CLIENT_ID = os.getenv("FRESHBOOKS_CLIENT_ID")
CLIENT_SECRET = os.getenv("FRESHBOOKS_CLIENT_SECRET")
REDIRECT_URI = "https://localhost:8080/callback"
CERT_FILE = os.path.expanduser("~/.freshbooks_cert.pem")

if not CLIENT_ID or not CLIENT_SECRET:
    print("Error: Please set FRESHBOOKS_CLIENT_ID and FRESHBOOKS_CLIENT_SECRET environment variables")
    sys.exit(1)
KEY_FILE = os.path.expanduser("~/.freshbooks_key.pem")

auth_code = None
server_ready = threading.Event()

class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        query = parse_qs(urlparse(self.path).query)
        auth_code = query.get('code', [None])[0]
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'<html><body><h1>Authorization successful! You can close this window.</h1></body></html>')
        
        print(f"\n✓ Received callback with code: {auth_code[:20] if auth_code else 'None'}...")
    
    def log_message(self, format, *args):
        pass

def generate_cert():
    """Generate self-signed certificate using OpenSSL"""
    if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
        print(f"Using existing certificate at {CERT_FILE}")
        return
    
    print("Generating self-signed certificate...")
    cmd = f'openssl req -x509 -newkey rsa:2048 -keyout {KEY_FILE} -out {CERT_FILE} -days 365 -nodes -subj "/CN=localhost" 2>/dev/null'
    result = os.system(cmd)
    
    if result == 0:
        print(f"✓ Certificate generated at {CERT_FILE}")
    else:
        print("✗ Failed to generate certificate. Make sure OpenSSL is installed.")
        exit(1)

def run_server(server):
    """Run server in background thread"""
    server_ready.set()
    print("  [Server thread] Ready to accept connections")
    try:
        server.handle_request()
        print("  [Server thread] Request handled")
    except Exception as e:
        print(f"  [Server thread] Error: {e}")

def main():
    print("=" * 60)
    print("FreshBooks OAuth HTTPS Authentication Test")
    print("=" * 60)
    print()
    
    # Generate certificate
    generate_cert()
    print()
    
    # Step 1: Start HTTPS server in background thread
    print("Step 1: Starting HTTPS callback server...")
    print("-" * 60)
    
    try:
        server = HTTPServer(('localhost', 8080), CallbackHandler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(CERT_FILE, KEY_FILE)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        print("✓ HTTPS server created")
        
        # Start server in background thread
        server_thread = threading.Thread(target=run_server, args=(server,), daemon=True)
        server_thread.start()
        
        # Wait for server to be ready
        server_ready.wait(timeout=2)
        print("✓ Server listening on https://localhost:8080/callback")
        
    except Exception as e:
        print(f"✗ Failed to start server: {e}")
        return
    
    print()
    
    # Step 2: Open browser for authorization
    print("Step 2: Opening browser for authorization...")
    print("-" * 60)
    auth_url = f"https://auth.freshbooks.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}"
    print(f"Authorization URL: {auth_url}")
    print()
    print("⚠️  Your browser will show a security warning about the")
    print("   self-signed certificate. Click 'Advanced' and 'Proceed'.")
    print()
    
    webbrowser.open(auth_url)
    
    print("Waiting for authorization callback...")
    print("(Timeout in 120 seconds)")
    print()
    
    # Wait for callback (with timeout)
    start_time = time.time()
    server_thread.join(timeout=120)  # Wait up to 2 minutes
    
    if auth_code:
        print()
    elif time.time() - start_time >= 120:
        print("\n✗ Timeout waiting for callback")
        print("\nTroubleshooting:")
        print("  1. Did you authorize the app in FreshBooks?")
        print("  2. Did you click 'Advanced' -> 'Proceed' on the security warning?")
        print("  3. Check if FreshBooks app is configured with redirect URI:")
        print(f"     {REDIRECT_URI}")
        return
    else:
        print("\n✗ Server thread ended without receiving callback")
        return
    
    if not auth_code:
        print("✗ Failed to get authorization code")
        return
    
    print(f"✓ Received authorization code: {auth_code[:20]}...")
    print()
    
    # Step 3: Exchange code for token
    print("Step 3: Exchanging code for access token...")
    print("-" * 60)
    
    token_response = requests.post('https://api.freshbooks.com/auth/oauth/token', data={
        'grant_type': 'authorization_code',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'code': auth_code,
        'redirect_uri': REDIRECT_URI
    })
    
    token_data = token_response.json()
    
    if 'access_token' not in token_data:
        print(f"✗ Failed to get access token: {token_data}")
        return
    
    access_token = token_data['access_token']
    print(f"✓ Access token received: {access_token[:50]}...")
    print()
    
    # Step 4: Test API
    print("Step 4: Testing API with access token...")
    print("-" * 60)
    
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
        print(f"  Response: {me_response.text}")
        return
    
    print()
    print("=" * 60)
    print("✓ Authentication test completed successfully!")
    print("=" * 60)
    print()
    print(f"Access Token: {access_token}")
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
