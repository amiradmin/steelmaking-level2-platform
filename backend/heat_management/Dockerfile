FROM debian:trixie-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      python3 \
      python3-fastapi \
      python3-uvicorn \
      python3-pydantic \
      python3-psycopg \
      python3-psycopg-c \
      python3-cryptography \
    && python3 -c "import fastapi, pydantic, psycopg; from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey; print('Heat management Debian dependency check OK')" \
    && rm -rf /var/lib/apt/lists/*

COPY app ./app

EXPOSE 9000

CMD ["uvicorn", "app.licensed:app", "--host", "0.0.0.0", "--port", "9000"]
