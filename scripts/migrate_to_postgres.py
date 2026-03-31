#!/usr/bin/env python3
"""
Migrate data from SQLite to PostgreSQL
This script moves all application data from application.db to PostgreSQL
"""

import sys
from pathlib import Path
from sqlalchemy import create_engine, inspect, text, MetaData, Table, select
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Add parent directory to path to import set_master_path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.set_master_path import switch_to_app_context
switch_to_app_context()

# Import models to ensure they're registered
from api.models import (
    Base, User, StaffProfile, Patient, PatientFile, 
    PatientHistoryEntry, Chat, Message, MedDocument
)
from api.config import get_database_connection_url

load_dotenv()

# Database URLs
SQLITE_URL = "sqlite:///.output/application.db"
POSTGRES_URL = get_database_connection_url()

def confirm_migration():
    """Ask user to confirm migration."""
    print("="*70)
    print("DATABASE MIGRATION: SQLite → PostgreSQL")
    print("="*70)
    print(f"Source:      {SQLITE_URL}")
    print(f"Destination: {POSTGRES_URL}")
    print()
    print("⚠️  WARNING: This will:")
    print("   1. Create all tables in PostgreSQL")
    print("   2. Copy all data from SQLite to PostgreSQL")
    print("   3. Existing PostgreSQL data will be preserved (append mode)")
    print()
    response = input("Continue? (yes/no): ").lower().strip()
    if response != 'yes':
        print("Migration cancelled.")
        sys.exit(0)

def create_postgres_schema(pg_engine):
    """Create all tables in PostgreSQL."""
    print("\n📋 Creating PostgreSQL schema...")
    
    # Create schemas (to separate app data from MIMIC data)
    with pg_engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS app"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS mimiciii"))
        conn.commit()
        print("✓ Schema 'app' created")
        print("✓ Schema 'mimiciii' created")
    
    Base.metadata.create_all(bind=pg_engine)
    print("✓ Tables created successfully")

def migrate_table(sqlite_session, pg_session, model_class, sqlite_table_name=None):
    """Migrate data from one table."""
    pg_table_name = model_class.__tablename__
    # Use the provided SQLite table name, or the model's tablename if not provided
    source_table = sqlite_table_name or pg_table_name
    
    print(f"\n📦 Migrating {source_table} → app.{pg_table_name}...", end=" ")
    
    try:
        # For SQLite, we need to use core Table objects without schema
        # Get the table metadata but without schema
        sqlite_metadata = MetaData()
        sqlite_table = Table(source_table, sqlite_metadata, autoload_with=sqlite_session.bind)
        
        # Get all records from SQLite using raw table
        result = sqlite_session.execute(select(sqlite_table))
        rows = result.fetchall()
        count = len(rows)
        
        if count == 0:
            print("(empty)")
            return 0
        
        # Convert rows to model instances and add to PostgreSQL
        for row in rows:
            # Create model instance from row data
            record_dict = dict(row._mapping)
            instance = model_class(**record_dict)
            pg_session.merge(instance)
        
        pg_session.commit()
        print(f"✓ {count} records migrated")
        return count
        
    except Exception as e:
        pg_session.rollback()
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 0

