FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120

ARG PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_TRUSTED_HOST=

COPY requirements.txt .
RUN if [ -n "$PIP_TRUSTED_HOST" ]; then \
      python -m pip install --no-cache-dir --retries 10 --timeout 120 \
        --index-url "$PIP_INDEX_URL" --trusted-host "$PIP_TRUSTED_HOST" \
        -r requirements.txt; \
    else \
      python -m pip install --no-cache-dir --retries 10 --timeout 120 \
        --index-url "$PIP_INDEX_URL" \
        -r requirements.txt; \
    fi

COPY common.py eaf_simulator.py lf_simulator.py ccm_simulator.py ./

CMD ["python", "eaf_simulator.py"]
