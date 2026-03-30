# Setup

## Dependencies
postgres + docker + python 3.13

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