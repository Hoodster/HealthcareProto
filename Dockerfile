FROM python:3.13-slim

WORKDIR /app
ARG PORT=8000

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE ${PORT}

CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "${PORT}"]