from django.core.management.base import BaseCommand

from api.rbac import ensure_role_groups


class Command(BaseCommand):
    help = "Create the managed Level 2 RBAC role groups."

    def handle(self, *args, **options) -> None:
        del args, options
        ensure_role_groups()
        self.stdout.write(self.style.SUCCESS("Level 2 RBAC roles are ready."))
