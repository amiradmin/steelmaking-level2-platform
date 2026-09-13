FROM debian:trixie-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      python3 \
      python3-django \
      python3-djangorestframework \
      python3-djangorestframework-simplejwt \
      python3-djangorestframework-spectacular \
      python3-django-cors-headers \
      python3-django-channels \
      python3-daphne \
      python3-psycopg \
      python3-psycopg-c \
      python3-cryptography \
    && python3 -c "import django, rest_framework, psycopg, corsheaders, channels, daphne, rest_framework_simplejwt, drf_spectacular; from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey; print('Level 2 Debian dependency check OK', django.get_version(), rest_framework.VERSION)" \
    && rm -rf /var/lib/apt/lists/*

COPY . .

EXPOSE 8080

CMD ["sh", "-c", "python3 manage.py migrate --noinput && python3 manage.py bootstrap_operator && daphne -b 0.0.0.0 -p 8080 level2_project.asgi:application"]
