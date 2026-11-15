import os
import time

import django
from django.db import OperationalError, connection

MAX_ATTEMPTS = 30
RETRY_DELAY_SECONDS = 2
CONNECT_TIMEOUT_SECONDS = 3


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "level2_project.settings")
    django.setup()

    if connection.vendor == "postgresql":
        connection.settings_dict["OPTIONS"]["connect_timeout"] = CONNECT_TIMEOUT_SECONDS

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            connection.ensure_connection()
        except OperationalError:
            if attempt == MAX_ATTEMPTS:
                raise
            if attempt == 1 or attempt % 5 == 0:
                print(f"Waiting for database ({attempt}/{MAX_ATTEMPTS})", flush=True)
            time.sleep(RETRY_DELAY_SECONDS)
        else:
            connection.close()
            print("Database connection ready", flush=True)
            return


if __name__ == "__main__":
    main()
