from getpass import getpass

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create or update the local Adarsh administrator without storing a password in code."

    def handle(self, *args, **options):
        username = "Adarsh"
        password = getpass("Admin password (input hidden): ")
        if not password:
            raise CommandError("Password cannot be empty.")
        confirm = getpass("Confirm admin password: ")
        if password != confirm:
            raise CommandError("Passwords did not match.")
        User = get_user_model()
        user, created = User.objects.get_or_create(username=username)
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        user.save()
        self.stdout.write(self.style.SUCCESS(
            f"Admin {username} {'created' if created else 'updated'} successfully."
        ))
