# Setup

## Dependencies
postgres + docker + python 3.13

## Before

### Docker
```bash
# Start PostgreSQL with docker-compose
docker-compose up -d postgres

# Verify it's running
docker ps | grep mimic-postgres

# Test connection
psql postgresql://USER:PASSWORD@localhost:5432/mimic_demo -c "SELECT version();"
```

### Copy environment and fill
```bash
cp .env.example .env
```

## Install
```bash
python3 -m venv .venv
source .venv/bin/activate

pip3 install -r requirements.txt 
```

## Run
```bash
source .venv/bin/activate # optional
python3 -m uvicorn api.app:app --host 127.0.0.1 --port 8000 --reload
```

## Documentation
http://localhost:8000/hp_proto/api/swagger

# TODO
- drug database (drug-to-druge, safety db)
- 