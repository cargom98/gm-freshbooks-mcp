#!/usr/bin/env python3
"""FreshBooks MCP Server with OAuth Authentication"""

import os
import json
import asyncio
import webbrowser
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Optional
import requests
from mcp.server import Server
from mcp.types import Tool, TextContent
import mcp.server.stdio

# Configuration
CLIENT_ID = os.getenv("FRESHBOOKS_CLIENT_ID")
CLIENT_SECRET = os.getenv("FRESHBOOKS_CLIENT_SECRET")
TUNNEL_URL = os.getenv("FRESHBOOKS_TUNNEL_URL", "https://test.devopsengineer.com")
REDIRECT_URI = f"{TUNNEL_URL}/callback"
LOCAL_PORT = int(os.getenv("FRESHBOOKS_LOCAL_PORT", "8000"))
TOKEN_FILE = os.path.expanduser("~/.freshbooks_token.json")

# Global state
auth_code = None
access_token = None
refresh_token = None
account_id = None
auth_server = None
server_ready = threading.Event()


class CallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler for OAuth callback"""
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
            <p>You can close this window and return to your application.</p>
            <script>setTimeout(function(){ window.close(); }, 3000);</script>
        </body>
        </html>
        '''
        self.wfile.write(html.encode('utf-8'))
    
    def log_message(self, format, *args):
        pass


def run_callback_server(server):
    """Run callback server in background thread"""
    server_ready.set()
    try:
        for _ in range(5):
            server.handle_request()
    except Exception as e:
        print(f"Callback server error: {e}", flush=True)


def start_oauth_flow() -> Optional[str]:
    """Start OAuth flow and return authorization code"""
    global auth_code, auth_server
    auth_code = None
    
    # Start local HTTP server
    try:
        auth_server = HTTPServer(('localhost', LOCAL_PORT), CallbackHandler)
        server_thread = threading.Thread(target=run_callback_server, args=(auth_server,), daemon=True)
        server_thread.start()
        server_ready.wait(timeout=2)
    except Exception as e:
        print(f"Failed to start callback server: {e}", flush=True)
        return None
    
    # Open browser for authorization
    auth_url = f"https://auth.freshbooks.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}"
    print(f"Opening browser for authorization...", flush=True)
    print(f"Redirect URI: {REDIRECT_URI}", flush=True)
    webbrowser.open(auth_url)
    
    # Wait for callback
    import time
    start_time = time.time()
    while not auth_code and (time.time() - start_time) < 120:
        time.sleep(0.5)
    
    return auth_code


def exchange_code_for_token(code: str) -> dict:
    """Exchange authorization code for access token"""
    response = requests.post('https://api.freshbooks.com/auth/oauth/token', data={
        'grant_type': 'authorization_code',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'code': code,
        'redirect_uri': REDIRECT_URI
    })
    
    return response.json()


def refresh_access_token(refresh_tok: str) -> dict:
    """Refresh an expired access token"""
    response = requests.post('https://api.freshbooks.com/auth/oauth/token', data={
        'grant_type': 'refresh_token',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'refresh_token': refresh_tok
    })
    
    return response.json()


def save_token(token_data: dict):
    """Save token data to file"""
    with open(TOKEN_FILE, 'w') as f:
        json.dump(token_data, f, indent=2)


def load_token() -> Optional[dict]:
    """Load token data from file"""
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r') as f:
            return json.load(f)
    return None


def ensure_authenticated() -> bool:
    """Ensure we have a valid access token"""
    global access_token, refresh_token, account_id
    
    # Try to load existing token
    token_data = load_token()
    
    if token_data and 'access_token' in token_data:
        access_token = token_data['access_token']
        refresh_token = token_data.get('refresh_token')
        
        # Test if token is still valid
        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.get('https://api.freshbooks.com/auth/api/v1/users/me', headers=headers)
        
        if response.status_code == 200:
            me_data = response.json()
            if me_data['response'].get('business_memberships'):
                account_id = me_data['response']['business_memberships'][0]['business']['account_id']
            return True
        
        # Try to refresh token
        if refresh_token:
            new_token_data = refresh_access_token(refresh_token)
            if 'access_token' in new_token_data:
                save_token(new_token_data)
                access_token = new_token_data['access_token']
                refresh_token = new_token_data.get('refresh_token')
                
                # Get account ID
                headers = {'Authorization': f'Bearer {access_token}'}
                response = requests.get('https://api.freshbooks.com/auth/api/v1/users/me', headers=headers)
                if response.status_code == 200:
                    me_data = response.json()
                    if me_data['response'].get('business_memberships'):
                        account_id = me_data['response']['business_memberships'][0]['business']['account_id']
                return True
    
    # Need new authorization
    print("No valid token found. Starting OAuth flow...", flush=True)
    code = start_oauth_flow()
    if not code:
        return False
    
    token_data = exchange_code_for_token(code)
    if 'access_token' not in token_data:
        print(f"Failed to get access token: {token_data}", flush=True)
        return False
    
    save_token(token_data)
    access_token = token_data['access_token']
    refresh_token = token_data.get('refresh_token')
    
    # Get account ID
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get('https://api.freshbooks.com/auth/api/v1/users/me', headers=headers)
    if response.status_code == 200:
        me_data = response.json()
        if me_data['response'].get('business_memberships'):
            account_id = me_data['response']['business_memberships'][0]['business']['account_id']
    
    return True


def make_api_request(endpoint: str, method: str = 'GET', data: dict = None) -> dict:
    """Make authenticated API request"""
    if not ensure_authenticated():
        raise Exception("Failed to authenticate")
    
    if not account_id:
        raise Exception("Account ID not available")
    
    headers = {'Authorization': f'Bearer {access_token}'}
    url = f'https://api.freshbooks.com/accounting/account/{account_id}/{endpoint}'
    
    if method == 'GET':
        response = requests.get(url, headers=headers)
    elif method == 'POST':
        response = requests.post(url, headers=headers, json=data)
    elif method == 'PUT':
        response = requests.put(url, headers=headers, json=data)
    elif method == 'DELETE':
        response = requests.delete(url, headers=headers)
    else:
        raise ValueError(f"Unsupported method: {method}")
    
    response.raise_for_status()
    return response.json()


# Initialize MCP server
app = Server("freshbooks-server")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available FreshBooks tools"""
    return [
        Tool(
            name="get_account_info",
            description="Get FreshBooks account information including user profile and business details",
            inputSchema={
                "type": "object",
                "properties": {},
            }
        ),
        Tool(
            name="list_clients",
            description="Get list of clients from FreshBooks",
            inputSchema={
                "type": "object",
                "properties": {},
            }
        ),
        Tool(
            name="get_client",
            description="Get details of a specific client by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "client_id": {
                        "type": "string",
                        "description": "The FreshBooks client ID"
                    }
                },
                "required": ["client_id"]
            }
        ),
        Tool(
            name="list_invoices",
            description="Get list of invoices from FreshBooks",
            inputSchema={
                "type": "object",
                "properties": {},
            }
        ),
        Tool(
            name="get_invoice",
            description="Get details of a specific invoice by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "invoice_id": {
                        "type": "string",
                        "description": "The FreshBooks invoice ID"
                    }
                },
                "required": ["invoice_id"]
            }
        ),
        Tool(
            name="list_expenses",
            description="Get list of expenses from FreshBooks with optional pagination",
            inputSchema={
                "type": "object",
                "properties": {
                    "page": {
                        "type": "number",
                        "description": "Page number to retrieve (default: 1)"
                    },
                    "per_page": {
                        "type": "number",
                        "description": "Number of expenses per page (default: 15, max: 100)"
                    }
                },
            }
        ),
        Tool(
            name="list_projects",
            description="Get list of projects from FreshBooks",
            inputSchema={
                "type": "object",
                "properties": {},
            }
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls"""
    
    if name == "get_account_info":
        if not ensure_authenticated():
            raise Exception("Failed to authenticate")
        
        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.get('https://api.freshbooks.com/auth/api/v1/users/me', headers=headers)
        result = response.json()
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    elif name == "list_clients":
        result = make_api_request("users/clients")
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    elif name == "get_client":
        client_id = arguments.get("client_id")
        result = make_api_request(f"users/clients/{client_id}")
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    elif name == "list_invoices":
        result = make_api_request("invoices/invoices")
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    elif name == "get_invoice":
        invoice_id = arguments.get("invoice_id")
        result = make_api_request(f"invoices/invoices/{invoice_id}")
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    elif name == "list_expenses":
        page = arguments.get("page", 1)
        per_page = arguments.get("per_page", 15)
        endpoint = f"expenses/expenses?page={page}&per_page={per_page}"
        result = make_api_request(endpoint)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    elif name == "list_projects":
        result = make_api_request(f"projects/business_id/{account_id}")
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    else:
        raise ValueError(f"Unknown tool: {name}")


async def main():
    """Run the MCP server"""
    if not CLIENT_ID or not CLIENT_SECRET:
        print("Error: FRESHBOOKS_CLIENT_ID and FRESHBOOKS_CLIENT_SECRET environment variables must be set", flush=True)
        return
    
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
