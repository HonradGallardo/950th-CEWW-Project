import os
import django
from django.db import connection

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CEWWproject.settings')
django.setup()

def fix_missing_columns():
    with connection.cursor() as cursor:
        print("Checking and fixing Asset table columns...")
        
        columns_to_add = [
            ("processor", "varchar(100)"),
            ("ram_gb", "integer"),
            ("storage_capacity", "varchar(50)"),
            ("ip_address", "inet"),
            ("mac_address", "varchar(17)"),
            ("firmware_version", "varchar(50)"),
            ("specifications", "jsonb DEFAULT '{}'::jsonb")
        ]
        
        for col_name, col_type in columns_to_add:
            try:
                # We use IF NOT EXISTS to prevent crashing if the column is already there
                cursor.execute(f"ALTER TABLE core_asset ADD COLUMN IF NOT EXISTS {col_name} {col_type};")
                print(f"Successfully ensured '{col_name}' exists.")
            except Exception as e:
                print(f"Error adding '{col_name}': {e}")

if __name__ == "__main__":
    fix_missing_columns()
    print("Database fix complete.")