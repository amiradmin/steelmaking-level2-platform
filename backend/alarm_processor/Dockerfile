# syntax=docker/dockerfile:1.7
FROM python:3.13-slim-trixie

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --retries 10 --timeout 120 -r requirements.txt

COPY processor.py ./

CMD ["python", "processor.py"]
