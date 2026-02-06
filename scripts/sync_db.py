#!/usr/bin/env python3
"""
sync_to_db.py - Sync YAML product and filter files to Neon database

Scans the Products/ folder recursively for *.yml files.
- Product YAML schema:
  brand, model, full_name, category, pricing{buy_min,buy_max,sell_target}, active
  optional: aliases[], fuzzy_patterns[]
- Filter YAML schema:
  keywords[], optional description
  inferred filter_type from filename/path (boost/reject)
"""

import os
import sys
from pathlib import Path

import psycopg2
import yaml
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("DATABASE_URL not found in .env file.")
    sys.exit(1)


def connect_db():
    """Connect to Neon database."""
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        print(f"Database connection failed: {e}")
        sys.exit(1)


def load_yaml_file(filepath: Path):
    """Load and parse YAML file."""
    try:
        with filepath.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None


def is_product_yaml(data: dict) -> bool:
    """Heuristic to detect product YAML files."""
    if not isinstance(data, dict):
        return False

    required_top = {"brand", "model", "full_name", "category", "pricing", "active"}
    if not required_top.issubset(data.keys()):
        return False

    pricing = data.get("pricing")
    if not isinstance(pricing, dict):
        return False

    required_pricing = {"buy_min", "buy_max", "sell_target"}
    return required_pricing.issubset(pricing.keys())


def is_filter_yaml(data: dict) -> bool:
    """Heuristic to detect filter YAML files (boost/reject keywords)."""
    if not isinstance(data, dict):
        return False
    keywords = data.get("keywords")
    return isinstance(keywords, list)


def infer_filter_type(filepath: Path) -> str | None:
    """
    Infer filter type from file name/path.
    Looks for 'boost' or 'reject' anywhere in the filename or parent folders.
    """
    haystack = " ".join(
        [filepath.name.lower()] + [p.name.lower() for p in filepath.parents]
    )
    if "reject" in haystack:
        return "reject"
    if "boost" in haystack:
        return "boost"
    return None


def upsert_product(cursor, product_data: dict) -> int | None:
    """Insert or update product and return product id."""
    try:
        cursor.execute(
            """
            INSERT INTO products (
                brand, model, full_name, category,
                buy_price_min, buy_price_max, sell_target, active
            )
            VALUES (
                %(brand)s, %(model)s, %(full_name)s, %(category)s,
                %(buy_min)s, %(buy_max)s, %(sell_target)s, %(active)s
            )
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
            """,
            {
                "brand": product_data["brand"],
                "model": product_data["model"],
                "full_name": product_data["full_name"],
                "category": product_data["category"],
                "buy_min": product_data["pricing"].get("buy_min"),
                "buy_max": product_data["pricing"].get("buy_max"),
                "sell_target": product_data["pricing"].get("sell_target"),
                "active": product_data.get("active", True),
            },
        )
        return cursor.fetchone()[0]
    except Exception as e:
        print(
            f"Error upserting product {product_data.get('brand')} {product_data.get('model')}: {e}"
        )
        return None


def sync_aliases(cursor, product_id: int, aliases: list[str]):
    """Delete old aliases and insert new ones."""
    try:
        cursor.execute(
            "DELETE FROM product_aliases WHERE product_id = %s", (product_id,)
        )
        for alias in aliases or []:
            cursor.execute(
                "INSERT INTO product_aliases (product_id, alias) VALUES (%s, %s)",
                (product_id, alias),
            )
    except Exception as e:
        print(f"Error syncing aliases for product {product_id}: {e}")


def sync_fuzzy_patterns(cursor, product_id: int, patterns: list[str]):
    """Delete old patterns and insert new ones."""
    try:
        cursor.execute(
            "DELETE FROM product_fuzzy_patterns WHERE product_id = %s", (product_id,)
        )
        for pattern in patterns or []:
            cursor.execute(
                "INSERT INTO product_fuzzy_patterns (product_id, pattern) VALUES (%s, %s)",
                (product_id, pattern),
            )
    except Exception as e:
        print(f"Error syncing fuzzy patterns for product {product_id}: {e}")


def sync_filter_keywords(cursor, filter_data: dict, filter_type: str):
    """Sync filter keywords (reject or boost)."""
    try:
        keywords = filter_data.get("keywords", []) or []
        description = filter_data.get("description", "") or ""

        for keyword in keywords:
            cursor.execute(
                """
                INSERT INTO filter_keywords (keyword, filter_type, description)
                VALUES (%s, %s, %s)
                ON CONFLICT (keyword, filter_type)
                DO UPDATE SET description = EXCLUDED.description
                """,
                (keyword, filter_type, description),
            )
    except Exception as e:
        print(f"Error syncing {filter_type} keywords: {e}")


def main():
    products_root = Path("Products")
    if not products_root.exists():
        print("Products/ folder not found. Nothing to sync.")
        sys.exit(0)

    print(f"Scanning YAML files under: {products_root.resolve()}")

    conn = connect_db()
    cursor = conn.cursor()

    products_synced = 0
    filter_keywords_synced = 0
    skipped = 0
    errors = 0

    try:
        yaml_files = sorted(products_root.rglob("*.yml"))

        for yaml_file in yaml_files:
            data = load_yaml_file(yaml_file)
            if data is None:
                errors += 1
                continue

            # Product file
            if is_product_yaml(data):
                product_id = upsert_product(cursor, data)
                if product_id:
                    sync_aliases(cursor, product_id, data.get("aliases", []))
                    sync_fuzzy_patterns(
                        cursor, product_id, data.get("fuzzy_patterns", [])
                    )
                    print(
                        f"Synced product: {data['brand']} {data['model']} ({yaml_file})"
                    )
                    products_synced += 1
                else:
                    errors += 1
                continue

            # Filter file
            if is_filter_yaml(data):
                filter_type = infer_filter_type(yaml_file)
                if not filter_type:
                    skipped += 1
                    print(f"Skipped filter file (unknown type): {yaml_file}")
                    continue

                sync_filter_keywords(cursor, data, filter_type)
                count = len(data.get("keywords", []) or [])
                filter_keywords_synced += count
                print(f"Synced {filter_type} keywords: {count} ({yaml_file})")
                continue

            # Unknown YAML schema
            skipped += 1
            print(f"Skipped unknown YAML schema: {yaml_file}")

        conn.commit()

        print("\n" + "=" * 60)
        print("Summary")
        print(f"Products synced: {products_synced}")
        print(f"Filter keywords synced: {filter_keywords_synced}")
        print(f"Skipped files: {skipped}")
        print(f"Errors: {errors}")

    except Exception as e:
        conn.rollback()
        print(f"Sync failed: {e}")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
