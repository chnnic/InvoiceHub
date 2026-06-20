import secrets
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()

class Command(BaseCommand):
    help = "Create the initial superuser if it does not exist."

    def handle(self, *args, **options):
        username = getattr(settings, "SUPERUSER_USERNAME", "admin")
        email = getattr(settings, "SUPERUSER_EMAIL", "admin@example.com")
        password = getattr(settings, "SUPERUSER_PASSWORD", "")
        user = User.objects.filter(username=username).first()
        if user:
            self.stdout.write(self.style.SUCCESS(f"Superuser already exists: {username}"))
            return
        if not password:
            password = secrets.token_urlsafe(16)
            self.stdout.write(self.style.WARNING(f"Generated superuser password: {password}"))
        user = User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"Created superuser: {user.username}"))
