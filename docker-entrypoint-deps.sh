#!/bin/bash
set -e

echo "Checking WooCommerce Python dependencies..."

# Install missing Python packages only when needed.
python3 -c "import filetype" 2>/dev/null || NEED_INSTALL=1
python3 -c "import phonenumbers" 2>/dev/null || NEED_INSTALL=1
python3 -c "import woocommerce" 2>/dev/null || NEED_INSTALL=1

if [ "${NEED_INSTALL}" = "1" ]; then
    echo "Installing WooCommerce dependencies: filetype, phonenumbers, woocommerce..."
    pip3 install --user --no-warn-script-location filetype phonenumbers woocommerce
    echo "WooCommerce dependencies installed successfully."
else
    echo "WooCommerce dependencies already installed."
fi

# Initialize an empty database so Odoo can serve HTTP/websocket requests.
export DB_HOST="${HOST:-db}"
export DB_PORT="${PORT:-5432}"
export DB_USER="${USER:-odoo}"
export DB_PASSWORD="${PASSWORD:-odoo}"
export DB_NAME="${DB_NAME:-${POSTGRES_DB:-odoo}}"

echo "Checking Odoo database initialization status for '${DB_NAME}'..."
NEEDS_INIT="$(python3 - <<'PY'
import os
import time

import psycopg2

host = os.environ["DB_HOST"]
port = int(os.environ["DB_PORT"])
user = os.environ["DB_USER"]
password = os.environ["DB_PASSWORD"]
dbname = os.environ["DB_NAME"]

conn = None
for attempt in range(30):
    try:
        conn = psycopg2.connect(host=host, port=port, user=user, password=password, dbname=dbname)
        break
    except Exception:
        if attempt == 29:
            raise
        time.sleep(1)

with conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'ir_module_module'
            )
            """
        )
        has_module_table = cur.fetchone()[0]

        if not has_module_table:
            print("1")
        else:
            cur.execute("SELECT state FROM ir_module_module WHERE name = 'base' LIMIT 1")
            row = cur.fetchone()
            print("0" if row and row[0] == "installed" else "1")
PY
)"

if [ "${NEEDS_INIT}" = "1" ]; then
    echo "Database '${DB_NAME}' is empty/uninitialized. Running one-time base install..."
    /entrypoint.sh odoo -d "${DB_NAME}" -i base --without-demo=all --stop-after-init
    echo "Database '${DB_NAME}' initialized."
else
    echo "Database '${DB_NAME}' already initialized."
fi

exec /entrypoint.sh "$@"
