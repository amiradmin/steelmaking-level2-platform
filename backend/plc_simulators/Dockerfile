# syntax=docker/dockerfile:1.7
FROM python:3.13-slim-trixie

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PYTHONPATH=/usr/lib/python3/dist-packages

ARG PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_TRUSTED_HOST=

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      python3-aiofiles \
      python3-aiosqlite \
      python3-cryptography \
      python3-dateutil \
      python3-openssl \
      python3-pytz \
      python3-sortedcontainers \
      python3-typing-extensions \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN --mount=type=cache,id=steelmaking-pip-cache,target=/root/.cache/pip,sharing=locked \
    if [ -n "$PIP_TRUSTED_HOST" ]; then \
      python -m pip install --retries 10 --timeout 120 \
        --index-url "$PIP_INDEX_URL" --trusted-host "$PIP_TRUSTED_HOST" \
        -r requirements.txt; \
    else \
      python -m pip install --retries 10 --timeout 120 \
        --index-url "$PIP_INDEX_URL" \
        -r requirements.txt; \
    fi && \
    python -m pip install --retries 10 --timeout 120 --no-deps \
      "https://files.pythonhosted.org/packages/3f/0d/2f8fc320a12b6c8b972568a588ae57f4db7e9f7e7f53d02a24d0cebb17d7/asyncua-1.1.8-py3-none-any.whl#sha256=40c57151b93537beb77cb3f1a0190d75cef5326e8c40978de28b69e5b41e6ede" && \
    python -c "import asyncua, cryptography, OpenSSL; print('PLC OPC UA dependency check OK')"

COPY common.py production_timeline.py s7_memory.py s7_address_map.json \
     eaf_simulator.py lf_simulator.py ccm_simulator.py ./

CMD ["python", "eaf_simulator.py"]
