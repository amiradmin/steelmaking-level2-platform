# syntax=docker/dockerfile:1.7
FROM python:3.13-slim-trixie

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/usr/lib/python3/dist-packages

# Use Debian's psycopg package instead of the pip binary extra. This avoids
# platform/index-specific psycopg-binary wheel resolution during Docker builds
# while keeping the processor on psycopg v3.
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
        python3-psycopg \
    && rm -rf /var/lib/apt/lists/* \
    && python -c "import psycopg; from psycopg.types.json import Jsonb; print('alarm processor dependency check OK', psycopg.__version__)"

COPY processor.py ./

CMD ["python", "processor.py"]
