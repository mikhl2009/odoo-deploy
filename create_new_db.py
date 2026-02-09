#!/usr/bin/env python3
"""
Skapar ny Odoo-databas och installerar moduler i rätt ordning
"""
import xmlrpc.client
import time

# Odoo connection
url = "https://snushallen.cloud"
db_name = "odoo_wms"  # Nytt databasnamn
master_password = "MMMO20092009!"
username = "admin"
password = "admin"  # Standardlösenord för ny databas

def create_database():
    """Skapar ny databas"""
    print(f"Skapar ny databas: {db_name}...")
    
    db = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/db")
    
    try:
        # Skapa databas med demo data avaktiverat
        db.create_database(
            master_password,
            db_name,
            False,  # demo data
            "sv_SE",  # språk
            password  # admin password
        )
        print(f"✓ Databas '{db_name}' skapad")
        return True
    except Exception as e:
        print(f"✗ Fel vid skapande av databas: {e}")
        return False

def connect_odoo():
    """Ansluter till Odoo och returnerar uid och models"""
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    
    print(f"Ansluter till {url} som {username}...")
    uid = common.authenticate(db_name, username, password, {})
    
    if not uid:
        raise Exception("Autentisering misslyckades")
    
    print(f"✓ Ansluten (uid: {uid})")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    return uid, models

def install_module(models, uid, module_name):
    """Installerar en modul"""
    print(f"\nInstallerar modul: {module_name}...")
    
    try:
        # Uppdatera modullista först
        models.execute_kw(
            db_name, uid, password,
            'ir.module.module', 'update_list',
            [[]]
        )
        
        # Hitta modulen
        module_ids = models.execute_kw(
            db_name, uid, password,
            'ir.module.module', 'search',
            [[['name', '=', module_name]]]
        )
        
        if not module_ids:
            print(f"✗ Modul '{module_name}' hittades inte")
            return False
        
        module_id = module_ids[0]
        
        # Kontrollera status
        module_info = models.execute_kw(
            db_name, uid, password,
            'ir.module.module', 'read',
            [module_id], {'fields': ['state', 'shortdesc']}
        )[0]
        
        print(f"  Hittade: {module_info['shortdesc']} (state: {module_info['state']})")
        
        if module_info['state'] == 'installed':
            print(f"  ✓ Redan installerad")
            return True
        
        # Installera
        print(f"  Installerar...")
        models.execute_kw(
            db_name, uid, password,
            'ir.module.module', 'button_immediate_install',
            [[module_id]]
        )
        
        # Vänta lite
        time.sleep(2)
        
        print(f"✓ Modul '{module_name}' installerad")
        return True
        
    except Exception as e:
        print(f"✗ Fel vid installation av {module_name}: {e}")
        return False

def main():
    print("=" * 60)
    print("SKAPAR NY ODOO-DATABAS OCH INSTALLERAR MODULER")
    print("=" * 60)
    
    # Steg 1: Skapa databas
    if not create_database():
        print("\nFel: Kunde inte skapa databas")
        return
    
    print("\nVäntar 10 sekunder på att databasen initieras...")
    time.sleep(10)
    
    try:
        # Steg 2: Anslut
        uid, models = connect_odoo()
        
        # Steg 3: Installera moduler i rätt ordning
        modules = [
            'stock',           # Stock Management
            'sale_management', # Sales
            'purchase',        # Purchase
            'queue_job',       # Queue Job (MÅSTE FÖRST för WooCommerce)
            'prima_wms',       # Prima WMS
            'woocommerce_sync' # WooCommerce Sync
        ]
        
        print("\n" + "=" * 60)
        print("INSTALLERAR MODULER")
        print("=" * 60)
        
        for module in modules:
            success = install_module(models, uid, module)
            if not success and module in ['queue_job', 'woocommerce_sync']:
                print(f"\nVARNING: Kritisk modul misslyckades: {module}")
                print("Fortsätter ändå...")
            time.sleep(3)  # Vänta mellan installationer
        
        print("\n" + "=" * 60)
        print("✓ KLART!")
        print("=" * 60)
        print(f"\nDatabas: {db_name}")
        print(f"URL: {url}")
        print(f"Användare: {username}")
        print(f"Lösenord: {password}")
        print("\nDu kan nu logga in och konfigurera WooCommerce-integration.")
        
    except Exception as e:
        print(f"\n✗ Fel under installation: {e}")

if __name__ == "__main__":
    main()
