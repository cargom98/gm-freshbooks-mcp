#!/usr/bin/env python3
"""Test HTTPS server on localhost:8080"""

import os
import ssl
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

CERT_FILE = os.path.expanduser("~/.freshbooks_cert.pem")
KEY_FILE = os.path.expanduser("~/.freshbooks_key.pem")

class TestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'<html><body><h1>HTTPS Server is working!</h1></body></html>')
        print(f"Received request: {self.path}")
    
    def log_message(self, format, *args):
        print(f"[Server] {format % args}")

def generate_cert():
    """Generate self-signed certificate"""
    if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
        print(f"✓ Using existing certificate at {CERT_FILE}")
        return True
    
    print("Generating self-signed certificate...")
    cmd = f'openssl req -x509 -newkey rsa:2048 -keyout {KEY_FILE} -out {CERT_FILE} -days 365 -nodes -subj "/CN=localhost" 2>&1'
    result = os.system(cmd)
    
    if result == 0:
        print(f"✓ Certificate generated successfully")
        return True
    else:
        print("✗ Failed to generate certificate")
        return False

def test_server():
    print("=" * 60)
    print("Testing HTTPS Server on localhost:8080")
    print("=" * 60)
    print()
    
    # Generate certificate
    if not generate_cert():
        return
    print()
    
    # Create HTTPS server
    print("Starting HTTPS server on https://localhost:8080...")
    try:
        server = HTTPServer(('localhost', 8080), TestHandler)
        
        # Wrap with SSL
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(CERT_FILE, KEY_FILE)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        
        print("✓ Server started successfully!")
        print()
        print("Server is listening on https://localhost:8080")
        print("Open your browser and go to: https://localhost:8080/test")
        print()
        print("⚠️  You'll see a security warning - click 'Advanced' and 'Proceed'")
        print()
        print("Press Ctrl+C to stop the server")
        print("-" * 60)
        print()
        
        # Serve forever
        server.serve_forever()
        
    except OSError as e:
        if e.errno == 48:  # Address already in use
            print(f"✗ Port 8080 is already in use")
            print("  Try: lsof -ti:8080 | xargs kill -9")
        else:
            print(f"✗ Error starting server: {e}")
    except KeyboardInterrupt:
        print("\n\n✓ Server stopped")
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_server()