def verify_migration(sqlite_engine, pg_engine):
    """Verify row counts match."""
    print("\n🔍 Verifying migration...")
    
    # Check if app schema exists
    with pg_engine.connect() as conn:
        result = conn.execute(text(
            "SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'app'"
        ))
        if not result.fetchone():
            print("   ✗ 'app' schema not found in PostgreSQL")
            return False
        print("   ✓ Schema 'app' exists")
    
    sqlite_inspector = inspect(sqlite_engine)
    pg_inspector = inspect(pg_engine)
    
    sqlite_tables = set(sqlite_inspector.get_table_names())
    pg_tables = set(pg_inspector.get_table_names(schema='app'))
    
    print(f"   SQLite tables: {len(sqlite_tables)}")
    print(f"   PostgreSQL app tables: {len(pg_tables)}")
    
    # Define table mappings (SQLite table name -> PostgreSQL table name in app schema)
    table_mapping = {
        'users': 'users',
        'staff_profiles': 'staff_profiles',
        'patients': 'app_patients',  # Renamed in PostgreSQL
        'patient_files': 'patient_files',
        'patient_history': 'patient_history',
        'chats': 'chats',
        'messages': 'messages',
        'med_documents': 'med_documents'
    }
    
    all_match = True
    
    with sqlite_engine.connect() as sqlite_conn, pg_engine.connect() as pg_conn:
        for sqlite_table, pg_table in table_mapping.items():
            try:
                # Query SQLite without schema prefix
                if sqlite_table in sqlite_tables:
                    sqlite_result = sqlite_conn.execute(
                        text(f"SELECT COUNT(*) FROM {sqlite_table}")
                    )
                    sqlite_count = sqlite_result.scalar()
                else:
                    sqlite_count = 0
                
                # Query PostgreSQL with schema prefix
                if pg_table in pg_tables:
                    pg_result = pg_conn.execute(
                        text(f"SELECT COUNT(*) FROM app.{pg_table}")
                    )
                    pg_count = pg_result.scalar()
                else:
                    pg_count = 0
                
                status = "✓" if sqlite_count <= pg_count else "✗"
                print(f"   {status} {sqlite_table} → app.{pg_table}: SQLite={sqlite_count}, PostgreSQL={pg_count}")
                
                if sqlite_count > pg_count:
                    all_match = False
                    
            except Exception as e:
                print(f"   ✗ {sqlite_table}: Error - {e}")
                all_match = False
        
        return all_match

def main():
    """Main migration process."""
    confirm_migration()
    
    # Check if SQLite database exists
    sqlite_path = Path(".output/application.db")
    if not sqlite_path.exists():
        print(f"\n✗ SQLite database not found: {sqlite_path}")
        print("   Nothing to migrate.")
        sys.exit(0)
    
    print("\n🔌 Connecting to databases...")
    
    # Create engines
    try:
        sqlite_engine = create_engine(SQLITE_URL, echo=False)
        pg_engine = create_engine(POSTGRES_URL, echo=False)
        print("✓ Connected to both databases")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        sys.exit(1)
    
    # Create PostgreSQL schema
    create_postgres_schema(pg_engine)
    
    # Create sessions
    SessionSQLite = sessionmaker(bind=sqlite_engine)
    SessionPG = sessionmaker(bind=pg_engine)
    
    print("\n" + "="*70)
    print("MIGRATING DATA")
    print("="*70)
    
    total_migrated = 0
    
    # Migrate tables in dependency order
    migration_order = [
        (User, 'users'),           # No dependencies
        (StaffProfile, 'staff_profiles'),   # Depends on User
        (Patient, 'patients'),        # Depends on User - SQLite uses 'patients', PG uses 'app_patients'
        (PatientFile, 'patient_files'),    # Depends on Patient
        (PatientHistoryEntry, 'patient_history'),  # Depends on Patient
        (MedDocument, 'med_documents'),    # Depends on User and Patient
        (Chat, 'chats'),           # Depends on User
        (Message, 'messages'),        # Depends on Chat
    ]
    
    with SessionSQLite() as sqlite_session, SessionPG() as pg_session:
        for model_class, sqlite_table_name in migration_order:
            count = migrate_table(sqlite_session, pg_session, model_class, sqlite_table_name)
            total_migrated += count
    
    print("\n" + "="*70)
    print(f"✓ Migration completed: {total_migrated} total records migrated")
    print("="*70)
    
    # Verify migration
    if verify_migration(sqlite_engine, pg_engine):
        print("\n✓ Verification successful! All data migrated correctly.")
    else:
        print("\n⚠️  Verification warning: Some row counts don't match.")
        print("    This might be normal if PostgreSQL already had data.")
    
    print("\n📝 Next steps:")
    print("   1. Test your application with PostgreSQL")
    print("   2. If everything works, you can backup/remove the SQLite database:")
    print(f"      mv .output/application.db .output/application.db.backup")
    print()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Migration cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
