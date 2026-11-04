FROM debian:trixie-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN set -eux; \
    sed -i \
      -e "s|http://deb.debian.org/debian-security|http://mirrors.aliyun.com/debian-security|g" \
      -e "s|http://deb.debian.org/debian|http://mirror.famaserver.com/debian|g" \
      /etc/apt/sources.list.d/debian.sources; \
    apt-get update; \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ca-certificates; \
    sed -i \
      -e "s|http://mirrors.aliyun.com/debian-security|https://mirrors.aliyun.com/debian-security|g" \
      -e "s|http://mirror.famaserver.com/debian|https://mirror.famaserver.com/debian|g" \
      /etc/apt/sources.list.d/debian.sources; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      python3 \
      python-is-python3 \
      python3-fastapi \
      python3-uvicorn \
      python3-pydantic \
      python3-psycopg \
      python3-psycopg-c \
      python3-cryptography \
    && python3 -c "import fastapi, uvicorn, pydantic, psycopg; from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey; print('Heat management Debian dependency check OK')" \
    && rm -rf /var/lib/apt/lists/*

COPY app ./app

EXPOSE 9000

CMD ["python3", "-m", "uvicorn", "app.licensed:app", "--host", "0.0.0.0", "--port", "9000"]
