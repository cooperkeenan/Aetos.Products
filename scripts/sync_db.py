#!/usr/bin/env python3
"""
sync_to_db.py - Sync YAML product files to Neon database
"""

import os
import sys
import yaml
import psycopg2
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    print("❌ DATABASE_URL not found in .env file!")
    sys.exit(1)


def connect_db():
    """Connect to Neon database"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        sys.exit(1)


def load_yaml_file(filepath):
    """Load and parse YAML file"""
    try:
        with open(filepath, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"❌ Error reading {filepath}: {e}")
        return None


def upsert_product(cursor, product_data):
    """Insert or update product"""
    try:
        cursor.execute("""
            INSERT INTO products (brand, model, full_name, category, buy_price_min, buy_price_max, sell_target, active)
            VALUES (%(brand)s, %(model)s, %(full_name)s, %(category)s, %(buy_min)s, %(buy_max)s, %(sell_target)s, %(active)s)
            ON CONFLICT (brand, model) 
            DO UPDATE SET
                full_name = EXCLUDED.full_name,
                category = EXCLUDED.category,
                buy_price_min = EXCLUDED.buy_price_min,
                buy_price_max = EXCLUDED.buy_price_max,
                sell_target = EXCLUDED.sell_target,
                active = EXCLUDED.active,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id;
        """, {
            'brand': product_data['brand'],
            'model': product_data['model'],
            'full_name': product_data['full_name'],
            'category': product_data['category'],
            'buy_min': product_data['pricing']['buy_min'],
            'buy_max': product_data['pricing']['buy_max'],
            'sell_target': product_data['pricing']['sell_target'],
            'active': product_data['active']
        })
        
        product_id = cursor.fetchone()[0]
        return product_id
    except Exception as e:
        print(f"❌ Error upserting product {product_data['brand']} {product_data['model']}: {e}")
        return None


def sync_aliases(cursor, product_id, aliases):
    """Delete old aliases and insert new ones"""
    try:
        # Delete existing aliases
        cursor.execute("DELETE FROM product_aliases WHERE product_id = %s", (product_id,))
        
        # Insert new aliases
        for alias in aliases:
            cursor.execute("""
                INSERT INTO product_aliases (product_id, alias)
                VALUES (%s, %s)
            """, (product_id, alias))
    except Exception as e:
        print(f"❌ Error syncing aliases for product {product_id}: {e}")


def sync_fuzzy_patterns(cursor, product_id, patterns):
    """Delete old patterns and insert new ones"""
    try:
        # Delete existing patterns
        cursor.execute("DELETE FROM product_fuzzy_patterns WHERE product_id = %s", (product_id,))
        
        # Insert new patterns
        for pattern in patterns:
            cursor.execute("""
                INSERT INTO product_fuzzy_patterns (product_id, pattern)
                VALUES (%s, %s)
            """, (product_id, pattern))
    except Exception as e:
        print(f"❌ Error syncing fuzzy patterns for product {product_id}: {e}")


def sync_filter_keywords(cursor, filter_data, filter_type):
    """Sync filter keywords (reject or boost)"""
    try:
        keywords = filter_data.get('keywords', [])
        description = filter_data.get('description', '')
        
        for keyword in keywords:
            cursor.execute("""
                INSERT INTO filter_keywords (keyword, filter_type, description)
                VALUES (%s, %s, %s)
                ON CONFLICT (keyword, filter_type) 
                DO UPDATE SET description = EXCLUDED.description
            """, (keyword, filter_type, description))
    except Exception as e:
        print(f"❌ Error syncing {filter_type} keywords: {e}")


def main():
    """Main sync function"""
    print("📂 Scanning YAML files...")
    
    # Connect to database
    conn = connect_db()
    cursor = conn.cursor()
    
    products_synced = 0
    errors = 0
    
    try:
        # Sync Canon cameras
        canon_dir = Path('Products/Cameras/Canon')
        if canon_dir.exists():
            print(f"\n📷 Syncing Canon cameras from {canon_dir}")
            for yaml_file in canon_dir.glob('*.yml'):
                product_data = load_yaml_file(yaml_file)
                if product_data:
                    product_id = upsert_product(cursor, product_data)
                    if product_id:
                        sync_aliases(cursor, product_id, product_data.get('aliases', []))
                        sync_fuzzy_patterns(cursor, product_id, product_data.get('fuzzy_patterns', []))
                        print(f"  ✅ {product_data['brand']} {product_data['model']}")
                        products_synced += 1
                    else:
                        errors += 1
        
        # Sync Nikon cameras
        nikon_dir = Path('Products/Cameras/Nikon')
        if nikon_dir.exists():
            print(f"\n📷 Syncing Nikon cameras from {nikon_dir}")
            for yaml_file in nikon_dir.glob('*.yml'):
                product_data = load_yaml_file(yaml_file)
                if product_data:
                    product_id = upsert_product(cursor, product_data)
                    if product_id:
                        sync_aliases(cursor, product_id, product_data.get('aliases', []))
                        sync_fuzzy_patterns(cursor, product_id, product_data.get('fuzzy_patterns', []))
                        print(f"  ✅ {product_data['brand']} {product_data['model']}")
                        products_synced += 1
                    else:
                        errors += 1
        
        # Sync filter keywords (reject)
        reject_file = Path('Products/Cameras/Matching/filters_reject.yml')
        if reject_file.exists():
            print(f"\n🚫 Syncing rejection filters")
            reject_data = load_yaml_file(reject_file)
            if reject_data:
                sync_filter_keywords(cursor, reject_data, 'reject')
                print(f"  ✅ {len(reject_data.get('keywords', []))} reject keywords")
        
        # Sync filter keywords (boost)
        boost_file = Path('Products/Cameras/Matching/filters_boost.yml')
        if boost_file.exists():
            print(f"\n⭐ Syncing boost filters")
            boost_data = load_yaml_file(boost_file)
            if boost_data:
                sync_filter_keywords(cursor, boost_data, 'boost')
                print(f"  ✅ {len(boost_data.get('keywords', []))} boost keywords")
        
        # Commit transaction
        conn.commit()
        
        # Summary
        print(f"\n" + "="*50)
        print(f"📊 Summary:")
        print(f"   Products synced: {products_synced}")
        print(f"   Errors: {errors}")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Sync failed: {e}")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    main()