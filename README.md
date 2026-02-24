# FreshBooks MCP Server

An MCP (Model Context Protocol) server for FreshBooks API with OAuth 2.0 authentication using Cloudflare Tunnel.

## Features

- OAuth 2.0 authentication flow with Cloudflare Tunnel
- Automatic token refresh
- Token persistence across sessions
- Comprehensive FreshBooks API integration:
  - Account information
  - Clients management
  - Invoices
  - Expenses
  - Projects

## Prerequisites

1. **FreshBooks Developer Account**
   - Go to [FreshBooks Developer Portal](https://my.freshbooks.com/#/developer)
   - Create a new application
   - Note your Client ID and Client Secret

2. **Cloudflare Tunnel** (for OAuth callback)
   - Install cloudflared: `brew install cloudflared` (macOS)
   - Set up a tunnel pointing to `http://localhost:8000`
   - Note your tunnel URL (e.g., `https://test.devopsengineer.com`)

3. **Python Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

## Setup

### 1. Configure FreshBooks App

1. Go to [FreshBooks Developer Portal](https://my.freshbooks.com/#/developer)
2. Edit your application
3. Set the Redirect URI to: `https://your-tunnel-url.com/callback`
   - Example: `https://test.devopsengineer.com/callback`
4. Save changes

### 2. Start Cloudflare Tunnel

Make sure your tunnel is running and pointing to `http://localhost:8000`:

```bash
# If using cloudflared tunnel
cloudflared tunnel --url http://localhost:8000

# Or if you have a configured tunnel
cloudflared tunnel run your-tunnel-name
```

### 3. Test Authentication Flow

Run the test script to verify OAuth works:

```bash
python3 tests/test_existing_tunnel.py
```

This will:
- Start local server on port 8000
- Open browser for FreshBooks authorization
- Capture the callback via your tunnel
- Exchange code for access token
- Save token to `~/.freshbooks_token.json`

### 4. Configure MCP Client

Copy the example configuration:

```bash
cp docs/mcp.json.example ~/.kiro/settings/mcp.json
```

**Or manually add to your MCP configuration:**

```json
{
  "mcpServers": {
    "freshbooks": {
      "command": "python3",
      "args": ["/path/to/freshbooks_server.py"],
      "env": {
        "FRESHBOOKS_CLIENT_ID": "your_client_id",
        "FRESHBOOKS_CLIENT_SECRET": "your_client_secret",
        "FRESHBOOKS_TUNNEL_URL": "https://your-tunnel-url.com",
        "FRESHBOOKS_LOCAL_PORT": "8000"
      },
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

**Important:** Update the following in your MCP configuration:
- `args[0]`: Full path to `freshbooks_server.py`
- `FRESHBOOKS_CLIENT_ID`: Your FreshBooks Client ID
- `FRESHBOOKS_CLIENT_SECRET`: Your FreshBooks Client Secret
- `FRESHBOOKS_TUNNEL_URL`: Your Cloudflare tunnel URL

## Usage

Once configured, the MCP server provides these tools:

### Available Tools

- `get_account_info` - Get account information and user profile
- `list_clients` - Get all clients
- `get_client` - Get specific client by ID
- `list_invoices` - Get all invoices
- `get_invoice` - Get specific invoice by ID
- `list_expenses` - Get all expenses (with pagination)
- `list_projects` - Get all projects
- `upload_attachment` - Upload a receipt image or PDF file
- `attach_receipt_to_expense` - Attach an uploaded receipt to an expense

### Attaching Receipts to Expenses

The server supports a two-step process for attaching receipts:

1. **Upload the receipt file:**
   ```
   Tool: upload_attachment
   Parameters:
     - file_path: Local path to the receipt (PNG, JPEG, or PDF)
   Returns: JWT token and attachment details
   ```

2. **Attach to expense:**
   ```
   Tool: attach_receipt_to_expense
   Parameters:
     - expense_id: The FreshBooks expense ID
     - jwt: JWT token from upload_attachment
     - media_type: File type (e.g., 'image/png', 'image/jpeg', 'application/pdf')
   ```

**Example workflow:**
1. Upload receipt: `upload_attachment(file_path="receipt.png")`
2. Get JWT from response
3. Attach to expense: `attach_receipt_to_expense(expense_id="123", jwt="...", media_type="image/png")`

**Note:** The upload_attachment feature requires your FreshBooks app to have the appropriate OAuth permissions. If you receive a 403 Forbidden error, check your app settings in the [FreshBooks Developer Portal](https://my.freshbooks.com/#/developer) to ensure it has full expense management permissions.

### Authentication Flow

1. **First Use:** Server checks for token in `~/.freshbooks_token.json`
2. **No Token:** Initiates OAuth flow:
   - Starts local HTTP server on port 8000
   - Opens browser to FreshBooks authorization
   - Receives callback via Cloudflare tunnel
   - Exchanges code for access token
   - Saves token for future use
3. **Token Exists:** Validates token with FreshBooks API
4. **Token Expired:** Automatically refreshes using refresh_token
5. **Subsequent Requests:** Uses saved token

## Testing

### Test OAuth Flow

```bash
python3 tests/test_existing_tunnel.py
```

### Test Individual Components

```bash
# Test HTTP server
python3 tests/test_port_listening.py

# Test with HTTP (no SSL)
python3 tests/test_http_auth.py

# Test API endpoints
python3 tests/test_api.py

# Test client operations
python3 tests/test_clients.py

# Test invoice operations
python3 tests/test_invoices.py
```

## Troubleshooting

### OAuth Callback Not Received

1. Verify tunnel is running: `curl https://your-tunnel-url.com`
2. Check tunnel points to `http://localhost:8000`
3. Verify FreshBooks redirect URI matches exactly
4. Check local server is running on port 8000

### Port Already in Use

```bash
# Find process using port 8000
lsof -ti:8000

# Kill the process
lsof -ti:8000 | xargs kill -9
```

### Token Issues

```bash
# Remove saved token to force re-authentication
rm ~/.freshbooks_token.json
```

### MCP Server Not Starting

1. Check Python path in `mcp.json`
2. Verify environment variables are set
3. Check MCP server logs
4. Test server manually: `python3 freshbooks_server.py`

## Architecture

```
┌─────────────┐
│   Kiro/MCP  │
│   Client    │
└──────┬──────┘
       │
       │ stdio
       │
┌──────▼──────────────────┐
│  FreshBooks MCP Server  │
│  (freshbooks_server.py) │
└──────┬──────────────────┘
       │
       │ OAuth Flow (first time)
       │
┌──────▼──────────────────┐
│  Local HTTP Server      │
│  localhost:8000         │
└──────┬──────────────────┘
       │
       │ via Cloudflare Tunnel
       │
┌──────▼──────────────────┐
│  https://tunnel-url.com │
│  (Public HTTPS)         │
└──────┬──────────────────┘
       │
       │ OAuth Callback
       │
┌──────▼──────────────────┐
│  FreshBooks OAuth       │
│  Authorization          │
└─────────────────────────┘
```

## Security Notes

- Client Secret is stored in MCP configuration (keep secure)
- Access tokens are stored in `~/.freshbooks_token.json`
- Tokens are automatically refreshed when expired
- OAuth flow uses authorization code grant (most secure)
- Cloudflare Tunnel provides HTTPS without exposing local network

## Project Structure

```
freshbooks-mcp/
├── freshbooks_server.py      # Main MCP server
├── requirements.txt           # Python dependencies
├── README.md                  # This file
├── .gitignore                # Git ignore rules
├── docs/
│   └── mcp.json.example      # Example MCP configuration
├── scripts/
│   └── setup_cloudflared.sh  # Cloudflare tunnel setup script
└── tests/
    ├── test_api.py           # API integration tests
    ├── test_attach_receipt.py # Receipt attachment tests
    ├── test_auth_flow.py     # OAuth flow tests
    ├── test_clients.py       # Client API tests
    ├── test_cloudflared_auth.py
    ├── test_existing_tunnel.py
    ├── test_http_auth.py
    ├── test_https_server.py
    ├── test_invoices.py      # Invoice API tests
    ├── test_port_listening.py
    ├── test_simple_auth.py
    └── test_token.py         # Token management tests
```
