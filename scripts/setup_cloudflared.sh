#!/bin/bash
# Setup script for cloudflared tunnel

echo "============================================================"
echo "FreshBooks MCP Server - Cloudflare Tunnel Setup"
echo "============================================================"
echo ""

# Check if cloudflared is installed
if ! command -v cloudflared &> /dev/null; then
    echo "cloudflared is not installed."
    echo ""
    echo "Installing cloudflared..."
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew &> /dev/null; then
            brew install cloudflared
        else
            echo "Homebrew not found. Please install from:"
            echo "https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/"
            exit 1
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
        sudo dpkg -i cloudflared-linux-amd64.deb
        rm cloudflared-linux-amd64.deb
    else
        echo "Unsupported OS. Please install manually from:"
        echo "https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/"
        exit 1
    fi
fi

echo "✓ cloudflared is installed"
echo ""

# Test cloudflared
echo "Testing cloudflared..."
cloudflared --version

echo ""
echo "============================================================"
echo "✓ Setup complete!"
echo "============================================================"
echo ""
echo "You can now run: python3 test_cloudflared_auth.py"
echo ""
