#!/usr/bin/env python3
"""Test FreshBooks OAuth authentication flow"""

import os
import sys

# Set your credentials via environment variables
CLIENT_ID = os.getenv("FRESHBOOKS_CLIENT_ID")
CLIENT_SECRET = os.getenv("FRESHBOOKS_CLIENT_SECRET")

if not CLIENT_ID or not CLIENT_SECRET:
    print("Error: Please set FRESHBOOKS_CLIENT_ID and FRESHBOOKS_CLIENT_SECRET environment variables")
    sys.exit(1)

# Set environment variables for the server
os.environ["FRESHBOOKS_CLIENT_ID"] = CLIENT_ID
os.environ["FRESHBOOKS_CLIENT_SECRET"] = CLIENT_SECRET

# Import after setting env vars
import json
from freshbooks_server import (
    ensure_authenticated,
    make_api_request,
    load_token,
    TOKEN_FILE
)

def test_authentication():
    """Test the authentication flow"""
    print("=" * 60)
    print("FreshBooks OAuth Authentication Flow Test")
    print("=" * 60)
    print()
    
    # Check for existing token
    existing_token = load_token()
    if existing_token:
        print(f"✓ Found existing token at {TOKEN_FILE}")
        print(f"  Token preview: {existing_token.get('access_token', '')[:50]}...")
        print()
    else:
        print(f"✗ No existing token found at {TOKEN_FILE}")
        print("  Will initiate OAuth flow...")
        print()
    
    # Test authentication
    print("Step 1: Authenticating...")
    print("-" * 60)
    try:
        if ensure_authenticated():
            print("✓ Authentication successful!")
            print()
        else:
            print("✗ Authentication failed")
            return False
    except Exception as e:
        print(f"✗ Authentication error: {e}")
        return False
    
    # Test account info
    print("Step 2: Fetching account information...")
    print("-" * 60)
    try:
        import requests
        from freshbooks_server import access_token
        
        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.get('https://api.freshbooks.com/auth/api/v1/users/me', headers=headers)
        
        if response.status_code == 200:
            me_data = response.json()
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
            print()
        else:
            print(f"✗ Failed to get account info: {response.status_code}")
            print(f"  Response: {response.text}")
            return False
    except Exception as e:
        print(f"✗ Error fetching account info: {e}")
        return False
    
    # Test API calls
    print("Step 3: Testing API endpoints...")
    print("-" * 60)
    
    # Test clients
    try:
        print("  Testing get_clients...")
        clients = make_api_request("users/clients")
        client_count = len(clients.get('response', {}).get('result', {}).get('clients', []))
        print(f"  ✓ Retrieved {client_count} clients")
    except Exception as e:
        print(f"  ✗ Error getting clients: {e}")
    
    # Test invoices
    try:
        print("  Testing get_invoices...")
        invoices = make_api_request("invoices/invoices")
        invoice_count = len(invoices.get('response', {}).get('result', {}).get('invoices', []))
        print(f"  ✓ Retrieved {invoice_count} invoices")
    except Exception as e:
        print(f"  ✗ Error getting invoices: {e}")
    
    print()
    print("=" * 60)
    print("✓ Authentication flow test completed successfully!")
    print("=" * 60)
    print()
    print(f"Token saved at: {TOKEN_FILE}")
    print("You can now use the MCP server with this authenticated session.")
    print()
    
    return True


if __name__ == "__main__":
    try:
        success = test_authentication()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
