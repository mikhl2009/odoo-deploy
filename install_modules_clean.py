#!/usr/bin/env python3
"""
Install Odoo modules in correct order on clean database.
Uses XML-RPC API to call button_immediate_install.
"""
import xmlrpc.client
import os

# Odoo connection settings
ODOO_URL = "https://snushallen.cloud"
ODOO_DB = "odoo_production"
ODOO_USER = "mikael@snushallen.se"
ODOO_PASSWORD = "d429e24c601e4476177ecf8051d81556c8f0f7b9"

def connect_odoo():
    """Connect to Odoo and authenticate."""
    common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common')
    uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})
    
    if not uid:
        raise Exception("Authentication failed!")
    
    print(f"✅ Connected to Odoo as user ID: {uid}")
    models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')
    return models, uid

def install_module(models, uid, module_name):
    """Install a module by name."""
    try:
        print(f"\n📦 Installing module: {module_name}")
        
        # Search for the module
        module_ids = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            'ir.module.module', 'search',
            [[['name', '=', module_name]]]
        )
        
        if not module_ids:
            print(f"❌ Module {module_name} not found!")
            return False
        
        module_id = module_ids[0]
        
        # Check current state
        module_data = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            'ir.module.module', 'read',
            [module_id], {'fields': ['state', 'shortdesc']}
        )[0]
        
        print(f"   Current state: {module_data['state']}")
        
        if module_data['state'] == 'installed':
            print(f"✅ {module_name} already installed")
            return True
        
        # Install the module using button_immediate_install
        print(f"   Installing {module_data['shortdesc']}...")
        models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            'ir.module.module', 'button_immediate_install',
            [[module_id]]
        )
        
        print(f"✅ Successfully installed {module_name}")
        return True
        
    except Exception as e:
        print(f"❌ Error installing {module_name}: {str(e)}")
        return False

def main():
    """Main installation sequence."""
    print("=" * 60)
    print("ODOO MODULE INSTALLATION - CLEAN DATABASE")
    print("=" * 60)
    
    # Connect to Odoo
    models, uid = connect_odoo()
    
    # Modules to install in order
    modules_sequence = [
        ('stock', 'Required for WMS functionality'),
        ('sale_management', 'Sales module'),
        ('purchase', 'Purchase module'),
        ('barcodes', 'Barcode scanning'),
        ('prima_wms', 'Prima WMS custom extension')
    ]
    
    print("\n📋 Installation sequence:")
    for i, (module, desc) in enumerate(modules_sequence, 1):
        print(f"   {i}. {module} - {desc}")
    
    # Install each module
    for module_name, description in modules_sequence:
        success = install_module(models, uid, module_name)
        if not success:
            print(f"\n⚠️  Warning: Failed to install {module_name}")
            print("Continuing with next module...")
    
    print("\n" + "=" * 60)
    print("✅ INSTALLATION COMPLETED!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Verify modules in Odoo UI: Apps → Installed")
    print("2. Check Prima WMS fields in Products")
    print("3. Restart Odoo container to load OCA modules")
    print("4. Update Apps List to see OCA WMS modules")

if __name__ == "__main__":
    main()
