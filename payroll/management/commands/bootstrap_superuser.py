import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create the initial deployment superuser from environment variables."

    def handle(self, *args, **options):
        User = get_user_model()
        if User.objects.filter(is_superuser=True).exists():
            return

        username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
        if not username or not email or not password:
            raise CommandError(
                "Set DJANGO_SUPERUSER_USERNAME, DJANGO_SUPERUSER_EMAIL, and "
                "DJANGO_SUPERUSER_PASSWORD to create the initial superuser."
            )
        if User.objects.filter(username=username).exists():
            raise CommandError(
                f"Username {username!r} exists but is not a superuser."
            )

        User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
        )
        self.stdout.write("Initial deployment superuser created.")
