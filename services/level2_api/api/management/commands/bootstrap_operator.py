from __future__ import annotations

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Create the initial operator account when credentials are configured."""

    help = "Create the initial Level 2 operator if it does not already exist."

    def handle(self, *args: object, **options: object) -> None:
        del args, options
        username = os.getenv("DJANGO_BOOTSTRAP_USERNAME", "").strip()
        password = os.getenv("DJANGO_BOOTSTRAP_PASSWORD", "")
        display_name = os.getenv("DJANGO_BOOTSTRAP_DISPLAY_NAME", "").strip()

        if not username or not password:
            self.stdout.write("Bootstrap operator skipped: credentials are not configured.")
            return

        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(username=username)
        if not created:
            self.stdout.write(f"Bootstrap operator {username} already exists.")
            return

        user.first_name = display_name
        user.set_password(password)
        user.save(update_fields=["first_name", "password"])
        self.stdout.write(self.style.SUCCESS(f"Bootstrap operator {username} created."))
