#!/usr/bin/env python3
"""
Initialize MIMIC-III demo database with data from CSV files.
This script creates tables and imports data into PostgreSQL.
"""

import os
import csv
from dotenv import load_dotenv
from psycopg2 import connect, sql
from psycopg2.extensions import connection
from pathlib import Path
from tqdm import tqdm
from utils.set_master_path import switch_to_app_context
switch_to_app_context()



from api.config import get_database_connection_schema

load_dotenv()
config_schema = get_database_connection_schema()

MIMIC_DATA_DIR = Path(os.getenv('MIMIC_DATA_DIR', '.sources/mimic'))
SCHEMA_FILE = MIMIC_DATA_DIR / '.create_tables.sql'


def connect_db():
    """Create database connection."""
    try:
        conn = connect(**config_schema)
        print(f"✓ Connected to database: {config_schema['database']}")
        return conn
    except Exception as e:
        print(f"✗ Failed to connect to database: {e}")
        raise


def create_schema(conn: connection):
    """Create MIMIC-III schema from SQL file."""
    print("\nCreating schema...")
    try:
        with conn.cursor() as cur:
            # Create mimiciii schema first
            cur.execute("CREATE SCHEMA IF NOT EXISTS mimiciii")
            print("✓ Schema 'mimiciii' created")

            # Set search path to mimiciii schema
            cur.execute("SET search_path TO mimiciii, public")

            # Read and execute schema SQL
            with open(SCHEMA_FILE, 'r') as f:
                schema_sql = f.read()
            cur.execute(schema_sql)

        conn.commit()
        print("✓ Tables created in mimiciii schema")
    except Exception as e:
        print(f"✗ Failed to create schema: {e}")
        conn.rollback()
        raise


def import_csv_to_table(conn: connection, table_name: str, csv_file: Path):
    """Import CSV file into PostgreSQL table in mimiciii schema."""
    if not csv_file.exists():
        print(f"  ⚠ File not found: {csv_file}")
        return

    try:
        # Get row count for progress bar
        with open(csv_file, 'r', encoding='utf-8') as f:
            row_count = sum(1 for _ in f) - 1  # Exclude header

        if row_count == 0:
            print(f"  ⚠ {table_name}: No data to import")
            return

        # Import data
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)  # Skip header

            with conn.cursor() as cur:
                # Set search path to mimiciii schema
                cur.execute("SET search_path TO mimiciii, public")

                # Prepare insert statement - use lowercase table name and mimiciii schema
                table_lower = table_name.lower()
                columns = sql.SQL(', ').join(map(sql.Identifier, headers))
                placeholders = sql.SQL(', ').join(sql.Placeholder() * len(headers))
                insert_query = sql.SQL("INSERT INTO mimiciii.{} ({}) VALUES ({})").format(
                    sql.Identifier(table_lower),
                    columns,
                    placeholders
                )

                # Insert rows with progress bar
                rows_imported = 0
                with tqdm(total=row_count, desc=f"  {table_name:20s}", unit="rows") as pbar:
                    for row in reader:
                        # Convert empty strings to None for NULL values
                        row = [None if val == '' else val for val in row]
                        cur.execute(insert_query, row)
                        rows_imported += 1
                        pbar.update(1)

                        # Commit in batches
                        if rows_imported % 1000 == 0:
                            conn.commit()

                conn.commit()

        print(f"  ✓ {table_name}: {rows_imported:,} rows imported")


    except Exception as e:
        print(f"  ✗ {table_name}: Failed - {e}")
        conn.rollback()


def import_all_data(conn: connection):
    """Import all MIMIC-III CSV files."""
    print("\nImporting data from CSV files...")

    # List of tables to import (in order to respect foreign keys)
    tables = [
        'ADMISSIONS',
        'CALLOUT',
        'CAREGIVERS',
        'D_CPT',
        'D_ICD_DIAGNOSES',
        'D_ICD_PROCEDURES',
        'D_ITEMS',
        'D_LABITEMS',
        'PATIENTS',
        'ICUSTAYS',
        'TRANSFERS',
        'SERVICES',
        'CHARTEVENTS',
        'CPTEVENTS',
        'DATETIMEEVENTS',
        'DIAGNOSES_ICD',
        'DRGCODES',
        'INPUTEVENTS_CV',
        'INPUTEVENTS_MV',
        'LABEVENTS',
        'MICROBIOLOGYEVENTS',
        'NOTEEVENTS',
        'OUTPUTEVENTS',
        'PRESCRIPTIONS',
        'PROCEDUREEVENTS_MV',
        'PROCEDURES_ICD',
    ]

    for table in tables:
        csv_file = MIMIC_DATA_DIR / f'{table}.csv'
        import_csv_to_table(conn, table, csv_file)


def verify_import(conn: connection):
    """Verify data import by counting rows in mimiciii schema."""
    print("\nVerifying data import...")

    with conn.cursor() as cur:
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'mimiciii'
            ORDER BY table_name
        """)
        tables = [row[0] for row in cur.fetchall()]

        print(f"\n{'Table':<25} {'Row Count':>15}")
        print("-" * 42)

        total_rows = 0
        for table in tables:
            cur.execute(f"SELECT COUNT(*) FROM mimiciii.{table}")
            result = cur.fetchone()
            count = result[0] if result else 0
            total_rows += count
            print(f"{table:<25} {count:>15,}")

        print("-" * 42)
        print(f"{'TOTAL':<25} {total_rows:>15,}")


def main():
    """Main execution function."""
    print("=" * 50)
    print("MIMIC-III PostgreSQL Database Initialization")
    print("=" * 50)

    # Check data directory
    if not MIMIC_DATA_DIR.exists():
        print(f"✗ Data directory not found: {MIMIC_DATA_DIR}")
        return

    if not SCHEMA_FILE.exists():
        print(f"✗ Schema file not found: {SCHEMA_FILE}")
        return

    print(f"✓ Data directory: {MIMIC_DATA_DIR}")

    # Connect and initialize
    conn = connect()

    try:
        create_schema(conn)
        import_all_data(conn)
        verify_import(conn)

        print("\n" + "=" * 50)
        print("Database initialization complete!")
        print("=" * 50)

    finally:
        conn.close()


if __name__ == '__main__':
    main()
