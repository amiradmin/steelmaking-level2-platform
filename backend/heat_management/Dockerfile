FROM python:3.13-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/usr/lib/python3/dist-packages

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      python3-cryptography \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    python -c "from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey; print('Heat management license crypto check OK')"

COPY app ./app

EXPOSE 9000

CMD ["uvicorn", "app.licensed:app", "--host", "0.0.0.0", "--port", "9000"]
