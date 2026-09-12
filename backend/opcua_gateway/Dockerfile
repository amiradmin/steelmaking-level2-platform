FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120

ARG PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_TRUSTED_HOST=

COPY opcua_gateway/requirements.txt ./requirements.txt
RUN if [ -n "$PIP_TRUSTED_HOST" ]; then \
      python -m pip install --no-cache-dir --retries 10 --timeout 120 \
        --index-url "$PIP_INDEX_URL" --trusted-host "$PIP_TRUSTED_HOST" \
        -r requirements.txt; \
    else \
      python -m pip install --no-cache-dir --retries 10 --timeout 120 \
        --index-url "$PIP_INDEX_URL" \
        -r requirements.txt; \
    fi

COPY opcua_gateway/gateway.py opcua_gateway/healthcheck.py ./
COPY plc_simulators/s7_address_map.json ./s7_address_map.json

HEALTHCHECK --interval=10s --timeout=4s --start-period=20s --retries=3 \
    CMD ["python", "healthcheck.py"]

CMD ["python", "gateway.py"]
