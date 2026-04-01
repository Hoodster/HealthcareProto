#!/bin/bash
# Quick setup script for PostgreSQL migration

set -e  # Exit on error

echo "==========================================="
echo "PostgreSQL Migration Setup"
echo "==========================================="
echo ""

# Check if docker-compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose not found. Please install Docker first."
    exit 1
fi

echo "1️⃣  Starting PostgreSQL container..."
docker-compose up -d postgres

echo ""
echo "2️⃣  Waiting for PostgreSQL to be ready..."
sleep 5

# Check if PostgreSQL is ready
until docker exec mimic-postgres pg_isready -U mimic_user -d mimic_demo > /dev/null 2>&1; do
    echo "   Waiting for PostgreSQL..."
    sleep 2
done

echo "   ✓ PostgreSQL is ready!"

echo ""
echo "3️⃣  Verifying connection..."
python3 verify_postgres.py

echo ""
echo "==========================================="
echo "✓ Setup complete!"
echo "==========================================="
echo ""
echo "Next steps:"
echo ""
echo "  1. Migrate your SQLite data:"
echo "     python3 migrate_to_postgres.py"
echo ""
echo "  2. Initialize MIMIC-III data (if needed):"
echo "     python3 init_mimic_db.py"
echo ""
echo "  3. Start your application:"
echo "     uvicorn api.app:create_app --factory --reload"
echo ""
echo "For more information, see MIGRATION_GUIDE.md"
echo ""
