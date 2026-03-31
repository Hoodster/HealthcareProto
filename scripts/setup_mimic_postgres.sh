#!/bin/bash

# Script to set up MIMIC-III demo data in local PostgreSQL database
# Usage: ./setup_mimic_postgres.sh

set -e  # Exit on error

# Configuration
DB_NAME="mimic_demo"
DB_USER="mimic_user"
DB_PASSWORD="mimic_password"
DB_HOST="localhost"
DB_PORT="5432"
MIMIC_DATA_DIR=".sources/mimic"

echo "=========================================="
echo "MIMIC-III PostgreSQL Database Setup"
echo "=========================================="
echo ""

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo "Error: PostgreSQL is not installed."
    echo "On macOS, install with: brew install postgresql@15"
    echo "Then start the service: brew services start postgresql@15"
    exit 1
fi

# Check if PostgreSQL is running
if ! pg_isready -h $DB_HOST -p $DB_PORT &> /dev/null; then
    echo "Error: PostgreSQL is not running on $DB_HOST:$DB_PORT"
    echo "Start it with: brew services start postgresql@15"
    exit 1
fi

echo "✓ PostgreSQL is installed and running"
echo ""

# Create database and user
echo "Creating database and user..."
psql -h $DB_HOST -p $DB_PORT -U $(whoami) postgres <<EOF
-- Drop database if exists
DROP DATABASE IF EXISTS $DB_NAME;

-- Drop user if exists
DROP USER IF EXISTS $DB_USER;

-- Create user
CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';

-- Create database
CREATE DATABASE $DB_NAME OWNER $DB_USER;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
EOF

echo "✓ Database '$DB_NAME' created"
echo ""

# Create schema and tables
echo "Creating MIMIC-III schema..."
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME < "$MIMIC_DATA_DIR/.create_tables.sql"
echo "✓ Schema created"
echo ""

# Import CSV data
echo "Importing CSV data..."
echo "This may take a few minutes..."

# Function to import CSV file
import_csv() {
    local table_name=$1
    local file_name="${MIMIC_DATA_DIR}/${table_name}.csv"
    
    if [ -f "$file_name" ]; then
        echo "  - Importing $table_name..."
        psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "\COPY $table_name FROM '$file_name' DELIMITER ',' CSV HEADER;"
    else
        echo "  ! Warning: $file_name not found, skipping..."
    fi
}

# Import all tables
import_csv "ADMISSIONS"
import_csv "CALLOUT"
import_csv "CAREGIVERS"
import_csv "CHARTEVENTS"
import_csv "CPTEVENTS"
import_csv "DATETIMEEVENTS"
import_csv "DIAGNOSES_ICD"
import_csv "DRGCODES"
import_csv "D_CPT"
import_csv "D_ICD_DIAGNOSES"
import_csv "D_ICD_PROCEDURES"
import_csv "D_ITEMS"
import_csv "D_LABITEMS"
import_csv "ICUSTAYS"
import_csv "INPUTEVENTS_CV"
import_csv "INPUTEVENTS_MV"
import_csv "LABEVENTS"
import_csv "MICROBIOLOGYEVENTS"
import_csv "NOTEEVENTS"
import_csv "OUTPUTEVENTS"
import_csv "PATIENTS"
import_csv "PRESCRIPTIONS"
import_csv "PROCEDUREEVENTS_MV"
import_csv "PROCEDURES_ICD"
import_csv "SERVICES"
import_csv "TRANSFERS"

echo ""
echo "✓ Data import complete"
echo ""

# Verify data
echo "Verifying data import..."
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME <<EOF
SELECT 
    'PATIENTS' as table_name, COUNT(*) as row_count FROM PATIENTS
UNION ALL
SELECT 'ADMISSIONS', COUNT(*) FROM ADMISSIONS
UNION ALL
SELECT 'ICUSTAYS', COUNT(*) FROM ICUSTAYS
UNION ALL
SELECT 'LABEVENTS', COUNT(*) FROM LABEVENTS
UNION ALL
SELECT 'NOTEEVENTS', COUNT(*) FROM NOTEEVENTS;
EOF

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Database connection details:"
echo "  Host:     $DB_HOST"
echo "  Port:     $DB_PORT"
echo "  Database: $DB_NAME"
echo "  User:     $DB_USER"
echo "  Password: $DB_PASSWORD"
echo ""
echo "Connection string:"
echo "  postgresql://$DB_USER:$DB_PASSWORD@$DB_HOST:$DB_PORT/$DB_NAME"
echo ""
echo "Add this to your .env file:"
echo "  DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@$DB_HOST:$DB_PORT/$DB_NAME"
echo ""
