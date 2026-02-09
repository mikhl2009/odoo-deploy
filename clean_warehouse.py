#!/usr/bin/env python3
"""
Rensa korrupt warehouse-data från Odoo-databasen
"""
import psycopg2
import sys

# Databasuppgifter (från docker-compose.yml)
DB_HOST = "db"  # Inom Docker-nätverket
DB_PORT = 5432
DB_NAME = "odoo"
DB_USER = "odoo"
DB_PASSWORD = "odoo_secret_2026"

def clean_warehouse_data():
    """Ta bort korrupt warehouse-data"""
    try:
        # Anslut till databasen
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = conn.cursor()
        
        print("🔍 Kollar efter warehouse-data...")
        
        # Kolla om stock_warehouse-tabellen finns
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'stock_warehouse'
            );
        """)
        
        table_exists = cursor.fetchone()[0]
        
        if table_exists:
            print("✅ stock_warehouse-tabell hittad")
            
            # Lista befintliga warehouses
            cursor.execute("SELECT id, name, code FROM stock_warehouse;")
            warehouses = cursor.fetchall()
            
            if warehouses:
                print(f"\n📦 Befintliga lager ({len(warehouses)}):")
                for wh_id, name, code in warehouses:
                    print(f"   ID: {wh_id}, Namn: {name}, Kod: {code}")
                
                print("\n⚠️  Tar bort alla warehouses...")
                cursor.execute("DELETE FROM stock_warehouse;")
                conn.commit()
                print("✅ Alla warehouses borttagna!")
            else:
                print("ℹ️  Inga warehouses att ta bort")
        else:
            print("ℹ️  stock_warehouse-tabell finns inte ännu")
        
        cursor.close()
        conn.close()
        
        print("\n✅ Databas rengjord! Försök installera Stock igen.")
        
    except Exception as e:
        print(f"❌ Fel: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("="*60)
    print("🧹 ODOO DATABASE CLEANER")
    print("="*60)
    clean_warehouse_data()
