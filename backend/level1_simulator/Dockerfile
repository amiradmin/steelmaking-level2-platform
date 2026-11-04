FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120

ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/

COPY requirements.txt .
RUN python -m pip install --no-cache-dir --retries 10 --timeout 120 \
    --index-url "$PIP_INDEX_URL" -r requirements.txt

COPY simulator.py .

CMD ["python", "simulator.py"]
