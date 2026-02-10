#!/usr/bin/env python3
"""
Installerar Odoo-moduler i rätt ordning för WMS + WooCommerce
"""
import xmlrpc.client
import time

# Odoo connection - uppdatera dessa vid behov
url = "https://snushallen.cloud"
db = "odoo"
username = "mikael@snushallen.se"
password = "a04315610102c5d4cde37f7c8afea09d8721569a"  # API key

def connect():
    """Ansluter till Odoo"""
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, username, password, {})
    if not uid:
        raise Exception("Autentisering misslyckades")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    print(f"✓ Ansluten till {url} (db: {db}, uid: {uid})")
    return uid, models

def install_module(models, uid, module_name):
    """Installerar en modul och väntar på att den blir klar"""
    print(f"\n{'='*50}")
    print(f"Installerar: {module_name}")
    print('='*50)
    
    # Hitta modulen
    module_ids = models.execute_kw(
        db, uid, password,
        'ir.module.module', 'search',
        [[['name', '=', module_name]]]
    )
    
    if not module_ids:
        print(f"  ✗ Modul '{module_name}' hittades inte!")
        return False
    
    module_id = module_ids[0]
    
    # Kolla status
    info = models.execute_kw(
        db, uid, password,
        'ir.module.module', 'read',
        [module_id], {'fields': ['state', 'shortdesc']}
    )[0]
    
    print(f"  Namn: {info['shortdesc']}")
    print(f"  Status: {info['state']}")
    
    if info['state'] == 'installed':
        print(f"  ✓ Redan installerad, hoppar över")
        return True
    
    # Installera
    print(f"  Installerar...")
    try:
        models.execute_kw(
            db, uid, password,
            'ir.module.module', 'button_immediate_install',
            [[module_id]]
        )
        print(f"  ✓ Installation klar!")
        return True
    except Exception as e:
        print(f"  ✗ Fel: {e}")
        return False

def main():
    print("\n" + "="*60)
    print("ODOO MODULINSTALLATION - WMS + WooCommerce")
    print("="*60)
    
    # Moduler i rätt ordningsföljd
    # queue_job MÅSTE installeras FÖRE woocommerce_sync
    modules = [
        "stock",            # 1. Lager/Inventory (bas för WMS)
        "sale_management",  # 2. Försäljning
        "purchase",         # 3. Inköp
        "queue_job",        # 4. Jobbkö (krävs av WooCommerce)
        "prima_wms",        # 5. Prima WMS custom extension
        "woocommerce_sync", # 6. WooCommerce Sync (sist, beror på queue_job)
    ]
    
    try:
        uid, models = connect()
        
        # Uppdatera modullistan först
        print("\nUppdaterar modullistan...")
        models.execute_kw(
            db, uid, password,
            'ir.module.module', 'update_list',
            []
        )
        print("✓ Modullistan uppdaterad")
        
        # Installera moduler i ordning
        results = {}
        for module in modules:
            success = install_module(models, uid, module)
            results[module] = success
            if success:
                time.sleep(2)  # Vänta mellan installationer
        
        # Sammanfattning
        print("\n" + "="*60)
        print("SAMMANFATTNING")
        print("="*60)
        for module, success in results.items():
            status = "✓ OK" if success else "✗ MISSLYCKADES"
            print(f"  {module}: {status}")
        
        if all(results.values()):
            print("\n✓ Alla moduler installerade!")
            print("\nNästa steg:")
            print("1. Gå till Inställningar → Tekniska → WooCommerce Websites")
            print("2. Skapa en ny website med dina WooCommerce API-nycklar")
            print("3. Kör första synkroniseringen")
        else:
            print("\n⚠ Vissa moduler misslyckades, se ovan")
            
    except Exception as e:
        print(f"\n✗ Fel: {e}")

if __name__ == "__main__":
    main()
