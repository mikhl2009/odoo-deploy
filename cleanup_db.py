#!/usr/bin/env python3
"""
Cleanup script for corrupted Odoo warehouse data.
Run this inside the Odoo container where db hostname resolves.
"""
import os

try:
    import psycopg2
except ImportError:
    print("Installing psycopg2...")
    os.system("pip3 install psycopg2-binary")
    import psycopg2

# Database connection settings from environment
DB_HOST = os.environ.get('HOST', 'db')
DB_PORT = 5432
DB_NAME = os.environ.get('PGDATABASE', 'odoo')
DB_USER = os.environ.get('USER', 'odoo')
DB_PASSWORD = os.environ.get('PASSWORD', 'odoo_secret_2026')

def cleanup_warehouses():
    """Remove all warehouse records to allow clean Stock module installation."""
    try:
        # Connect to database
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        conn.autocommit = True
        cur = conn.cursor()
        
        # Check if table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'stock_warehouse'
            );
        """)
        
        if cur.fetchone()[0]:
            print("Found stock_warehouse table. Cleaning up...")
            
            # Delete all warehouse records
            cur.execute("DELETE FROM stock_warehouse;")
            print("✅ Successfully deleted all warehouse records")
            
            # Also clean related tables if they exist
            related_tables = [
                'stock_location',
                'stock_picking_type',
                'stock_route'
            ]
            
            for table in related_tables:
                cur.execute(f"""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = '{table}'
                    );
                """)
                if cur.fetchone()[0]:
                    cur.execute(f"DELETE FROM {table};")
                    print(f"✅ Cleaned {table}")
        else:
            print("ℹ️  stock_warehouse table does not exist. Nothing to clean.")
        
        cur.close()
        conn.close()
        print("\n✅ Database cleanup completed successfully!")
        print("You can now install the Stock module in Odoo.")
        
    except Exception as e:
        print(f"❌ Error during cleanup: {str(e)}")
        raise

if __name__ == "__main__":
    cleanup_warehouses()
