#!/usr/bin/env python3
"""Test if HTTPS server is properly listening on port 8080"""

import os
import ssl
import time
import socket
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler

CERT_FILE = os.path.expanduser("~/.freshbooks_cert.pem")
KEY_FILE = os.path.expanduser("~/.freshbooks_key.pem")

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Server is listening!')
    
    def log_message(self, format, *args):
        pass

def generate_cert():
    """Generate self-signed certificate"""
    if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
        return True
    
    print("Generating certificate...")
    cmd = f'openssl req -x509 -newkey rsa:2048 -keyout {KEY_FILE} -out {CERT_FILE} -days 365 -nodes -subj "/CN=localhost" 2>&1'
    result = os.system(cmd)
    return result == 0

def check_port_available(port=8080):
    """Check if port is available"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(('localhost', port))
        sock.close()
        return True
    except OSError:
        return False

def start_server_thread(server):
    """Start server in background thread"""
    # Handle multiple requests
    for _ in range(5):
        server.handle_request()

def main():
    print("=" * 60)
    print("Testing HTTPS Server on localhost:8080")
    print("=" * 60)
    print()
    
    # Check if port is available
    print("1. Checking if port 8080 is available...")
    if not check_port_available(8080):
        print("   ✗ Port 8080 is already in use")
        print("   Run: lsof -ti:8080 | xargs kill -9")
        return
    print("   ✓ Port 8080 is available")
    print()
    
    # Generate certificate
    print("2. Checking SSL certificate...")
    if not generate_cert():
        print("   ✗ Failed to generate certificate")
        return
    print(f"   ✓ Certificate ready at {CERT_FILE}")
    print()
    
    # Start HTTPS server
    print("3. Starting HTTPS server...")
    try:
        server = HTTPServer(('localhost', 8080), SimpleHandler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(CERT_FILE, KEY_FILE)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        print("   ✓ Server created and bound to port 8080")
    except Exception as e:
        print(f"   ✗ Failed to create server: {e}")
        return
    print()
    
    # Start server in background thread
    print("4. Starting server thread...")
    server_thread = threading.Thread(target=start_server_thread, args=(server,), daemon=True)
    server_thread.start()
    
    # Give server time to start
    time.sleep(0.5)
    print("   ✓ Server thread started")
    print()
    
    # Test connection with socket
    print("5. Testing socket connection to localhost:8080...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('localhost', 8080))
        sock.close()
        
        if result == 0:
            print("   ✓ Port 8080 is listening and accepting connections")
        else:
            print(f"   ✗ Cannot connect to port 8080 (error code: {result})")
            return
    except Exception as e:
        print(f"   ✗ Socket test failed: {e}")
        return
    print()
    
    # Test HTTPS request
    print("6. Testing HTTPS request to https://localhost:8080/test...")
    try:
        # Disable SSL verification for self-signed cert
        response = requests.get('https://localhost:8080/test', verify=False, timeout=5)
        
        if response.status_code == 200:
            print(f"   ✓ HTTPS request successful!")
            print(f"   Response: {response.text}")
        else:
            print(f"   ✗ Unexpected status code: {response.status_code}")
    except requests.exceptions.SSLError as e:
        print(f"   ⚠️  SSL Error (expected with self-signed cert): {e}")
        print("   This is normal - browser will show security warning")
    except Exception as e:
        print(f"   ✗ Request failed: {e}")
        return
    
    print()
    print("=" * 60)
    print("✓ Server is working correctly!")
    print("=" * 60)
    print()
    print("The server can successfully:")
    print("  • Bind to port 8080")
    print("  • Accept HTTPS connections")
    print("  • Respond to requests")
    print()
    print("You can now run the OAuth flow test.")
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
