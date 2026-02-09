#!/usr/bin/env python3
"""
Script för att installera Odoo-moduler via XML-RPC API
"""
import xmlrpc.client
import sys

# Odoo-anslutningsinformation
ODOO_URL = "https://snushallen.cloud"
ODOO_DB = "odoo"
ODOO_USERNAME = "mikael@snushallen.se"
ODOO_PASSWORD = "f9acc9818d15a4c30caf92dd7db006c948cbe294"  # API-nyckel

# Moduler att installera (i ordning)
MODULES_TO_INSTALL = [
    # Core Odoo-moduler
    "stock",                    # Inventory/Lager
    "sale_management",          # Försäljning
    "purchase",                 # Inköp
    "barcodes",                 # Streckkoder
    
    # OCA WMS-moduler (om tillgängliga)
    "shopfloor",                # Scanner-gränssnitt
    "stock_storage_type",       # Lagerplatstyper
    "stock_location_zone",      # Lagerzoner
    "stock_barcode",            # Streckkodsscanning
    
    # Custom modul
    "prima_wms",                # Din egen modul
]

def connect_odoo():
    """Anslut till Odoo och returnera API-objekt"""
    print(f"🔗 Ansluter till {ODOO_URL}...")
    
    common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common')
    
    # Autentisera
    try:
        uid = common.authenticate(ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD, {})
        if not uid:
            print("❌ Autentisering misslyckades!")
            sys.exit(1)
        print(f"✅ Ansluten som användare ID: {uid}")
    except Exception as e:
        print(f"❌ Fel vid anslutning: {e}")
        sys.exit(1)
    
    models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')
    return uid, models


def update_module_list(uid, models):
    """Uppdatera modullistan"""
    print("\n📋 Uppdaterar modullista...")
    try:
        models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            'ir.module.module', 'update_list', []
        )
        print("✅ Modullista uppdaterad!")
    except Exception as e:
        print(f"⚠️  Varning vid uppdatering av modullista: {e}")


def install_module(uid, models, module_name):
    """Installera en specifik modul"""
    try:
        # Sök efter modulen
        module_ids = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            'ir.module.module', 'search',
            [[['name', '=', module_name]]]
        )
        
        if not module_ids:
            print(f"⚠️  Modul '{module_name}' hittades inte")
            return False
        
        # Kolla status
        module_info = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            'ir.module.module', 'read',
            [module_ids], {'fields': ['name', 'state', 'shortdesc']}
        )[0]
        
        state = module_info['state']
        desc = module_info.get('shortdesc', module_name)
        
        if state == 'installed':
            print(f"✅ {desc} - redan installerad")
            return True
        elif state == 'to install':
            print(f"⏳ {desc} - väntar på installation")
            return True
        elif state == 'uninstalled':
            print(f"📦 Installerar {desc}...")
            # Installera modulen
            models.execute_kw(
                ODOO_DB, uid, ODOO_PASSWORD,
                'ir.module.module', 'button_immediate_install',
                [module_ids]
            )
            print(f"✅ {desc} - installerad!")
            return True
        else:
            print(f"⚠️  {desc} - okänd status: {state}")
            return False
            
    except Exception as e:
        print(f"❌ Fel vid installation av '{module_name}': {e}")
        return False


def main():
    """Huvudfunktion"""
    print("=" * 60)
    print("🚀 ODOO MODULE INSTALLER")
    print("=" * 60)
    
    # Anslut till Odoo
    uid, models = connect_odoo()
    
    # Uppdatera modullista
    update_module_list(uid, models)
    
    # Installera moduler
    print(f"\n📦 Installerar {len(MODULES_TO_INSTALL)} moduler...\n")
    
    success_count = 0
    failed_modules = []
    
    for module in MODULES_TO_INSTALL:
        if install_module(uid, models, module):
            success_count += 1
        else:
            failed_modules.append(module)
        print()  # Tom rad mellan moduler
    
    # Sammanfattning
    print("=" * 60)
    print("📊 SAMMANFATTNING")
    print("=" * 60)
    print(f"✅ Lyckade: {success_count}/{len(MODULES_TO_INSTALL)}")
    
    if failed_modules:
        print(f"⚠️  Misslyckade/Saknas: {len(failed_modules)}")
        for module in failed_modules:
            print(f"   - {module}")
    else:
        print("🎉 Alla moduler installerade!")
    
    print("\n💡 Tips: Vissa moduler kan kräva omstart av Odoo-servern")
    print("=" * 60)


if __name__ == "__main__":
    main()
