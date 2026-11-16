from datetime import time, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from booking.models import Doctor, Slot, Specialty


class Command(BaseCommand):
    help = "Add fictional doctors, a patient and future slots to a local demo database."

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        password = "ClearwayDemo!26"
        patient, created = User.objects.get_or_create(username="demo_patient")
        if created:
            patient.set_password(password)
            patient.save(update_fields=["password"])

        profiles = [
            ("demo_cardio", "Dr. Ananya Rao", "Cardiology", 12, "850.00",
             "Consultations for heart health, blood pressure, and follow-up care."),
            ("demo_skin", "Dr. Neel Sharma", "Dermatology", 8, "650.00",
             "Consultations for skin, hair, and nail concerns."),
            ("demo_child", "Dr. Meera Iyer", "Pediatrics", 10, "750.00",
             "Routine checkups and pediatric consultations for children and adolescents."),
        ]
        for username, name, specialty_name, experience, fee, bio in profiles:
            account, created = User.objects.get_or_create(username=username)
            if created:
                account.set_password(password)
                account.save(update_fields=["password"])
            specialty, _ = Specialty.objects.get_or_create(name=specialty_name)
            doctor, _ = Doctor.objects.get_or_create(account=account, defaults={
                "name": name, "specialty": specialty, "experience": experience, "fee": fee, "bio": bio,
            })
            for offset in (0, 1, 2, 3):
                date = timezone.localdate() + timedelta(days=offset)
                for hour in (10, 14, 17):
                    start, end = time(hour), time(hour, 30)
                    candidate = Slot(doctor=doctor, date=date, start_time=start, end_time=end)
                    if candidate.starts_at <= timezone.now():
                        continue
                    if not doctor.slots.filter(date=date, start_time__lt=end, end_time__gt=start).exists():
                        candidate.save()
        self.stdout.write(self.style.SUCCESS("Demo ready. Sign in as demo_patient or demo_cardio with ClearwayDemo!26"))
