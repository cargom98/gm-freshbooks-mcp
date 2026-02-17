#!/usr/bin/env python3
"""Test FreshBooks OAuth using Cloudflare Tunnel for public HTTPS callback"""

import os
import json
import time
import subprocess
import threading
import webbrowser
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import requests

# Configuration
CLIENT_ID = os.getenv("FRESHBOOKS_CLIENT_ID")
CLIENT_SECRET = os.getenv("FRESHBOOKS_CLIENT_SECRET")

if not CLIENT_ID or not CLIENT_SECRET:
    print("Error: Please set FRESHBOOKS_CLIENT_ID and FRESHBOOKS_CLIENT_SECRET environment variables")
    sys.exit(1)

auth_code = None
tunnel_url = None
cloudflared_process = None

class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
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
        </body>
        </html>
        '''
        self.wfile.write(html.encode('utf-8'))
        
        print(f"\n✓ Received callback with authorization code")
    
    def log_message(self, format, *args):
        pass

def start_cloudflared_tunnel():
    """Start cloudflared tunnel and extract the public URL"""
    global tunnel_url, cloudflared_process
    
    print("Starting Cloudflare Tunnel...")
    print("(This will create a temporary public HTTPS URL)")
    print()
    
    try:
        # Start cloudflared tunnel
        cloudflared_process = subprocess.Popen(
            ['cloudflared', 'tunnel', '--url', 'http://localhost:8080'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        # Wait for tunnel URL to appear in output
        url_pattern = re.compile(r'https://[a-z0-9-]+\.trycloudflare\.com')
        
        for line in cloudflared_process.stdout:
            print(f"  [cloudflared] {line.strip()}")
            match = url_pattern.search(line)
            if match:
                tunnel_url = match.group(0)
                print()
                print(f"✓ Tunnel URL: {tunnel_url}")
                break
        
        if not tunnel_url:
            print("✗ Failed to get tunnel URL")
            return False
        
        return True
        
    except FileNotFoundError:
        print("✗ cloudflared not found!")
        print()
        print("Install cloudflared:")
        print("  macOS: brew install cloudflared")
        print("  Linux: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/")
        return False
    except Exception as e:
        print(f"✗ Error starting tunnel: {e}")
        return False

def stop_cloudflared_tunnel():
    """Stop the cloudflared tunnel"""
    global cloudflared_process
    if cloudflared_process:
        print("\nStopping Cloudflare Tunnel...")
        cloudflared_process.terminate()
        cloudflared_process.wait()

def run_server(server):
    """Run HTTP server in background thread"""
    try:
        # Handle multiple requests
        for _ in range(5):
            server.handle_request()
    except Exception as e:
        print(f"  [Server] Error: {e}")

def main():
    print("=" * 70)
    print("FreshBooks OAuth with Cloudflare Tunnel")
    print("=" * 70)
    print()
    
    # Step 1: Start local HTTP server
    print("Step 1: Starting local HTTP server...")
    print("-" * 70)
    
    try:
        server = HTTPServer(('localhost', 8080), CallbackHandler)
        print("✓ HTTP server listening on http://localhost:8080")
        
        # Start server in background thread
        server_thread = threading.Thread(target=run_server, args=(server,), daemon=True)
        server_thread.start()
        
    except Exception as e:
        print(f"✗ Failed to start server: {e}")
        return
    
    print()
    
    # Step 2: Start Cloudflare Tunnel
    print("Step 2: Starting Cloudflare Tunnel...")
    print("-" * 70)
    
    if not start_cloudflared_tunnel():
        return
    
    # Give tunnel a moment to stabilize
    time.sleep(2)
    print()
    
    # Step 3: Display instructions
    print("Step 3: Configure FreshBooks App")
    print("-" * 70)
    print()
    print("⚠️  IMPORTANT: Update your FreshBooks app configuration:")
    print()
    print("  1. Go to: https://my.freshbooks.com/#/developer")
    print("  2. Edit your app")
    print("  3. Set Redirect URI to:")
    print(f"     {tunnel_url}/callback")
    print()
    print("  4. Save the changes")
    print()
    
    input("Press ENTER when you've updated the redirect URI...")
    print()
    
    # Step 4: Open browser for authorization
    print("Step 4: Opening browser for authorization...")
    print("-" * 70)
    
    redirect_uri = f"{tunnel_url}/callback"
    auth_url = f"https://auth.freshbooks.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={redirect_uri}"
    
    print(f"Authorization URL: {auth_url[:80]}...")
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
        stop_cloudflared_tunnel()
        return
    
    print()
    
    # Step 5: Exchange code for token
    print("Step 5: Exchanging code for access token...")
    print("-" * 70)
    
    token_response = requests.post('https://api.freshbooks.com/auth/oauth/token', data={
        'grant_type': 'authorization_code',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'code': auth_code,
        'redirect_uri': redirect_uri
    })
    
    token_data = token_response.json()
    
    if 'access_token' not in token_data:
        print(f"✗ Failed to get access token: {token_data}")
        stop_cloudflared_tunnel()
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
    print("Step 6: Testing API with access token...")
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
        print(f"  Response: {me_response.text}")
        stop_cloudflared_tunnel()
        return
    
    print()
    print("=" * 70)
    print("✓ Authentication completed successfully!")
    print("=" * 70)
    print()
    print(f"Access Token: {access_token[:50]}...")
    print(f"Refresh Token: {refresh_token[:50] if refresh_token else 'N/A'}...")
    print()
    
    # Cleanup
    stop_cloudflared_tunnel()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        stop_cloudflared_tunnel()
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        stop_cloudflared_tunnel()
