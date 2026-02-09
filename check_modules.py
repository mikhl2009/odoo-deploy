#!/usr/bin/env python3
"""
Fix Odoo warehouse issue and list available modules
"""
import xmlrpc.client
import sys

ODOO_URL = "https://snushallen.cloud"
ODOO_DB = "odoo"
ODOO_USERNAME = "mikael@snushallen.se"
ODOO_PASSWORD = "f9acc9818d15a4c30caf92dd7db006c948cbe294"

def connect_odoo():
    common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common')
    uid = common.authenticate(ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD, {})
    if not uid:
        print("❌ Autentisering misslyckades!")
        sys.exit(1)
    models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')
    return uid, models

def list_available_modules(uid, models, search_term=""):
    """Lista tillgängliga moduler"""
    print(f"\n🔍 Söker moduler med '{search_term}'...")
    
    domain = [] if not search_term else [
        '|', ['name', 'ilike', search_term],
        ['shortdesc', 'ilike', search_term]
    ]
    
    module_ids = models.execute_kw(
        ODOO_DB, uid, ODOO_PASSWORD,
        'ir.module.module', 'search',
        [domain]
    )
    
    modules = models.execute_kw(
        ODOO_DB, uid, ODOO_PASSWORD,
        'ir.module.module', 'read',
        [module_ids], 
        {'fields': ['name', 'state', 'shortdesc'], 'limit': 50}
    )
    
    # Gruppera per status
    by_state = {}
    for mod in modules:
        state = mod['state']
        if state not in by_state:
            by_state[state] = []
        by_state[state].append(mod)
    
    # Visa resultat
    for state, mods in sorted(by_state.items()):
        print(f"\n📦 Status: {state.upper()} ({len(mods)})")
        for mod in sorted(mods, key=lambda x: x['name']):
            desc = mod.get('shortdesc', mod['name'])
            print(f"   • {mod['name']:<30} {desc}")
    
    return modules

def check_module_status(uid, models):
    """Kontrollera status på viktiga moduler"""
    important_modules = ['stock', 'sale_management', 'purchase', 'prima_wms']
    
    print("\n" + "="*60)
    print("📊 STATUS PÅ VIKTIGA MODULER")
    print("="*60)
    
    for module_name in important_modules:
        module_ids = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            'ir.module.module', 'search',
            [[['name', '=', module_name]]]
        )
        
        if not module_ids:
            print(f"❌ {module_name:<25} - HITTADES INTE")
            continue
        
        module_info = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            'ir.module.module', 'read',
            [module_ids], 
            {'fields': ['name', 'state', 'shortdesc']}
        )[0]
        
        state = module_info['state']
        desc = module_info.get('shortdesc', module_name)
        
        status_emoji = {
            'installed': '✅',
            'to install': '⏳',
            'to upgrade': '🔄',
            'uninstalled': '📦',
            'uninstallable': '⚠️'
        }.get(state, '❓')
        
        print(f"{status_emoji} {desc:<40} [{state}]")

def main():
    print("="*60)
    print("🔍 ODOO MODULE CHECKER")
    print("="*60)
    
    uid, models = connect_odoo()
    print("✅ Ansluten!")
    
    # Uppdatera modullista
    print("\n📋 Uppdaterar modullista...")
    models.execute_kw(
        ODOO_DB, uid, ODOO_PASSWORD,
        'ir.module.module', 'update_list', []
    )
    print("✅ Klar!")
    
    # Kontrollera status
    check_module_status(uid, models)
    
    # Lista WMS-relaterade moduler
    print("\n" + "="*60)
    print("🔍 TILLGÄNGLIGA WMS/STOCK-MODULER")
    print("="*60)
    list_available_modules(uid, models, "wms")
    list_available_modules(uid, models, "stock")
    list_available_modules(uid, models, "shopfloor")
    list_available_modules(uid, models, "prima")
    
    print("\n" + "="*60)
    print("💡 REKOMMENDATIONER:")
    print("="*60)
    print("1. Installera moduler via Odoo UI (Apps) istället")
    print("2. Aktivera Developer Mode först (?debug=1)")
    print("3. Sök efter 'Prima WMS' i Apps")
    print("4. OCA-moduler behöver finnas i /mnt/extra-addons")
    print("="*60)

if __name__ == "__main__":
    main()
