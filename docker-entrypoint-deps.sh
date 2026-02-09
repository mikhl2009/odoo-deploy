#!/bin/bash
set -e

# Install WooCommerce Python dependencies if not already present
echo "Checking WooCommerce Python dependencies..."

# Check if packages are installed
python3 -c "import filetype" 2>/dev/null || NEED_INSTALL=1
python3 -c "import phonenumbers" 2>/dev/null || NEED_INSTALL=1
python3 -c "import woocommerce" 2>/dev/null || NEED_INSTALL=1

if [ "$NEED_INSTALL" = "1" ]; then
    echo "Installing WooCommerce dependencies: filetype, phonenumbers, woocommerce..."
    pip3 install --user --no-warn-script-location filetype phonenumbers woocommerce
    echo "✅ WooCommerce dependencies installed successfully!"
else
    echo "✅ WooCommerce dependencies already installed."
fi

# Run original Odoo entrypoint
exec /entrypoint.sh "$@"
